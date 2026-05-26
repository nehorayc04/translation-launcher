"""
High-level OAuth flow + DRM check for the launcher.

`login()` opens the system browser to Supabase's Google authorize URL,
waits on a loopback HTTP listener for the redirect, exchanges the
auth code for tokens via PKCE, persists them in the OS keyring,
and returns the user profile.

`me()` returns the cached user (refreshing the access token first
if it's about to expire). Returns None if signed out.

`owns_game(game_id)` is the DRM gate the rest of the launcher calls
before letting a download / install proceed.

This module is the ONLY place that touches the Supabase Auth REST
API directly — everything else goes through these four functions.
"""
from __future__ import annotations

import logging
import threading
import time
import webbrowser
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote, urlencode

import requests

from .config import AuthConfigError, SupabaseConfig, load_config
from .loopback import LoopbackListener
from .pkce import generate as pkce_generate
from .storage import StoredToken, TokenStore

log = logging.getLogger(__name__)


def _debug_step(label: str) -> None:
    """Append a timestamped breadcrumb to a sidecar file. The launcher
    runs windowed (no console), and PyInstaller swallows stdout, so
    when the OAuth flow hangs we have no other way to tell which step
    is blocked. Best-effort — never raises."""
    try:
        from pathlib import Path as _P
        p = _P.home() / '.translation_manager' / 'auth_debug.log'
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, 'a', encoding='utf-8') as fh:
            fh.write(f'{time.strftime("%Y-%m-%d %H:%M:%S")}  {label}\n')
    except Exception:
        pass


class AuthError(RuntimeError):
    """Any sign-in / refresh / API failure surfaced to the UI."""


@dataclass
class UserInfo:
    """What the Eel frontend cares about."""
    id:         str
    email:      str
    full_name:  str
    avatar_url: str
    provider:   str

    def to_dict(self) -> dict:
        return {
            'id':        self.id,
            'email':     self.email,
            'fullName':  self.full_name,
            'avatarUrl': self.avatar_url,
            'provider':  self.provider,
        }


# Lazy singletons — created on first use so the auth subsystem doesn't
# load anything (or raise AuthConfigError) until someone actually
# tries to authenticate.
_store: Optional[TokenStore] = None
_cfg:   Optional[SupabaseConfig] = None

# Tracks the LoopbackListener for the currently-active Google OAuth
# attempt so abort_login() can shut it down from another thread. Eel
# runs each exposed function on a worker thread, so reads + writes are
# concurrent — guarded by a Lock. Lock-then-take pattern below: the
# aborter swaps the global to None while holding the lock, then calls
# .abort() outside the lock (abort can call .shutdown() which blocks
# briefly; we don't want to hold the lock during that).
_active_listener:      Optional[LoopbackListener] = None
_active_listener_lock                              = threading.Lock()

# Last-built authorize URL — exposed to the frontend via the
# auth_get_authorize_url Eel bridge so the modal can offer a "copy
# link" affordance. Lets users open the OAuth flow in a different
# browser profile than the OS default, which webbrowser.open() picks
# blindly. Set once per login() attempt right before webbrowser.open;
# cleared when login() returns or aborts so a stale URL with a now-
# closed listener never gets handed back out.
_last_authorize_url:   Optional[str] = None


def get_last_authorize_url() -> Optional[str]:
    """Return the URL of the currently-in-flight Google sign-in
    attempt, or None if no attempt is active. The URL embeds a PKCE
    challenge that ONLY this process can redeem, so handing it to the
    user (who pastes it into another browser) is safe — anyone else
    intercepting it can't redeem the auth code without our verifier."""
    return _last_authorize_url


def _store_or_init() -> TokenStore:
    global _store
    if _store is None:
        _store = TokenStore()
    return _store


def _cfg_or_init() -> SupabaseConfig:
    global _cfg
    if _cfg is None:
        _cfg = load_config()
    return _cfg


# ── public API ───────────────────────────────────────────────

def _supabase_error_message(resp) -> str:
    """Best-effort decode of Supabase's auth error envelopes — fields
    vary across versions (error_description / msg / error / message)."""
    try:
        body = resp.json()
        if isinstance(body, dict):
            for k in ('error_description', 'msg', 'message', 'error'):
                v = body.get(k)
                if isinstance(v, str) and v.strip():
                    return v.strip()
    except (ValueError, AttributeError):
        pass
    return f'HTTP {resp.status_code}'


