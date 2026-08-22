"""
Supabase project config for the launcher's OAuth flow.

The anon key is intentionally embeddable in the binary - Supabase's
RLS makes that key safe to ship to end users (it has zero implicit
permissions beyond what policies grant). The service-role key, which
is the dangerous one, never leaves the website's Vercel functions.

Resolution order (first hit wins):
  1. env vars  SUPABASE_URL / SUPABASE_ANON_KEY
  2. ~/.translation_manager/auth.json  { "url": "...", "anon_key": "..." }
  3. compile-time defaults (set via SUPABASE_URL/SUPABASE_ANON_KEY
     during the PyInstaller build, baked in below)

If none resolve we raise AuthConfigError early so the rest of the
flow never silently uses a placeholder.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

# Compile-time defaults. Sourced from a build-time-generated, gitignored
# `_baked.py` module so the actual values never enter source control.
# build_exe.bat regenerates _baked.py from .env.build before each
# PyInstaller run. If it's missing (dev environment), we leave the
# defaults blank and let the env / auth.json fallbacks kick in.
try:
    from . import _baked   # type: ignore[attr-defined]
    _DEFAULT_URL      = getattr(_baked, 'SUPABASE_URL', '')
    _DEFAULT_ANON_KEY = getattr(_baked, 'SUPABASE_ANON_KEY', '')
except ImportError:
    _DEFAULT_URL      = ''
    _DEFAULT_ANON_KEY = ''


class AuthConfigError(RuntimeError):
    """Raised when Supabase URL / anon key cannot be resolved."""


@dataclass(frozen=True)
class SupabaseConfig:
    url:      str
    anon_key: str

    @property
    def authorize_url(self) -> str:
        # /auth/v1/authorize is the Supabase Auth entry point for OAuth
        # providers. We pass provider + redirect_to + PKCE params via
        # query string at call time.
        return self.url.rstrip('/') + '/auth/v1/authorize'

    @property
    def token_url(self) -> str:
        return self.url.rstrip('/') + '/auth/v1/token'

    @property
    def user_url(self) -> str:
        return self.url.rstrip('/') + '/auth/v1/user'

    @property
    def rest_url(self) -> str:
        return self.url.rstrip('/') + '/rest/v1'


def _load_from_file() -> tuple[str, str]:
    p = Path.home() / '.translation_manager' / 'auth.json'
    if not p.exists():
        return '', ''
    try:
        data = json.loads(p.read_text(encoding='utf-8'))
        return str(data.get('url', '')), str(data.get('anon_key', ''))
    except (OSError, json.JSONDecodeError):
        return '', ''


def load_config() -> SupabaseConfig:
    url = os.environ.get('SUPABASE_URL') or ''
    key = os.environ.get('SUPABASE_ANON_KEY') or ''

    if not (url and key):
        f_url, f_key = _load_from_file()
        url = url or f_url
        key = key or f_key

    url = url or _DEFAULT_URL
    key = key or _DEFAULT_ANON_KEY

    if not url or not key:
        raise AuthConfigError(
            'Supabase URL/anon key not configured. Set SUPABASE_URL + '
            'SUPABASE_ANON_KEY env vars, drop them in '
            '~/.translation_manager/auth.json, or rebuild with bake-time '
            'defaults.'
        )
    return SupabaseConfig(url=url, anon_key=key)
