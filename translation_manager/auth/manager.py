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
API directly - everything else goes through these four functions.
"""
from __future__ import annotations

import json
import logging
import sys
import threading
import time
import uuid
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
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
    is blocked. Best-effort - never raises. Millisecond resolution so a
    'browser opens but with a big delay' report can be pinpointed."""
    try:
        from pathlib import Path as _P
        p = _P.home() / '.translation_manager' / 'auth_debug.log'
        p.parent.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y-%m-%d %H:%M:%S") + f'.{int((time.time() % 1) * 1000):03d}'
        with open(p, 'a', encoding='utf-8') as fh:
            fh.write(f'{ts}  {label}\n')
    except Exception:
        pass


def _open_browser(url: str) -> str:
    """Open the system browser to `url` as ROBUSTLY as possible on Windows,
    trying the most reliable method first. Returns the name of the method that
    succeeded ('' if all failed).

    `os.startfile` is the canonical Windows URL opener and returns immediately
    (the browser renders async) even in a frozen, console-less PyInstaller
    build - where `webbrowser`'s controller probing can misbehave / be slow.
    Each method is timestamped via _debug_step so a 'browser opens but with a
    big delay' report shows whether the delay is in our open call (it isn't -
    startfile returns in ms) or the browser's own cold-start (nothing we can
    do about that)."""
    # 1) os.startfile - Windows shell "open" verb; instant, most reliable.
    try:
        import os
        if hasattr(os, 'startfile'):
            os.startfile(url)                                 # type: ignore[attr-defined]
            _debug_step('browser: os.startfile returned')
            return 'startfile'
    except Exception as e:
        _debug_step(f'browser: os.startfile failed: {e}')
    # 2) webbrowser - the portable fallback.
    try:
        if webbrowser.open(url, new=2):
            _debug_step('browser: webbrowser.open OK')
            return 'webbrowser'
        _debug_step('browser: webbrowser.open returned False')
    except Exception as e:
        _debug_step(f'browser: webbrowser.open failed: {e}')
    # 3) ShellExecuteW - last-resort native shell open.
    try:
        import ctypes
        r = ctypes.windll.shell32.ShellExecuteW(None, 'open', url, None, None, 1)   # type: ignore[attr-defined]
        if int(r) > 32:
            _debug_step('browser: ShellExecuteW OK')
            return 'shellexecute'
        _debug_step(f'browser: ShellExecuteW returned {r}')
    except Exception as e:
        _debug_step(f'browser: ShellExecuteW failed: {e}')
    return ''


def _clipboard_set(text: str) -> bool:
    """Best-effort write to the Windows clipboard via raw Win32 (ctypes), with
    an OpenClipboard retry (Qt/other apps briefly hold the clipboard). No Qt
    dependency - safe to call from login()'s worker thread. Never raises.

    Used to auto-copy the authorize URL the instant login starts, so the user
    can paste it into the browser/profile of their choice WITHOUT racing the
    copy button or the login timeout (which clears the cached URL)."""
    if sys.platform != 'win32':
        return False
    try:
        import ctypes
        from ctypes import wintypes
        CF_UNICODETEXT = 13
        GMEM_MOVEABLE  = 0x0002
        k32 = ctypes.windll.kernel32
        u32 = ctypes.windll.user32
        k32.GlobalAlloc.argtypes  = [wintypes.UINT, ctypes.c_size_t]
        k32.GlobalAlloc.restype   = wintypes.HGLOBAL
        k32.GlobalLock.argtypes   = [wintypes.HGLOBAL]
        k32.GlobalLock.restype    = wintypes.LPVOID
        k32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
        k32.GlobalFree.argtypes   = [wintypes.HGLOBAL]
        k32.GlobalFree.restype    = wintypes.HGLOBAL
        u32.OpenClipboard.argtypes    = [wintypes.HWND]
        u32.OpenClipboard.restype     = wintypes.BOOL
        u32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
        u32.SetClipboardData.restype  = wintypes.HANDLE
        data = (text or '').encode('utf-16-le') + b'\x00\x00'
        opened = False
        for _ in range(20):
            if u32.OpenClipboard(None):
                opened = True
                break
            time.sleep(0.01)
        if not opened:
            return False
        try:
            u32.EmptyClipboard()
            h = k32.GlobalAlloc(GMEM_MOVEABLE, len(data))
            if not h:
                return False
            ptr = k32.GlobalLock(h)
            if not ptr:
                k32.GlobalFree(h)
                return False
            ctypes.memmove(ptr, data, len(data))
            k32.GlobalUnlock(h)
            if not u32.SetClipboardData(CF_UNICODETEXT, h):
                k32.GlobalFree(h)
                return False
            return True
        finally:
            u32.CloseClipboard()
    except Exception:
        return False


class AuthError(RuntimeError):
    """Any sign-in / refresh / API failure surfaced to the UI."""