def signin_with_password(email: str, password: str) -> dict:
    """Email+password sign-in. Returns the user dict on success; raises
    AuthError on any failure (invalid creds, network, etc.).

    Tokens land in the OS keyring exactly like the OAuth flow — the
    frontend can't tell which entry point was used."""
    cfg   = _cfg_or_init()
    store = _store_or_init()
    try:
        r = requests.post(
            cfg.token_url,
            params={'grant_type': 'password'},
            json={'email': email, 'password': password},
            headers={'apikey': cfg.anon_key, 'Content-Type': 'application/json'},
            timeout=15,
        )
    except requests.RequestException as e:
        raise AuthError(f'Network error: {e}') from e
    if not r.ok:
        raise AuthError(_supabase_error_message(r))

    try:
        body = r.json()
    except ValueError as e:
        raise AuthError('Sign-in returned non-JSON') from e
    stored = _store_token_from_response(cfg, store, body)
    user = _fetch_user(cfg, stored.access_token)
    # Backfill email + user_id in storage so me() works offline.
    stored = StoredToken(**{**stored.__dict__, 'email': user.email, 'user_id': user.id})
    store.save(stored)
    return user.to_dict()


def signup_with_password(email: str, password: str, full_name: str = '') -> dict:
    """Email+password registration. Returns the user dict.

    If the Supabase project has email-confirmation disabled, the response
    includes session tokens that we persist (immediate sign-in). If
    confirmation IS required, the response carries only the user object
    — we still return it so the UI can show "check your inbox", but no
    tokens are stored and the user remains signed-out locally.

    The returned dict always includes a `confirmed: bool` flag so the
    frontend can branch the UX cleanly."""
    cfg   = _cfg_or_init()
    store = _store_or_init()
    payload: dict = {'email': email, 'password': password}
    if full_name:
        # Supabase stores `data` under raw_user_meta_data; our
        # handle_new_user trigger reads full_name from there.
        payload['data'] = {'full_name': full_name}
    try:
        r = requests.post(
            cfg.url.rstrip('/') + '/auth/v1/signup',
            json=payload,
            headers={'apikey': cfg.anon_key, 'Content-Type': 'application/json'},
            timeout=15,
        )
    except requests.RequestException as e:
        raise AuthError(f'Network error: {e}') from e
    if not r.ok:
        raise AuthError(_supabase_error_message(r))

    try:
        body = r.json()
    except ValueError as e:
        raise AuthError('Sign-up returned non-JSON') from e

    if body.get('access_token'):
        # Confirmation disabled → we have a usable session immediately.
        stored = _store_token_from_response(cfg, store, body)
        user = _fetch_user(cfg, stored.access_token)
        stored = StoredToken(**{**stored.__dict__, 'email': user.email, 'user_id': user.id})
        store.save(stored)
        return {**user.to_dict(), 'confirmed': True}

    # Confirmation required → just the user object, no session.
    user_obj = body.get('user') or {}
    return {
        'id':        str(user_obj.get('id') or ''),
        'email':     str(user_obj.get('email') or email),
        'fullName':  full_name,
        'avatarUrl': '',
        'provider':  'email',
        'confirmed': False,
    }


def abort_login() -> bool:
    """Tear down any in-flight Google OAuth attempt immediately so a
    new login() call can rebind port 8085 without lag. Returns True
    iff there was an active listener to abort.

    Called from:
      • The Eel auth_abort_login bridge (user clicked "בטל וחזור").
      • The top of login() itself, defensively, so a forgotten-modal
        scenario can't leave a stale listener pinning the port."""
    global _active_listener
    with _active_listener_lock:
        srv = _active_listener
        _active_listener = None
    if srv is None:
        return False
    try:
        srv.abort()
    except Exception as e:
        log.warning('abort_login: listener.abort() raised: %s', e)
    return True


