"""
translation_manager.auth — Supabase OAuth (Google) + token storage
for the desktop launcher.

Public API:

    from translation_manager.auth import login, logout, me, owns_game

    login()        -> dict     # blocking, opens browser, returns user
    me()           -> dict|None # current cached user (None if signed out)
    logout()       -> None
    owns_game(id)  -> bool      # quick DRM check against user_purchases

Internals live in the sibling modules:

    config.py    — Supabase project URL + anon key (env-driven)
    pkce.py      — RFC 7636 PKCE verifier + challenge
    loopback.py  — one-shot http.server on 127.0.0.1 for the OAuth callback
    storage.py   — keyring-backed token store
    manager.py   — orchestration

We deliberately keep the OAuth flow in stdlib (http.server + requests +
webbrowser) so PyInstaller doesn't have to bundle aiohttp / authlib.
"""
from .manager import (
    login, logout, me, owns_game, abort_login,
    get_last_authorize_url,
    signin_with_password, signup_with_password,
    AuthError,
)

__all__ = [
    'login', 'logout', 'me', 'owns_game', 'abort_login',
    'get_last_authorize_url',
    'signin_with_password', 'signup_with_password',
    'AuthError',
]