class AuthNetworkError(AuthError):
    """A TRANSIENT auth failure - network down, timeout, or a 5xx/429 from
    Supabase. The session is still valid; the caller should KEEP it and retry
    later, NOT sign the user out. (A definitive failure - a revoked refresh
    token, a 401/403 - is a plain AuthError and DOES clear the session.)

    This split is the fix for "after a while I'm logged out and have to sign
    in again": a single network blip while the access token was expired used
    to wipe the whole session permanently."""


# Serializes token refreshes across Eel/Qt worker threads. Supabase rotates
# the refresh token on every refresh; two concurrent refreshes would make the
# second present an already-consumed token → 400 → false logout. The lock +
# a re-load-after-acquire (in _refresh_locked) means only one refresh runs and
# the loser just picks up the freshly-stored token.
_refresh_lock = threading.Lock()

# Last successfully-fetched user profile, cached to disk so me() can answer
# with a full identity (name + avatar) while OFFLINE / during a transient
# Supabase outage instead of returning a stripped-down or empty user.
_USER_CACHE_FILE = Path.home() / '.translation_manager' / 'user_cache.json'


def _save_user_cache(user: dict) -> None:
    try:
        _USER_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _USER_CACHE_FILE.write_text(json.dumps(user, ensure_ascii=False),
                                    encoding='utf-8')
    except OSError:
        pass


def _load_user_cache() -> Optional[dict]:
    try:
        data = json.loads(_USER_CACHE_FILE.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) and data.get('id') else None
    except (OSError, ValueError):
        return None


def _clear_user_cache() -> None:
    try:
        _USER_CACHE_FILE.unlink()
    except OSError:
        pass


def cached_user() -> Optional[dict]:
    """The last-known signed-in identity from the on-disk cache, WITHOUT any
    network call. Cheap + safe to call on the GUI thread. Used as a fallback
    when a live me() is too slow (so a slow network never crashes / signs out
    the launcher). Returns None if signed out / no cache."""
    return _load_user_cache()


def _cached_user_dict(tok) -> Optional[dict]:
    """Best identity we can return WITHOUT a network call - the on-disk
    profile cache, else a minimal dict from the stored token. Used on a
    transient failure so the user stays signed in."""
    cached = _load_user_cache()
    if cached:
        return cached
    uid = getattr(tok, 'user_id', '') or ''
    email = getattr(tok, 'email', '') or ''
    if uid or email:
        return {'id': uid, 'email': email, 'fullName': '',
                'avatarUrl': '', 'provider': 'email'}
    return None


# ── Single-session-per-account enforcement ───────────────────────
#
# Only ONE launcher install may hold a given account at a time. On every
# successful sign-in we (1) write THIS install's stable device-id into the
# user's `profiles.active_device` (RLS-scoped self-update) and (2) ask
# Supabase to revoke every OTHER session's refresh token (`logout?scope=
# others`). A displaced install then learns it lost the account the next
# time `me()` runs: it reads `active_device` back and, if it no longer
# matches, signs out locally and drops a one-shot "takeover" marker so the
# UI can explain WHY ("you signed in from another device").
#
# The device-id is a random uuid persisted next to the session, stable for
# the lifetime of the install (survives sign-out/in - it identifies the
# MACHINE, not the session).
_DEVICE_ID_FILE = Path.home() / '.translation_manager' / 'device_id'
_TAKEOVER_FLAG  = Path.home() / '.translation_manager' / 'session_takeover.flag'


_device_id_cache: str = ""


def _device_id() -> str:
    """Stable per-install id. Created once, then reused forever.

    CRITICAL: if the id file can be neither read (empty/corrupt/unreadable) NOR
    written (read-only file / unwritable home), we MUST NOT return a fresh uuid
    on every call - the single-session check compares this against the DB-stamped
    value, so a per-call-random id makes every poll look like a takeover and
    force-logs-the-user-out ~60s after each sign-in. Cache the generated id in a
    process global so it stays stable for the session even when it can't persist."""
    global _device_id_cache
    if _device_id_cache:
        return _device_id_cache
    try:
        existing = _DEVICE_ID_FILE.read_text(encoding='utf-8').strip()
        if existing:
            _device_id_cache = existing
            return existing
    except OSError:
        pass
    new_id = uuid.uuid4().hex
    try:
        _DEVICE_ID_FILE.parent.mkdir(parents=True, exist_ok=True)
        _DEVICE_ID_FILE.write_text(new_id, encoding='utf-8')
    except OSError:
        pass
    _device_id_cache = new_id          # stable for the session even if unpersisted
    return new_id


def device_id() -> str:
    """Public stable per-install id (random uuid, no PII). Used for anonymous
    active-install counting via the launcher feed (and single-session)."""
    return _device_id()


def _set_takeover_flag() -> None:
    try:
        _TAKEOVER_FLAG.parent.mkdir(parents=True, exist_ok=True)
        _TAKEOVER_FLAG.write_text(str(int(time.time())), encoding='utf-8')
    except OSError:
        pass


def _clear_takeover_flag() -> None:
    try:
        _TAKEOVER_FLAG.unlink()
    except OSError:
        pass


