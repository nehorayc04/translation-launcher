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
import time
import webbrowser
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlencode

import requests

from .config import AuthConfigError, SupabaseConfig, load_config
from .loopback import LoopbackListener
from .pkce import generate as pkce_generate
from .storage import StoredToken, TokenStore

log = logging.getLogger(__name__)


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

    pkce = pkce_generate()

    with LoopbackListener() as srv:
        authorize_url = cfg.authorize_url + '?' + urlencode({
            'provider':              'google',
            'redirect_to':           srv.redirect_uri,
            'code_challenge':        pkce.challenge,
            'code_challenge_method': pkce.method,
            'flow_type':             'pkce',
            # `state` is what protects us against a stranger forging a
            # /callback hit on our loopback — the listener checks it.
            'state':                 srv.state,
        })

        log.info('Opening browser to %s (loopback: %s)', cfg.authorize_url, srv.redirect_uri)
        opened = webbrowser.open(authorize_url, new=2)
        if not opened:
            # Fall back to printing — even on Windows this is unusual.
            log.warning('webbrowser.open returned False. Manual URL: %s', authorize_url)

        cb = srv.await_code(timeout=timeout)
        if cb.error or not cb.code:
            raise AuthError(cb.error_description or cb.error or 'Sign-in did not complete')

        # Exchange the auth code for tokens (PKCE: no client secret).
        token_payload = _exchange_pkce(cfg, cb.code, pkce.verifier)
        stored = _store_token_from_response(cfg, store, token_payload)

    user = _fetch_user(cfg, stored.access_token)
    # Update the stored email/user_id once we know them — cheap, lets
    # `me()` answer without an extra round-trip when offline.
    stored = StoredToken(**{**stored.__dict__, 'email': user.email, 'user_id': user.id})
    store.save(stored)

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
    try:
        r = requests.get(
            url,
            params={
                'select':  'id',
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
        log.warning('owns_game HTTP %d: %s', r.status_code, r.text[:200])
        return False
    try:
        rows = r.json()
    except ValueError:
        return False
    return isinstance(rows, list) and len(rows) > 0


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
