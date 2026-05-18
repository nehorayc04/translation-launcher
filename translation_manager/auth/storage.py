"""
Hybrid token storage: a short Fernet key in the OS keyring, the
encrypted session blob in a file under %USERPROFILE%.

Why hybrid:
  • Windows Credential Manager rejects credentials over ~2560 bytes
    with WinError 1783 ("The stub received bad data"). The Supabase
    session JSON (two long JWTs + user metadata) routinely exceeds
    that limit, so storing it directly in the keyring as we used to
    fails on the very first sign-in.
  • Storing the WHOLE blob on disk in plaintext would be worse than
    the old keyring approach — anyone who exfiltrated %USERPROFILE%
    would walk away with the user's refresh token.
  • Hybrid splits the two: the 44-byte base64 Fernet key sits inside
    the keyring (DPAPI-encrypted on Windows, Keychain on macOS, Secret
    Service on Linux), well below every backend's size limit. The
    encrypted payload sits on disk. Neither half is useful on its
    own — exfil of the disk file needs the keyring key, exfil of the
    keyring key needs the file. Symmetry of inconvenience.

Migration from the old plain-JSON-in-keyring layout is automatic on
the first load() after upgrade — if we find a legacy JSON blob under
the old keyring slot we decode it, re-save it under the new scheme,
and clear the legacy entry. From then on the new path is the only
one exercised.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

try:
    import keyring
    import keyring.errors as keyring_errors  # noqa: F401
except ImportError as e:                        # pragma: no cover
    raise RuntimeError(
        "Missing 'keyring' dependency. Run: pip install keyring"
    ) from e

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError as e:                        # pragma: no cover
    raise RuntimeError(
        "Missing 'cryptography' dependency. Run: pip install cryptography"
    ) from e

_SERVICE     = 'TranslationLauncher'
_KEY_USER    = 'supabase-fernet-key'   # 44-byte base64 Fernet key
_LEGACY_USER = 'supabase'              # old plain-JSON slot (pre-1.1)


def _session_file() -> Path:
    return Path.home() / '.translation_manager' / 'session.enc'


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


def _load_or_create_key() -> bytes:
    """Return the Fernet key, creating + persisting a new one if absent.
    The key is ~44 bytes of base64 — comfortably under every keyring
    backend's per-credential size limit."""
    try:
        existing = keyring.get_password(_SERVICE, _KEY_USER)
    except keyring.errors.KeyringError:
        existing = None
    if existing:
        return existing.encode('ascii')
    new_key = Fernet.generate_key()  # 32 random bytes → 44 base64 chars
    try:
        keyring.set_password(_SERVICE, _KEY_USER, new_key.decode('ascii'))
    except keyring.errors.KeyringError as e:
        raise RuntimeError(
            'Could not store the session encryption key in the OS keyring. '
            'Aborting to avoid writing an unprotected key to disk.'
        ) from e
    return new_key


def _atomic_write(path: Path, data: bytes) -> None:
    """Write file atomically — write to .tmp, fsync, replace. Prevents
    a half-written session.enc if the process is killed mid-write
    (which would otherwise look like corruption on next load)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    with open(tmp, 'wb') as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


class TokenStore:
    """File-backed encrypted session store. Key in keyring, payload on disk."""

    def save(self, token: StoredToken) -> None:
        try:
            key   = _load_or_create_key()
            blob  = json.dumps(asdict(token)).encode('utf-8')
            enc   = Fernet(key).encrypt(blob)
            _atomic_write(_session_file(), enc)
        except RuntimeError:
            # Already a friendly RuntimeError from _load_or_create_key.
            raise
        except keyring.errors.KeyringError as e:
            raise RuntimeError(
                'Could not access the OS keyring to save the session. '
                'Aborting to avoid writing tokens to disk in plaintext.'
            ) from e
        except OSError as e:
            raise RuntimeError(
                f'Could not write the encrypted session file: {e}'
            ) from e

    def load(self) -> Optional[StoredToken]:
        # ── Migration path: a legacy plain-JSON blob still in keyring? ──
        # Read it, write it through the new pipeline, clear the legacy
        # slot. Quietly, so an upgrade doesn't surface unrelated errors.
        legacy = self._read_legacy()
        if legacy is not None:
            try:
                self.save(legacy)
                self._clear_legacy()
            except Exception:
                # If migration fails (e.g. cryptography missing on this
                # platform) keep the legacy blob — at least the user
                # stays signed in.
                return legacy
            return legacy

        path = _session_file()
        if not path.exists():
            return None
        try:
            key  = _load_or_create_key()
            enc  = path.read_bytes()
            blob = Fernet(key).decrypt(enc)
            data = json.loads(blob.decode('utf-8'))
        except (InvalidToken, json.JSONDecodeError, ValueError, OSError,
                keyring.errors.KeyringError):
            # Corrupted file, mismatched key (e.g. user wiped Credential
            # Manager and a stale ciphertext is left), or unreadable —
            # nuke both halves so the next sign-in starts clean.
            self.clear()
            return None
        return StoredToken(
            access_token  = str(data.get('access_token', '')),
            refresh_token = str(data.get('refresh_token', '')),
            expires_at    = int(data.get('expires_at', 0)),
            user_id       = str(data.get('user_id', '')),
            email         = str(data.get('email', '')),
        )

    def clear(self) -> None:
        # Wipe both halves so a stale ciphertext can never haunt the
        # next session.
        try:
            keyring.delete_password(_SERVICE, _KEY_USER)
        except (keyring.errors.PasswordDeleteError, keyring.errors.KeyringError):
            pass
        self._clear_legacy()
        try:
            _session_file().unlink(missing_ok=True)
        except OSError:
            pass

    # ── legacy keyring slot (pre-1.1 plain-JSON) ────────────────────

    @staticmethod
    def _read_legacy() -> Optional[StoredToken]:
        try:
            raw = keyring.get_password(_SERVICE, _LEGACY_USER)
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
            return None

    @staticmethod
    def _clear_legacy() -> None:
        try:
            keyring.delete_password(_SERVICE, _LEGACY_USER)
        except (keyring.errors.PasswordDeleteError, keyring.errors.KeyringError):
            pass