def consume_takeover() -> bool:
    """One-shot read: True iff this install was displaced by another device
    since the last check, then clears the marker. The UI calls this after
    me() returns None to decide whether to show the 'signed in elsewhere'
    notice rather than a plain sign-out."""
    if not _TAKEOVER_FLAG.exists():
        return False
    _clear_takeover_flag()
    return True


def _profiles_url(cfg: SupabaseConfig) -> str:
    return cfg.rest_url + '/profiles'


def _claim_device(cfg: SupabaseConfig, access: str, uid: str) -> None:
    """Mark THIS install as the account's active device (best-effort -
    never raises; a failure just means enforcement is delayed to the next
    successful claim/check)."""
    if not uid:
        return
    try:
        requests.patch(
            _profiles_url(cfg) + f'?id=eq.{uid}',
            json={'active_device':    _device_id(),
                  'active_device_at': datetime.now(timezone.utc).isoformat()},
            headers={'apikey':        cfg.anon_key,
                     'Authorization': f'Bearer {access}',
                     'Content-Type':  'application/json',
                     'Prefer':        'return=minimal'},
            timeout=8,
        )
    except requests.RequestException as e:
        log.warning('claim_device failed (non-fatal): %s', e)


def _claim_device_if_free(cfg: SupabaseConfig, access: str, uid: str) -> bool | None:
    """Compare-and-swap: claim the active-device slot ONLY IF it is still NULL.

    Returns True  = WE won the empty slot,
            False = the request SUCCEEDED but 0 rows matched (someone else claimed
                    it first - a genuine lost race → the caller treats it as 'taken'),
            None  = the request could NOT be evaluated (network error / non-2xx /
                    bad body). This is TRANSIENT and MUST NOT be conflated with a
                    lost race - the caller maps None → 'unknown' so a passing
                    network blip never signs the user out ("signed in elsewhere").
    Prevents the TOCTOU where two simultaneous first-logins of one account both
    read NULL and both believe they own it (which silently defeats single-session).
    """
    if not uid:
        return None
    try:
        r = requests.patch(
            _profiles_url(cfg) + f'?id=eq.{uid}&active_device=is.null',
            json={'active_device':    _device_id(),
                  'active_device_at': datetime.now(timezone.utc).isoformat()},
            headers={'apikey':        cfg.anon_key,
                     'Authorization': f'Bearer {access}',
                     'Content-Type':  'application/json',
                     'Prefer':        'return=representation'},
            timeout=8,
        )
    except requests.RequestException as e:
        log.warning('claim_device_if_free failed (transient, non-fatal): %s', e)
        return None
    if not r.ok:
        return None
    try:
        rows = r.json()
    except ValueError:
        return None
    # A row is returned ONLY if our conditional (active_device IS NULL) matched
    # → we won the empty slot. 0 rows → someone else claimed it first (real loss).
    return isinstance(rows, list) and len(rows) > 0


def _register_active_session(cfg: SupabaseConfig, access: str, uid: str) -> None:
    """Run on every successful sign-in: take ownership of the account for THIS
    install by stamping our device-id into profiles.active_device. Any other
    install learns it was displaced on its next me() poll (reads a different
    active_device → signs out). Clears a stale takeover marker so a deliberate
    re-login doesn't surface the 'signed in elsewhere' notice.

    NOTE: deliberately does NOT call Supabase /logout?scope=others. On an older
    GoTrue an unrecognised scope can fall back to scope=global and revoke the
    CURRENT (just-created) session too - the exact false-logout class we're
    avoiding. The active_device claim + the 60 s client poll enforce
    single-session safely without touching the server's session table."""
    _clear_takeover_flag()
    _claim_device(cfg, access, uid)


def _device_owner_status(cfg: SupabaseConfig, access: str, uid: str) -> str:
    """'mine' | 'taken' | 'unknown'. Reads profiles.active_device for the
    current user. An unclaimed row (NULL - a pre-feature session or a fresh
    account) is CLAIMED on the spot and reported 'mine'. Any read failure is
    'unknown' so a transient network error NEVER signs the user out."""
    if not uid:
        return 'unknown'
    try:
        r = requests.get(
            _profiles_url(cfg),
            params={'id': f'eq.{uid}', 'select': 'active_device', 'limit': '1'},
            headers={'apikey':        cfg.anon_key,
                     'Authorization': f'Bearer {access}',
                     'Accept':        'application/json'},
            timeout=8,
        )
    except requests.RequestException:
        return 'unknown'
    if not r.ok:
        return 'unknown'
    try:
        rows = r.json()
    except ValueError:
        return 'unknown'
    if not isinstance(rows, list) or not rows:
        return 'unknown'
    current = str(rows[0].get('active_device') or '').strip()
    if not current:
        # CAS-claim the empty slot. WON → 'mine'. Genuinely LOST the race (another
        # install claimed between our read and our write) → 'taken'. But a
        # TRANSIENT claim failure (network blip / non-2xx) returns None and MUST
        # map to 'unknown' - NOT 'taken' - so a passing glitch never wrongly signs
        # the user out with "signed in elsewhere" (the documented no-sign-out rule).
        won = _claim_device_if_free(cfg, access, uid)
        if won is None:
            return 'unknown'
        return 'mine' if won else 'taken'
    return 'mine' if current == _device_id() else 'taken'


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