def login(timeout: float = 180.0) -> dict:
    """
    Blocking. Opens browser → loopback listener → token exchange.
    Returns the user dict (matching UserInfo.to_dict()).
    Raises AuthError on any failure (timeout, user cancel, network,
    invalid response).
    """
    try:
        cfg   = _cfg_or_init()
        store = _store_or_init()
    except AuthConfigError as e:
        raise AuthError(str(e)) from e

    # Defensive: abort any stale listener BEFORE binding the fixed
    # port. Without this, a second click on "המשך עם Google" after a
    # closed-but-not-cancelled modal would crash with EADDRINUSE.
    abort_login()

    pkce = pkce_generate()

    # Both module-level slots are reassigned inside the with-block
    # below. `global` must precede the first assignment in the
    # function body or Python silently treats them as fresh locals.
    global _active_listener, _last_authorize_url

    with LoopbackListener() as srv:
        # Register globally so abort_login() can find us. Using a lock
        # because Eel worker threads may run concurrent login attempts
        # (we just aborted any prior one above, but a parallel one
        # could land here at the same time).
        with _active_listener_lock:
            _active_listener = srv
        try:
            # IMPORTANT: redirect_to is explicitly percent-encoded via
            # quote(safe='') instead of being passed through urlencode().
            # urlencode uses quote_plus which leaves `/` as-is by default
            # in some Supabase URL-matchers — when the encoding doesn't
            # match the Redirect URLs whitelist BYTE-for-BYTE, Supabase
            # silently falls back to the Site URL (the Vercel homepage)
            # instead of completing the OAuth handshake.
            #
            # NOTE: `flow_type=pkce` is INTENTIONALLY OMITTED. It is a
            # supabase-js client-side flag, not a Supabase REST param.
            # When sent to GoTrue's /auth/v1/authorize it is ignored at
            # best and rejected at worst — in some versions GoTrue
            # silently falls back to the Site URL when it sees unknown
            # params, which is exactly the "always lands on Vercel
            # homepage" symptom we were chasing.
            # NOTE: NO `state` PARAMETER. Supabase's GoTrue acts as the
            # OAuth middleman and generates + verifies its OWN state via
            # an `sb-provider-state` cookie. Forcing a client-supplied
            # `state` here corrupts GoTrue's validation and the entire
            # flow fails with `bad_oauth_state` → Supabase redirects to
            # the Site URL with the error in the query string, which
            # presented as "always lands on the Vercel homepage". CSRF
            # protection for the loopback is still strong: only the
            # process holding the PKCE code_verifier can redeem the
            # auth_code on the token endpoint.
            encoded_redirect = quote(srv.redirect_uri, safe='')
            other_params = urlencode({
                'provider':              'google',
                'code_challenge':        pkce.challenge,
                'code_challenge_method': pkce.method,
                # Force Google's account chooser on every sign-in.
                # Without this, persistent Google cookies in the OS
                # default browser auto-complete the OAuth flow the
                # instant the user re-clicks "המשך עם Google" after
                # signing out — they get logged straight back into
                # the same account with no chance to pick another.
                # Supabase passes recognised OIDC params (prompt,
                # login_hint, etc.) straight through to the upstream
                # provider, so adding it here is enough.
                'prompt':                'select_account',
            })
            authorize_url = (
                cfg.authorize_url
                + '?redirect_to=' + encoded_redirect
                + '&' + other_params
            )

            # Expose to the frontend BEFORE opening the browser so the
            # AuthModal's "copy link" button has something to hand back
            # the instant the user clicks it. Plain assignment is fine —
            # we never read this concurrently from the worker thread
            # that's about to block in await_code(). The `global`
            # declaration lives at the top of login() because Python
            # requires it before the first assignment in the function
            # body; otherwise the finally-block assignment below
            # triggers SyntaxError.
            _last_authorize_url = authorize_url

            # Drop the exact URL into a sidecar file so the user can
            # paste it into a browser to verify it's what they think
            # AND compare against Supabase's Redirect URLs whitelist
            # without having to attach a debugger. The launcher is
            # windowed (no console), so logging alone is invisible.
            try:
                from pathlib import Path as _P
                dbg = _P.home() / '.translation_manager' / 'last_auth_url.txt'
                dbg.parent.mkdir(parents=True, exist_ok=True)
                dbg.write_text(
                    'AUTHORIZE URL (opened in browser):\n'
                    + authorize_url
                    + '\n\nLOOPBACK redirect_uri (must be in Supabase Redirect URLs):\n'
                    + srv.redirect_uri + '\n',
                    encoding='utf-8',
                )
            except Exception:
                pass

            log.info('Opening browser to %s (loopback: %s)', cfg.authorize_url, srv.redirect_uri)
            opened = webbrowser.open(authorize_url, new=2)
            if not opened:
                # Fall back to printing — even on Windows this is unusual.
                log.warning('webbrowser.open returned False. Manual URL: %s', authorize_url)

            _debug_step('awaiting callback')
            cb = srv.await_code(timeout=timeout)
            _debug_step(f'callback received (code={"yes" if cb.code else "no"}, '
                        f'error={cb.error!r})')
            if cb.error or not cb.code:
                raise AuthError(cb.error_description or cb.error or 'Sign-in did not complete')

            # Exchange the auth code for tokens (PKCE: no client secret).
            # Each step gets its own try/except so a failure surfaces
            # as a clear AuthError instead of an opaque "unexpected"
            # crash in the Eel worker (which would leave the UI stuck
            # on the spinner forever).
            _debug_step('exchanging PKCE code for tokens')
            try:
                token_payload = _exchange_pkce(cfg, cb.code, pkce.verifier)
            except AuthError:
                raise
            except Exception as e:
                raise AuthError(f'Token exchange failed: {e}') from e

            _debug_step('storing initial tokens (keyring + encrypted file)')
            try:
                stored = _store_token_from_response(cfg, store, token_payload)
            except AuthError:
                raise
            except Exception as e:
                raise AuthError(f'Saving session failed: {e}') from e
        finally:
            # Deregister even on error — otherwise a stale reference
            # would point at a closed server.
            with _active_listener_lock:
                if _active_listener is srv:
                    _active_listener = None
            # Drop the cached authorize URL too — if the copy-link
            # button is clicked AFTER the modal closes, returning the
            # URL of a now-dead listener would just confuse the user.
            _last_authorize_url = None

    _debug_step('fetching user profile from /auth/v1/user')
    try:
        user = _fetch_user(cfg, stored.access_token)
    except AuthError:
        raise
    except Exception as e:
        raise AuthError(f'Fetching user profile failed: {e}') from e

    # Backfill email + user_id so me() can answer offline. NON-FATAL:
    # if this second keyring/disk write fails for any reason (Windows
    # Credential Manager flake, transient OSError, etc.) we still have
    # a fully valid in-memory session and the initial save above
    # already persisted the tokens. Returning success here means the
    # user is signed in for THIS session even if me() has to do a
    # network roundtrip next launch. Raising would mean a successful
    # OAuth flow that the UI reports as a failure — exactly the
    # "stuck spinner / silent failure" bug we're fixing.
    _debug_step('backfilling email/user_id in session (non-fatal)')
    try:
        stored = StoredToken(**{**stored.__dict__, 'email': user.email, 'user_id': user.id})
        store.save(stored)
    except Exception as e:
        log.warning('Non-fatal: could not backfill user info in session: %s', e)
        _debug_step(f'backfill save failed (non-fatal): {e}')

    _debug_step('login() complete — returning user dict')
    return user.to_dict()


