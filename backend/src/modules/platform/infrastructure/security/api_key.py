"""
Opaque API key generation and hashing. Deliberately NOT a JWT and NOT
bcrypt: an API key is a long-lived, high-entropy bearer credential, so
(1) we want O(1) hash-lookup revocation rather than JWT-style stateless
decode+trust, and (2) bcrypt's random salt makes lookup-by-hash impossible
(fine for low-entropy passwords, wrong tool for an already-random secret).
SHA-256 over a cryptographically random token is the standard approach here
(the same shape GitHub/Stripe API keys use).
"""

import hashlib
import secrets

_PREFIX = "glados_ak_"
_PREFIX_DISPLAY_LEN = 12  # extra chars (after _PREFIX) kept in token_prefix for UI display


def generate_api_key() -> str:
    return _PREFIX + secrets.token_urlsafe(32)


def hash_api_key(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def display_prefix(token: str) -> str:
    """A short, non-secret slice of the key shown in the UI so an admin can
    recognize which key is which without ever seeing the full value again."""
    return token[: len(_PREFIX) + _PREFIX_DISPLAY_LEN]