# Lazy singletons - created on first use so the auth subsystem doesn't
# load anything (or raise AuthConfigError) until someone actually
# tries to authenticate.
_store: Optional[TokenStore] = None
_cfg:   Optional[SupabaseConfig] = None

# Tracks the LoopbackListener for the currently-active Google OAuth
# attempt so abort_login() can shut it down from another thread. Eel
# runs each exposed function on a worker thread, so reads + writes are
# concurrent - guarded by a Lock. Lock-then-take pattern below: the
# aborter swaps the global to None while holding the lock, then calls
# .abort() outside the lock (abort can call .shutdown() which blocks
# briefly; we don't want to hold the lock during that).
_active_listener:      Optional[LoopbackListener] = None
_active_listener_lock                              = threading.Lock()

# Last-built authorize URL - exposed to the frontend via the
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
    user (who pastes it into another browser) is safe - anyone else
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
    """Best-effort decode of Supabase's auth error envelopes - fields
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


# ── Two-factor (MFA / TOTP) - enforced at LOGIN, matching the website ──
#
# GoTrue does NOT block a password / OAuth sign-in when the account has an
# enrolled TOTP factor: it hands back an aal1 session and expects the CLIENT
# to force the second factor before treating the user as "logged in". The
# website does exactly this (LoginPage / AuthCallbackPage / ProtectedRoute
# render an MfaChallenge while the session is aal1). The launcher used to skip
# it entirely - a factor-enrolled account signed straight in with the password
# alone. This closes that gap: after the credential step we detect a verified
# TOTP factor, open a challenge, and require the 6-digit code (which upgrades
# the session to aal2) BEFORE any token is persisted to the keyring.
#
# The aal1 token that authorizes the challenge/verify calls is held in memory
# ONLY (never written to disk) between the two steps - an unverified session
# must never survive as a usable login.

@dataclass
class _PendingMfa:
    access_token:  str   # aal1 token - authorizes the challenge/verify calls
    refresh_token: str   # aal1 refresh - discarded once we hold the aal2 session
    factor_id:     str
    challenge_id:  str
    user_id:       str
    email:         str


_pending_mfa:      Optional[_PendingMfa] = None
_pending_mfa_lock                        = threading.Lock()


def _set_pending_mfa(access: str, refresh: str, factor_id: str,
                     challenge_id: str, uid: str, email: str) -> None:
    global _pending_mfa
    with _pending_mfa_lock:
        _pending_mfa = _PendingMfa(access, refresh, factor_id, challenge_id, uid, email)


def _clear_pending_mfa() -> None:
    global _pending_mfa
    with _pending_mfa_lock:
        _pending_mfa = None


def mfa_pending() -> bool:
    with _pending_mfa_lock:
        return _pending_mfa is not None


def cancel_mfa() -> None:
    """Drop a pending TOTP challenge (user backed out of the code screen).
    The in-memory aal1 session is discarded - nothing was persisted."""
    _clear_pending_mfa()


def _verified_totp_factor_id(cfg: SupabaseConfig, access_token: str) -> Optional[str]:
    """Return the id of a VERIFIED TOTP factor on this account, else None.

    GET /auth/v1/user carries a `factors` array when the account enrolled any.
    On ANY error we return None (→ treat as 'no MFA'): detection fails OPEN,
    exactly like the website (AuthContext.fetchMfa returns EMPTY_MFA on error).
    This is an honest-client gate - the true server-enforced factor is the
    admin API's aal2 requirement; a transient blip must never lock a
    factor-less user out of the launcher."""
    try:
        r = requests.get(
            cfg.user_url,
            headers={'apikey':        cfg.anon_key,
                     'Authorization': f'Bearer {access_token}',
                     'Accept':        'application/json'},
            timeout=8,
        )
    except requests.RequestException:
        return None
    if not r.ok:
        return None
    try:
        data = r.json()
    except ValueError:
        return None
    for f in (data.get('factors') or []):
        if str(f.get('factor_type')) == 'totp' and str(f.get('status')) == 'verified':
            fid = str(f.get('id') or '')
            if fid:
                return fid
    return None


def _mfa_challenge(cfg: SupabaseConfig, access_token: str, factor_id: str) -> str:
    """POST /auth/v1/factors/{id}/challenge → returns the challenge id."""
    try:
        r = requests.post(
            cfg.url.rstrip('/') + f'/auth/v1/factors/{factor_id}/challenge',
            headers={'apikey':        cfg.anon_key,
                     'Authorization': f'Bearer {access_token}',
                     'Content-Type':  'application/json'},
            timeout=10,
        )
    except requests.RequestException as e:
        raise AuthNetworkError(f'MFA challenge network error: {e}') from e
    if not r.ok:
        raise AuthError(_supabase_error_message(r))
    try:
        cid = str((r.json() or {}).get('id') or '')
    except ValueError:
        cid = ''
    if not cid:
        raise AuthError('MFA challenge returned no id')
    return cid


def _mfa_verify_request(cfg: SupabaseConfig, access_token: str, factor_id: str,
                        challenge_id: str, code: str) -> dict:
    """POST /auth/v1/factors/{id}/verify with the 6-digit code. On success
    GoTrue returns a NEW session at aal2 (access_token + refresh_token)."""
    try:
        r = requests.post(
            cfg.url.rstrip('/') + f'/auth/v1/factors/{factor_id}/verify',
            json={'challenge_id': challenge_id, 'code': code},
            headers={'apikey':        cfg.anon_key,
                     'Authorization': f'Bearer {access_token}',
                     'Content-Type':  'application/json'},
            timeout=15,
        )
    except requests.RequestException as e:
        raise AuthNetworkError(f'MFA verify network error: {e}') from e
    if not r.ok:
        raise AuthError(_supabase_error_message(r))
    try:
        return r.json()
    except ValueError as e:
        raise AuthError('MFA verify returned non-JSON') from e


def _begin_mfa_or_none(cfg: SupabaseConfig, body: dict,
                       fallback_email: str = '') -> Optional[dict]:
    """Given a fresh aal1 session `body` (password grant OR PKCE exchange),
    check for a verified TOTP factor. If present: open a challenge, stash the
    pending state IN MEMORY (nothing persisted), and return the frontend
    hand-off dict {mfaRequired, factorId, email}. Returns None when the account
    has no MFA - the caller then completes the normal (persisted) login."""
    access  = str(body.get('access_token') or '')
    refresh = str(body.get('refresh_token') or '')
    if not access or not refresh:
        return None
    factor_id = _verified_totp_factor_id(cfg, access)
    if not factor_id:
        return None
    u     = body.get('user') or {}
    email = str(u.get('email') or fallback_email or '')
    uid   = str(u.get('id') or '') or _uid_from_jwt(access)
    challenge_id = _mfa_challenge(cfg, access, factor_id)
    _set_pending_mfa(access, refresh, factor_id, challenge_id, uid, email)
    return {'mfaRequired': True, 'factorId': factor_id, 'email': email}


def verify_mfa(code: str) -> dict:
    """Complete a pending TOTP login: verify the 6-digit `code`, persist the
    resulting aal2 session, and return the user dict - the SAME shape a plain
    sign-in returns. Raises AuthError on a wrong/expired code (and re-issues a
    fresh challenge so the user can immediately retry with the current code)."""
    cfg   = _cfg_or_init()
    store = _store_or_init()
    with _pending_mfa_lock:
        p = _pending_mfa
    if p is None:
        raise AuthError('אין אימות דו-שלבי ממתין. התחבר/י מחדש.')
    code = (code or '').strip().replace(' ', '').replace('-', '')
    if not code:
        raise AuthError('הזן/י את קוד האימות בן 6 הספרות.')
    try:
        body = _mfa_verify_request(cfg, p.access_token, p.factor_id, p.challenge_id, code)
    except AuthNetworkError:
        raise AuthError('שגיאת רשת באימות הקוד. נסה/י שוב.')
    except AuthError:
        # Wrong/expired code - issue a fresh challenge so a retry with the
        # current rotating code works, then surface a friendly error.
        try:
            new_ch = _mfa_challenge(cfg, p.access_token, p.factor_id)
            with _pending_mfa_lock:
                if _pending_mfa is not None:
                    _pending_mfa.challenge_id = new_ch
        except Exception:
            pass
        raise AuthError('קוד שגוי או שפג תוקפו. נסה/י שוב עם הקוד הנוכחי מהאפליקציה.')

    stored = _store_token_from_response(cfg, store, body)
    user   = _fetch_user(cfg, stored.access_token)
    stored = StoredToken(**{**stored.__dict__, 'email': user.email, 'user_id': user.id})
    store.save(stored)
    _save_user_cache(user.to_dict())
    _register_active_session(cfg, stored.access_token, user.id)
    _clear_pending_mfa()
    return user.to_dict()


def signin_with_password(email: str, password: str) -> dict:
    """Email+password sign-in. Returns the user dict on success; raises
    AuthError on any failure (invalid creds, network, etc.).

    Tokens land in the OS keyring exactly like the OAuth flow - the
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

    # Two-factor gate: if the account has a verified TOTP factor, DON'T persist
    # this aal1 session - open a challenge and require the 6-digit code first
    # (verify_mfa() finishes the login and stores the aal2 session).
    pending = _begin_mfa_or_none(cfg, body, fallback_email=email)
    if pending is not None:
        return pending

    stored = _store_token_from_response(cfg, store, body)
    user = _fetch_user(cfg, stored.access_token)
    # Backfill email + user_id in storage so me() works offline.
    stored = StoredToken(**{**stored.__dict__, 'email': user.email, 'user_id': user.id})
    store.save(stored)
    _save_user_cache(user.to_dict())
    _register_active_session(cfg, stored.access_token, user.id)
    return user.to_dict()