def me() -> Optional[dict]:
    """Return the cached user or None if signed out."""
    try:
        cfg   = _cfg_or_init()
        store = _store_or_init()
    except AuthConfigError:
        return None

    tok = store.load()
    if not tok or not tok.refresh_token:
        return None

    # Refresh if the access token is about to expire.
    if tok.is_expired():
        try:
            tok = _refresh(cfg, store, tok)
        except AuthError:
            log.warning('Refresh failed, signing out.')
            store.clear()
            return None

    try:
        user = _fetch_user(cfg, tok.access_token)
        return user.to_dict()
    except AuthError:
        # Could be a revoked / expired session — wipe and report signed-out
        # rather than leaving the UI stuck on a stale identity.
        store.clear()
        return None


def logout() -> None:
    """Local sign-out only — does not call Supabase's /logout endpoint."""
    try:
        store = _store_or_init()
    except AuthConfigError:
        return
    store.clear()


def owns_game(game_id: str) -> bool:
    """
    DRM check. Returns True iff the signed-in user has an active
    'completed' purchase for `game_id`. False if signed out, no
    purchase, or any error (fail-closed — DRM should never grant
    access on its own bugs).
    """
    try:
        cfg   = _cfg_or_init()
        store = _store_or_init()
    except AuthConfigError:
        return False

    tok = store.load()
    if not tok:
        return False
    if tok.is_expired():
        try:
            tok = _refresh(cfg, store, tok)
        except AuthError:
            return False

    # RLS makes this a one-row, user-scoped query: we ask for any
    # 'completed' row for the given game; absence ⇒ no ownership.
    url = cfg.rest_url + '/user_purchases'
    # Pull more columns so the debug log can show WHICH row matched
    # (`provider` reveals admin-grant vs paypal, `completed_at` lets us
    # eyeball whether it's a test grant from earlier development).
    try:
        r = requests.get(
            url,
            params={
                'select':  'id,provider,completed_at',
                'game_id': f'eq.{game_id}',
                'status':  'eq.completed',
                'limit':   '1',
            },
            headers={
                'apikey':        cfg.anon_key,
                'Authorization': f'Bearer {tok.access_token}',
                'Accept':        'application/json',
            },
            timeout=8,
        )
    except requests.RequestException as e:
        log.warning('owns_game network error: %s', e)
        return False
    if not r.ok:
        log.warning('owns_game(%s) HTTP %d for user %s: %s',
                    game_id, r.status_code, getattr(tok, 'user_id', '?'),
                    r.text[:200])
        return False
    try:
        rows = r.json()
    except ValueError:
        return False
    if not isinstance(rows, list):
        return False
    if rows:
        row = rows[0]
        log.info("owns_game(%s) → True for user %s · row id=%s provider=%s completed_at=%s",
                 game_id, getattr(tok, 'user_id', '?'),
                 row.get('id'), row.get('provider'), row.get('completed_at'))
        return True
    log.info("owns_game(%s) → False for user %s · no completed row",
             game_id, getattr(tok, 'user_id', '?'))
    return False


