# -*- coding: utf-8 -*-
"""Encrypted storage for the volunteer's 3 provider API keys.

Same hybrid scheme as the launcher's session store (translation_manager/auth/
storage.py): a 44-byte Fernet key lives in the OS keyring (DPAPI on Windows),
the encrypted key blob sits on disk under %USERPROFILE%\\.community_compute\\.
Neither half is useful alone. The keys are NEVER transmitted anywhere — the
worker uses them locally to call the providers, and the operator never sees them.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import keyring
import keyring.errors
from cryptography.fernet import Fernet, InvalidToken

_SERVICE = "CommunityCompute"
_KEY_USER = "cc-fernet-key"


def _dir() -> Path:
    # FOLDERID_Profile-safe home (the sandbox redirects %USERPROFILE%; the real
    # user home is what SHGetKnownFolderPath returns — but for a shipped app the
    # plain home is correct, so keep it simple and robust).
    return Path(os.path.expanduser("~")) / ".community_compute"


def _blob() -> Path:
    return _dir() / "keys.enc"


def _fernet() -> Fernet:
    existing = keyring.get_password(_SERVICE, _KEY_USER)   # may raise KeyringError → caller handles
    if existing:
        return Fernet(existing.encode("ascii"))
    key = Fernet.generate_key()
    keyring.set_password(_SERVICE, _KEY_USER, key.decode("ascii"))
    return Fernet(key)


def load() -> dict:
    """Return {provider_id: api_key}. Missing/unreadable → {} (never raises)."""
    p = _blob()
    if not p.exists():
        return {}
    try:
        enc = p.read_bytes()
        data = json.loads(_fernet().decrypt(enc).decode("utf-8"))
        return {k: str(v) for k, v in data.items() if v}
    except (InvalidToken, ValueError, OSError, keyring.errors.KeyringError):
        return {}


def save(keys: dict) -> None:
    """Encrypt + persist {provider_id: api_key}. Empty values are dropped."""
    clean = {k: str(v).strip() for k, v in keys.items() if str(v).strip()}
    d = _dir()
    d.mkdir(parents=True, exist_ok=True)
    enc = _fernet().encrypt(json.dumps(clean).encode("utf-8"))
    tmp = _blob().with_suffix(".enc.tmp")
    with open(tmp, "wb") as fh:
        fh.write(enc)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, _blob())


def clear() -> None:
    try:
        keyring.delete_password(_SERVICE, _KEY_USER)
    except keyring.errors.KeyringError:
        pass
    try:
        _blob().unlink(missing_ok=True)
    except OSError:
        pass