def signup_with_password(email: str, password: str, full_name: str = '') -> dict:
    """Email+password registration. Returns the user dict.

    If the Supabase project has email-confirmation disabled, the response
    includes session tokens that we persist (immediate sign-in). If
    confirmation IS required, the response carries only the user object
    - we still return it so the UI can show "check your inbox", but no
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
        _save_user_cache(user.to_dict())
        _register_active_session(cfg, stored.access_token, user.id)
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
        _debug_step('abort_login: no active listener (nothing to abort)')
        return False
    _debug_step('abort_login: aborting active listener')
    try:
        srv.abort()
    except Exception as e:
        log.warning('abort_login: listener.abort() raised: %s', e)
    return True


def login(timeout: float = 300.0) -> dict:
    """
    Blocking. Opens browser → loopback listener → token exchange.
    Returns the user dict (matching UserInfo.to_dict()).
    Raises AuthError on any failure (timeout, user cancel, network,
    invalid response).
    """
    _debug_step('=== login() start ===')
    try:
        from translation_manager import _build_info as _bi   # type: ignore
        _debug_step(f'build_id={getattr(_bi, "BUILD_ID", "?")} dev_build={getattr(_bi, "DEV_BUILD", "?")}')
    except Exception:
        _debug_step('build_id=unknown (no _build_info)')

    try:
        cfg   = _cfg_or_init()
        store = _store_or_init()
    except AuthConfigError as e:
        raise AuthError(str(e)) from e

    # Defensive: abort any stale listener BEFORE binding the fixed
    # port. Without this, a second click on "המשך עם Google" after a
    # closed-but-not-cancelled modal would crash with EADDRINUSE.
    _debug_step('abort_login (defensive) before bind')
    abort_login()

    pkce = pkce_generate()

    # Both module-level slots are reassigned inside the with-block
    # below. `global` must precede the first assignment in the
    # function body or Python silently treats them as fresh locals.
    global _active_listener, _last_authorize_url

    # Set inside the with-block if the account requires a TOTP second factor;
    # read after the block to short-circuit into the code screen.
    pending_mfa_result: Optional[dict] = None

    _debug_step('binding loopback listener (port 8085)')
    with LoopbackListener() as srv:
        _debug_step('loopback bound + serve thread started')
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
            # in some Supabase URL-matchers - when the encoding doesn't
            # match the Redirect URLs whitelist BYTE-for-BYTE, Supabase
            # silently falls back to the Site URL (the Vercel homepage)
            # instead of completing the OAuth handshake.
            #
            # NOTE: `flow_type=pkce` is INTENTIONALLY OMITTED. It is a
            # supabase-js client-side flag, not a Supabase REST param.
            # When sent to GoTrue's /auth/v1/authorize it is ignored at
            # best and rejected at worst - in some versions GoTrue
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
                # signing out - they get logged straight back into
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
            # the instant the user clicks it. Plain assignment is fine -
            # we never read this concurrently from the worker thread
            # that's about to block in await_code(). The `global`
            # declaration lives at the top of login() because Python
            # requires it before the first assignment in the function
            # body; otherwise the finally-block assignment below
            # triggers SyntaxError.
            _last_authorize_url = authorize_url

            # Auto-copy the authorize URL to the clipboard RIGHT NOW - while the
            # login is definitely active (loopback listener alive) - so the user
            # can paste it into the browser/profile they want without racing the
            # copy button or the timeout (which clears _last_authorize_url). This
            # is the bulletproof path: the URL is on the clipboard the instant the
            # browser opens and stays there until the user copies something else.
            try:
                if _clipboard_set(authorize_url):
                    _debug_step('authorize URL auto-copied to clipboard')
                else:
                    _debug_step('authorize URL auto-copy: clipboard write failed')
            except Exception as _e:
                _debug_step(f'authorize URL auto-copy raised: {_e}')

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
            _debug_step('opening browser NOW')
            method = _open_browser(authorize_url)
            _debug_step(f'browser open call returned (method={method or "NONE"})')
            if not method:
                log.warning('all browser-open methods failed. Manual URL: %s', authorize_url)

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

            # Two-factor gate BEFORE persisting anything: an account with a
            # verified TOTP factor must enter the 6-digit code first. When
            # pending, nothing is written to the keyring (the aal1 session is
            # held in memory) and we hand the challenge back to the UI below.
            _debug_step('checking MFA factor')
            pending_mfa_result = _begin_mfa_or_none(cfg, token_payload)
            if pending_mfa_result is None:
                _debug_step('storing initial tokens (keyring + encrypted file)')
                try:
                    stored = _store_token_from_response(cfg, store, token_payload)
                except AuthError:
                    raise
                except Exception as e:
                    raise AuthError(f'Saving session failed: {e}') from e
        finally:
            # Deregister even on error - otherwise a stale reference
            # would point at a closed server.
            with _active_listener_lock:
                if _active_listener is srv:
                    _active_listener = None
            # Drop the cached authorize URL too - if the copy-link
            # button is clicked AFTER the modal closes, returning the
            # URL of a now-dead listener would just confuse the user.
            _last_authorize_url = None

    # Account requires a second factor - hand the challenge to the UI. The aal1
    # session was NOT persisted; verify_mfa() finishes the login on the code.
    if pending_mfa_result is not None:
        _debug_step('login() → MFA required, awaiting 6-digit code')
        return pending_mfa_result

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
    # OAuth flow that the UI reports as a failure - exactly the
    # "stuck spinner / silent failure" bug we're fixing.
    _debug_step('backfilling email/user_id in session (non-fatal)')
    try:
        stored = StoredToken(**{**stored.__dict__, 'email': user.email, 'user_id': user.id})
        store.save(stored)
    except Exception as e:
        log.warning('Non-fatal: could not backfill user info in session: %s', e)
        _debug_step(f'backfill save failed (non-fatal): {e}')

    _debug_step('login() complete - returning user dict')
    _save_user_cache(user.to_dict())
    # Claim this account for THIS install + evict any other device.
    _register_active_session(cfg, stored.access_token, user.id)
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
            tok = _refresh_locked(cfg, store, tok)
        except AuthNetworkError:
            # Transient (offline / timeout / 5xx) - DON'T sign out. Keep the
            # session and answer with the last-known identity; the next call
            # retries the refresh.
            log.warning('Refresh hit a transient error; keeping session.')
            return _cached_user_dict(tok)
        except AuthError:
            # Definitive - the refresh token was revoked/invalid. Only NOW do
            # we sign the user out.
            log.warning('Refresh token rejected, signing out.')
            store.clear()
            _clear_user_cache()
            return None

    try:
        user = _fetch_user(cfg, tok.access_token)
        # Single-session gate: another launcher install may have claimed this
        # account. We're provably online here (/user just returned 200), so a
        # 'taken' verdict is DEFINITIVE - sign out + leave a one-shot marker so
        # the UI can say WHY. 'unknown' (profiles read failed) keeps the session.
        uid = user.id or getattr(tok, 'user_id', '') or _uid_from_jwt(tok.access_token)
        if _device_owner_status(cfg, tok.access_token, uid) == 'taken':
            log.warning('Account claimed by another device - signing out here.')
            _set_takeover_flag()
            store.clear()
            _clear_user_cache()
            return None
        _save_user_cache(user.to_dict())
        return user.to_dict()
    except AuthNetworkError:
        # Transient /user failure - stay signed in with the cached identity.
        log.warning('/user hit a transient error; keeping session.')
        return _cached_user_dict(tok)
    except AuthError:
        # Definitive (401/403) - the session is genuinely invalid.
        store.clear()
        _clear_user_cache()
        return None


def logout() -> None:
    """Local sign-out only - does not call Supabase's /logout endpoint."""
    try:
        store = _store_or_init()
    except AuthConfigError:
        return
    store.clear()
    _clear_user_cache()
    _clear_pending_mfa()
    # A deliberate sign-out is not a takeover - drop any stale marker so the
    # next signed-out poll doesn't surface the "signed in elsewhere" notice.
    _clear_takeover_flag()


