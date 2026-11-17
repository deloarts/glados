"""
Keyed fingerprint of a time tracking user name, stored in a unique column
so one time tracking account can belong to one Glados user only. The user
name itself is stored encrypted, which is not deterministic,
so it cannot carry a unique index; a plain hash could, but user names are
guessable, and an unkeyed index would reveal from a database dump who
uses which account.

The HMAC key is derived from cfg.security.encryption_key with HKDF-SHA256
and a label of its own, so it is independent of the Fernet key derived from
the same secret in secret_box.py. The key id, the first 8 hex characters of
SHA-256 over the derived key, is stored next to each fingerprint; after a
key rotation the boot step in persistence/time_tracking_fingerprints.py
recomputes every fingerprint whose key id differs. Neither value can be
turned back into the user name.
"""

import hashlib
import hmac
from functools import cache

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from src.modules.platform.infrastructure.config.settings import cfg
from src.modules.platform.infrastructure.security.secret_box import EncryptionKeyMissingError

_HKDF_INFO = b"glados-time-tracking-fingerprint-v1"


@cache
def _derive(secret: str) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=_HKDF_INFO).derive(
        secret.encode("utf-8")
    )


def _current_key() -> bytes:
    secret = cfg.security.encryption_key
    if not secret:
        raise EncryptionKeyMissingError(
            "SECURITY__ENCRYPTION_KEY is not set, time tracking credentials cannot be stored."
        )
    return _derive(secret)


def time_tracking_fingerprint(subject: str) -> str:
    """HMAC-SHA256 over `subject` (see domain fingerprint_subject), hex."""
    return hmac.new(_current_key(), subject.encode("utf-8"), hashlib.sha256).hexdigest()


def time_tracking_fingerprint_key_id() -> str:
    """Identifies the key the current fingerprints are computed with."""
    return hashlib.sha256(_current_key()).hexdigest()[:8]
