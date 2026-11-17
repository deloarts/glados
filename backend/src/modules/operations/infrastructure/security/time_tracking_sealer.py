"""
Seals a user's time tracking credentials for the time tracking service's
public key, so Glados stores a value only the service can open. HPKE
(RFC 9180, base mode) with DHKEM(X25519, HKDF-SHA256), HKDF-SHA256 and
ChaCha20-Poly1305; the plaintext is UTF-8 JSON with one entry per credential
field, and the sealed value is the HPKE ciphertext in base64url without
padding. `INFO` binds the ciphertext to this purpose. The format is part of
the time tracking provider contract (docs/reference/time-tracking-provider.md).

Nothing here logs, and no error message carries a credential.
"""

import base64
import binascii
import json

from cryptography.hazmat.primitives import hpke
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey

INFO = b"glados time tracking credentials v1"

_SUITE = hpke.Suite(hpke.KEM.X25519, hpke.KDF.HKDF_SHA256, hpke.AEAD.CHACHA20_POLY1305)
_X25519_PUBLIC_KEY_LENGTH = 32


class InvalidCredentialKeyError(ValueError):
    """The public key is not 32 raw X25519 bytes in base64url."""


def _b64url_decode(text: str) -> bytes:
    stripped = text.strip()
    padded = stripped + "=" * (-len(stripped) % 4)
    try:
        return base64.urlsafe_b64decode(padded.encode("ascii"))
    except (binascii.Error, UnicodeEncodeError) as exc:
        raise InvalidCredentialKeyError("The credential key is not base64url.") from exc


def load_public_key(encoded: str) -> X25519PublicKey:
    raw = _b64url_decode(encoded)
    if len(raw) != _X25519_PUBLIC_KEY_LENGTH:
        raise InvalidCredentialKeyError("The credential key is not an X25519 public key.")
    return X25519PublicKey.from_public_bytes(raw)


def seal_credentials(values: dict[str, str], public_key: str) -> str:
    """The sealed value for `values`, for example {"user": ..., "password": ...}."""
    ciphertext = _SUITE.encrypt(
        json.dumps(values).encode("utf-8"), load_public_key(public_key), info=INFO
    )
    return base64.urlsafe_b64encode(ciphertext).rstrip(b"=").decode("ascii")