def owns_game(game_id: str) -> bool:
    """
    DRM check. Returns True iff the signed-in user has an active
    'completed' purchase for `game_id`. False if signed out, no
    purchase, or any error (fail-closed - DRM should never grant
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
            tok = _refresh_locked(cfg, store, tok)
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
    needed. Returns None when no session is available - every caller
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
            tok = _refresh_locked(cfg, store, tok)
        except AuthError:
            return None
    return (cfg, tok.access_token)


def get_access_token() -> Optional[str]:
    """Public accessor for the current Supabase access token. Refreshes
    on expiry. Returns None when signed out.

    Exposed to the launcher's React frontend so the in-launcher PayPal
    Smart Buttons can authenticate against /api/paypal?action=create-order
    / capture-order. The token is short-lived (1h) and scoped to the
    signed-in user - same posture as the website's BuyButton."""
    pair = _authed_token()
    return pair[1] if pair else None


def get_purchases() -> dict:
    """All 'completed' user_purchases rows for the current user, with
    the joined game catalog row inlined via PostgREST resource embedding.

    Returns a discriminated dict so the launcher's personal area can
    distinguish "empty list" from "signed out" from "network error" -
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
                # `created_at:purchased_at` is a PostgREST column alias -
                # the table column is `purchased_at` (default now() on the
                # initial pending row), but the JS shape keeps `created_at`
                # so we don't churn the frontend MyPurchase interface.
                'select': 'id,game_id,status,created_at:purchased_at,games(id,title_en,title_he,cover_url,version,version_label,download_url,price_cents,is_software)',
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


def _uid_from_jwt(access: str) -> str:
    """Extract the Supabase user id (`sub` claim) from a JWT access token.
    No signature check - the token is already trusted locally; we only need
    the id. Fallback for when StoredToken.user_id wasn't backfilled."""
    try:
        import base64, json
        payload = access.split('.')[1]
        payload += '=' * (-len(payload) % 4)          # pad to a multiple of 4
        return str(json.loads(base64.urlsafe_b64decode(payload)).get('sub') or '')
    except Exception:
        return ''


