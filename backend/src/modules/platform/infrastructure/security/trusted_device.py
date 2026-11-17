"""
Opaque trusted-device secret generation and hashing. Same shape as
src/modules/platform/infrastructure/security/pat.py: an opaque bearer secret lives only in
the browser's httpOnly cookie, SHA-256 hash-at-rest gives O(1) lookup and
instant revocation, and a database leak yields nothing replayable.
"""

import hashlib
import secrets

TRUSTED_DEVICE_COOKIE = "glados_trusted_device"


def generate_trusted_device_secret() -> str:
    return secrets.token_urlsafe(32)


def hash_trusted_device(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()
