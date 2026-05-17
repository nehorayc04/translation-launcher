"""
RFC 7636 PKCE — Proof Key for Code Exchange.

Why PKCE matters for a desktop app:
  Without PKCE, an attacker who intercepts the redirect ?code=
  on the loopback URL can exchange it for tokens (no client secret
  is shipped in a desktop binary — that's the whole point of public
  clients). PKCE binds the code exchange to a code_verifier the
  attacker can't know, so an intercepted code is useless.

Generated values:
  code_verifier   — high-entropy random string, 43–128 chars, [A-Z a-z 0-9 - . _ ~]
  code_challenge  — base64url( sha256(code_verifier) ), no padding
"""
from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass


@dataclass(frozen=True)
class PkcePair:
    verifier:  str
    challenge: str
    method:    str = 'S256'


def generate() -> PkcePair:
    # 32 random bytes → 43-char URL-safe verifier (within RFC range).
    verifier_bytes = secrets.token_bytes(32)
    verifier = base64.urlsafe_b64encode(verifier_bytes).rstrip(b'=').decode('ascii')

    digest = hashlib.sha256(verifier.encode('ascii')).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b'=').decode('ascii')

    return PkcePair(verifier=verifier, challenge=challenge)