def get_votes() -> list[str]:
    """List of game_ids the CURRENT user has voted for. Empty list when
    signed out.

    Reads via the HUB API (`/api/games?action=votes`) with the user's own
    access token - NOT a direct PostgREST query on `public.votes`. The
    2026-07-01 security hardening revoked the anon/authenticated SELECT GRANT
    on `votes` (to close a direct-read leak that exposed every voter's
    user_id), so a token-scoped SELECT now returns permission-denied and the
    personal area always showed "0 הצבעות" even for an account that HAD votes.
    The service-role API is the sanctioned read path: it computes `myVotes`
    (this user's game_ids) server-side from the bearer token."""
    try:
        cfg   = _cfg_or_init()
        store = _store_or_init()
    except AuthConfigError:
        return []
    tok = store.load()
    if not tok:
        return []
    if tok.is_expired():
        try:
            tok = _refresh_locked(cfg, store, tok)
        except AuthError:
            return []
    try:
        r = requests.get(
            'https://hebrew-translation-hub.com/api/games',
            params={'action': 'votes'},
            headers={
                'Accept':        'application/json',
                'Authorization': f'Bearer {tok.access_token}',
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
        data = r.json()
    except ValueError:
        return []
    votes = data.get('myVotes') if isinstance(data, dict) else None
    if not isinstance(votes, list):
        return []
    return [str(v) for v in votes if v]


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


def _refresh_locked(cfg: SupabaseConfig, store: TokenStore, tok: StoredToken) -> StoredToken:
    """Serialized refresh. Holds _refresh_lock, then RE-LOADS the token from
    the store: if another thread already refreshed it (no longer expired) we
    return that fresh token instead of burning our now-stale refresh_token on
    a second rotation (which Supabase would reject)."""
    with _refresh_lock:
        latest = store.load() or tok
        if not latest.is_expired():
            return latest
        return _refresh(cfg, store, latest)


def _refresh(cfg: SupabaseConfig, store: TokenStore, tok: StoredToken) -> StoredToken:
    """Trade refresh_token for a new access_token. Raises AuthNetworkError on a
    TRANSIENT failure (network/timeout/5xx/429 → keep the session) and plain
    AuthError on a DEFINITIVE one (revoked/invalid refresh token → sign out)."""
    try:
        r = requests.post(
            cfg.token_url,
            params={'grant_type': 'refresh_token'},
            json={'refresh_token': tok.refresh_token},
            headers={'apikey': cfg.anon_key, 'Content-Type': 'application/json'},
            timeout=15,
        )
    except requests.RequestException as e:
        raise AuthNetworkError(f'Refresh network error: {e}') from e
    if not r.ok:
        if r.status_code >= 500 or r.status_code == 429:
            raise AuthNetworkError(f'Refresh transient: HTTP {r.status_code}')
        raise AuthError(f'Refresh failed: HTTP {r.status_code}')
    try:
        body = r.json()
    except ValueError as e:
        # A non-JSON 200 (captive portal / proxy block page). Treat as TRANSIENT
        # so me() keeps the session instead of signing the user out - matches
        # the ValueError guard every sibling decoder (_exchange_pkce/_fetch_user)
        # already has.
        raise AuthNetworkError(f'Refresh response not JSON: {e}') from e
    return _store_token_from_response(cfg, store, body)


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
    try:
        store.save(tok)
    except RuntimeError as e:
        # The refresh SUCCEEDED server-side (the old refresh token is now rotated/
        # dead), but persisting failed (keyring/disk WRITE glitch). Do NOT raise:
        # the in-memory token is valid for THIS session. Raising a plain RuntimeError
        # here escapes me()'s AuthError/AuthNetworkError handlers → a sign-out, and
        # the NEXT refresh would use the dead old token → 400 invalid_grant → a
        # PERMANENT sign-out from a transient write error. Worst case now: the token
        # isn't on disk, so a later app restart re-authenticates - a graceful degrade.
        log.warning('token refreshed but could not persist the session (non-fatal): %s', e)
    return tok


def _fetch_user(cfg: SupabaseConfig, access_token: str) -> UserInfo:
    """GET /auth/v1/user - returns Supabase's canonical user object."""
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
        raise AuthNetworkError(f'/user network error: {e}') from e
    if not r.ok:
        if r.status_code >= 500 or r.status_code == 429:
            raise AuthNetworkError(f'/user transient: HTTP {r.status_code}')
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