def _authed_token() -> Optional[tuple]:
    """Return (cfg, access_token) for the current user, refreshing if
    needed. Returns None when no session is available — every caller
    should treat that as "signed out, return an empty list / false"."""
    try:
        cfg   = _cfg_or_init()
        store = _store_or_init()
    except AuthConfigError:
        return None
    tok = store.load()
    if not tok:
        return None
    if tok.is_expired():
        try:
            tok = _refresh(cfg, store, tok)
        except AuthError:
            return None
    return (cfg, tok.access_token)


def get_access_token() -> Optional[str]:
    """Public accessor for the current Supabase access token. Refreshes
    on expiry. Returns None when signed out.

    Exposed to the launcher's React frontend so the in-launcher PayPal
    Smart Buttons can authenticate against /api/paypal?action=create-order
    / capture-order. The token is short-lived (1h) and scoped to the
    signed-in user — same posture as the website's BuyButton."""
    pair = _authed_token()
    return pair[1] if pair else None


def get_purchases() -> dict:
    """All 'completed' user_purchases rows for the current user, with
    the joined game catalog row inlined via PostgREST resource embedding.

    Returns a discriminated dict so the launcher's personal area can
    distinguish "empty list" from "signed out" from "network error" —
    fail-closed used to mask everything as `[]`, which makes the empty
    state ambiguous (no purchases? wrong account? token expired?).

    Shape: {"rows": list[dict], "reason": str, "detail": str|None}
    reason ∈ {"signed-out", "ok", "error"}.
    """
    a = _authed_token()
    if a is None:
        return {"rows": [], "reason": "signed-out", "detail": None}
    cfg, access = a
    url = cfg.rest_url + '/user_purchases'
    try:
        r = requests.get(
            url,
            params={
                # `created_at:purchased_at` is a PostgREST column alias —
                # the table column is `purchased_at` (default now() on the
                # initial pending row), but the JS shape keeps `created_at`
                # so we don't churn the frontend MyPurchase interface.
                'select': 'id,game_id,status,created_at:purchased_at,games(id,title_en,title_he,cover_url,version,version_label,download_url,price_cents)',
                'status': 'eq.completed',
                'order':  'purchased_at.desc',
            },
            headers={
                'apikey':        cfg.anon_key,
                'Authorization': f'Bearer {access}',
                'Accept':        'application/json',
            },
            timeout=8,
        )
    except requests.RequestException as e:
        log.warning('get_purchases network error: %s', e)
        return {"rows": [], "reason": "error", "detail": f"network: {e}"}
    if not r.ok:
        log.warning('get_purchases HTTP %d: %s', r.status_code, r.text[:200])
        return {"rows": [], "reason": "error",
                "detail": f"HTTP {r.status_code}: {r.text[:160]}"}
    try:
        rows = r.json()
    except ValueError as e:
        return {"rows": [], "reason": "error", "detail": f"bad-json: {e}"}
    return {"rows": rows if isinstance(rows, list) else [], "reason": "ok",
            "detail": None}


