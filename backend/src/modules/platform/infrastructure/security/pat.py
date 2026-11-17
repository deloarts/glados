"""
Opaque personal-access-token generation and hashing. Same shape as
src/modules/platform/infrastructure/security/api_key.py (opaque bearer secret, SHA-256
hash-at-rest for O(1) lookup and instant revocation), a PAT is just as
long-lived and high-value as an API key, so it gets the same treatment
rather than being stored as a raw, unhashed JWT.
"""

import hashlib
import secrets

_PREFIX = "glados_pat_"
_PREFIX_DISPLAY_LEN = 12  # extra chars (after _PREFIX) kept in token_prefix for UI display


def generate_pat() -> str:
    return _PREFIX + secrets.token_urlsafe(32)


def hash_pat(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def display_prefix(token: str) -> str:
    """A short, non-secret slice of the token shown in the UI so a user can
    recognize which token is which without ever seeing the full value again."""
    return token[: len(_PREFIX) + _PREFIX_DISPLAY_LEN]
