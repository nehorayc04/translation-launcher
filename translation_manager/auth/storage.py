"""
OS-native token storage via `keyring`.

Backends per platform:
  Windows  → Windows Credential Manager (DPAPI-encrypted)
  macOS    → Keychain
  Linux    → libsecret / KWallet (via Secret Service)

We store a single JSON blob under
  service = 'TranslationLauncher'
  user    = 'supabase'
containing access_token, refresh_token, and the access token's
expiry timestamp. This is dramatically safer than dropping the
tokens into a plain file under %APPDATA%.

If `keyring` can't find a backend (very rare — only happens on
headless Linux with no D-Bus + no fallback) we DO NOT silently
fall back to disk. We raise so the operator can fix the
environment rather than ship plaintext tokens to disk.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from typing import Optional

try:
    import keyring
    import keyring.errors as keyring_errors  # noqa: F401  (re-exported by Token)
except ImportError as e:                        # pragma: no cover
    raise RuntimeError(
        "Missing 'keyring' dependency. Run: pip install keyring"
    ) from e

_SERVICE = 'TranslationLauncher'
_USER    = 'supabase'


@dataclass
class StoredToken:
    access_token:  str
    refresh_token: str
    expires_at:    int       # epoch seconds
    user_id:       str = ''
    email:         str = ''

    def is_expired(self, skew: int = 30) -> bool:
        """True if the access token will expire within `skew` seconds."""
        return time.time() + skew >= self.expires_at


class TokenStore:
    """Thin wrapper around the platform keyring."""

    def save(self, token: StoredToken) -> None:
        try:
            keyring.set_password(_SERVICE, _USER, json.dumps(asdict(token)))
        except keyring.errors.KeyringError as e:
            raise RuntimeError(
                'Could not store credentials in the OS keyring. '
                'Aborting to avoid writing plaintext tokens to disk.'
            ) from e

    def load(self) -> Optional[StoredToken]:
        try:
            raw = keyring.get_password(_SERVICE, _USER)
        except keyring.errors.KeyringError:
            return None
        if not raw:
            return None
        try:
            data = json.loads(raw)
            return StoredToken(
                access_token  = str(data.get('access_token', '')),
                refresh_token = str(data.get('refresh_token', '')),
                expires_at    = int(data.get('expires_at', 0)),
                user_id       = str(data.get('user_id', '')),
                email         = str(data.get('email', '')),
            )
        except (json.JSONDecodeError, ValueError, TypeError):
            # Corrupted blob — best-effort wipe so the next login flow
            # gets a clean slate.
            self.clear()
            return None

    def clear(self) -> None:
        try:
            keyring.delete_password(_SERVICE, _USER)
        except keyring.errors.PasswordDeleteError:
            pass
        except keyring.errors.KeyringError:
            pass