def get_votes() -> list[str]:
    """List of game_ids the current user has voted for. Empty list
    when signed out."""
    a = _authed_token()
    if a is None:
        return []
    cfg, access = a
    url = cfg.rest_url + '/votes'
    try:
        r = requests.get(
            url,
            params={
                'select': 'game_id',
                'order':  'created_at.desc',
            },
            headers={
                'apikey':        cfg.anon_key,
                'Authorization': f'Bearer {access}',
                'Accept':        'application/json',
            },
            timeout=8,
        )
    except requests.RequestException as e:
        log.warning('get_votes network error: %s', e)
        return []
    if not r.ok:
        log.warning('get_votes HTTP %d: %s', r.status_code, r.text[:200])
        return []
    try:
        rows = r.json()
    except ValueError:
        return []
    if not isinstance(rows, list):
        return []
    return [str(row.get('game_id')) for row in rows if row.get('game_id')]


# ── internals ─────────────────────────────────────────────────

def _exchange_pkce(cfg: SupabaseConfig, code: str, verifier: str) -> dict:
    """POST /auth/v1/token?grant_type=pkce with the auth code + verifier."""
    try:
        r = requests.post(
            cfg.token_url,
            params={'grant_type': 'pkce'},
            json={'auth_code': code, 'code_verifier': verifier},
            headers={'apikey': cfg.anon_key, 'Content-Type': 'application/json'},
            timeout=15,
        )
    except requests.RequestException as e:
        raise AuthError(f'Token exchange network error: {e}') from e
    if not r.ok:
        raise AuthError(f'Token exchange failed: HTTP {r.status_code} {r.text[:300]}')
    try:
        return r.json()
    except ValueError as e:
        raise AuthError('Token exchange returned non-JSON') from e


def _refresh(cfg: SupabaseConfig, store: TokenStore, tok: StoredToken) -> StoredToken:
    """Trade refresh_token for a new access_token."""
    try:
        r = requests.post(
            cfg.token_url,
            params={'grant_type': 'refresh_token'},
            json={'refresh_token': tok.refresh_token},
            headers={'apikey': cfg.anon_key, 'Content-Type': 'application/json'},
            timeout=15,
        )
    except requests.RequestException as e:
        raise AuthError(f'Refresh network error: {e}') from e
    if not r.ok:
        raise AuthError(f'Refresh failed: HTTP {r.status_code}')
    return _store_token_from_response(cfg, store, r.json())


def _store_token_from_response(cfg: SupabaseConfig, store: TokenStore, body: dict) -> StoredToken:
    access  = body.get('access_token')
    refresh = body.get('refresh_token')
    if not access or not refresh:
        raise AuthError('Token response missing access_token / refresh_token')
    expires_in = int(body.get('expires_in') or 3600)
    user = body.get('user') or {}
    tok = StoredToken(
        access_token  = access,
        refresh_token = refresh,
        expires_at    = int(time.time()) + expires_in,
        user_id       = str(user.get('id') or ''),
        email         = str(user.get('email') or ''),
    )
    store.save(tok)
    return tok


def _fetch_user(cfg: SupabaseConfig, access_token: str) -> UserInfo:
    """GET /auth/v1/user — returns Supabase's canonical user object."""
    try:
        r = requests.get(
            cfg.user_url,
            headers={
                'apikey':        cfg.anon_key,
                'Authorization': f'Bearer {access_token}',
                'Accept':        'application/json',
            },
            timeout=8,
        )
    except requests.RequestException as e:
        raise AuthError(f'/user network error: {e}') from e
    if not r.ok:
        raise AuthError(f'/user HTTP {r.status_code}: {r.text[:200]}')
    try:
        data = r.json()
    except ValueError as e:
        raise AuthError('/user returned non-JSON') from e

    meta = data.get('user_metadata') or {}
    app  = data.get('app_metadata')  or {}
    return UserInfo(
        id         = str(data.get('id') or ''),
        email      = str(data.get('email') or ''),
        full_name  = str(meta.get('full_name') or meta.get('name') or ''),
        avatar_url = str(meta.get('avatar_url') or meta.get('picture') or ''),
        provider   = str(app.get('provider') or 'email'),
    )
