"""
translation_manager.auth - Supabase OAuth (Google) + token storage
for the desktop launcher.

Public API:

    from translation_manager.auth import login, logout, me, owns_game

    login()        -> dict     # blocking, opens browser, returns user
    me()           -> dict|None # current cached user (None if signed out)
    logout()       -> None
    owns_game(id)  -> bool      # quick DRM check against user_purchases

Internals live in the sibling modules:

    config.py    - Supabase project URL + anon key (env-driven)
    pkce.py      - RFC 7636 PKCE verifier + challenge
    loopback.py  - one-shot http.server on 127.0.0.1 for the OAuth callback
    storage.py   - keyring-backed token store
    manager.py   - orchestration

We deliberately keep the OAuth flow in stdlib (http.server + requests +
webbrowser) so PyInstaller doesn't have to bundle aiohttp / authlib.
"""
from .manager import (
    login, logout, me, owns_game, abort_login,
    get_last_authorize_url,
    signin_with_password, signup_with_password,
    # Two-factor (TOTP) + single-session takeover. These are called as
    # `_auth.verify_mfa(...)` / `_auth.cancel_mfa()` / `_auth.consume_takeover()`
    # from main_eel - WITHOUT re-exporting them here the launcher's 2FA code
    # screen died with "module 'translation_manager.auth' has no attribute
    # 'verify_mfa'" and the takeover notice never fired.
    verify_mfa, cancel_mfa, mfa_pending, consume_takeover,
    get_purchases, get_votes,
    get_access_token, device_id,
    cached_user,
    AuthError,
)

__all__ = [
    'login', 'logout', 'me', 'owns_game', 'abort_login',
    'get_last_authorize_url',
    'signin_with_password', 'signup_with_password',
    'verify_mfa', 'cancel_mfa', 'mfa_pending', 'consume_takeover',
    # Used by main_eel.auth_get_my_purchases / auth_get_my_votes - the
    # personal area showed empty FOREVER without these in __all__:
    # `_auth.get_purchases()` raised AttributeError, the outer try/except
    # caught it, and the function returned `[]` like a clean empty list.
    'get_purchases', 'get_votes',
    # Last-known identity from the on-disk cache (no network) - the bridge's
    # auth_me falls back to this when a live me() is too slow, so a slow
    # network never crashes/signs-out the launcher.
    'cached_user',
    # get_access_token surfaces the current Supabase JWT so the
    # launcher's React-side PayPal SDK can call /api/paypal create-order
    # and capture-order. Same security posture as the website.
    'get_access_token',
    # Anonymous stable per-install id - used by main_eel._ping_install for
    # active-install counting (and the single-session active_device claim).
    'device_id',
    'AuthError',
]
