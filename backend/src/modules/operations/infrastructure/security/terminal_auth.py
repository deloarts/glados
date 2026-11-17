"""
Cryptography of the terminal device sign-in: the challenge nonce, the
Ed25519 signature check, the key fingerprint and the terminal access token.

The nonce is stateless. It carries its expiry and a random part, and an
HMAC binds both to the public key it was issued for, so any worker can check
it without shared state. Single use is enforced separately, by claiming the
nonce in the replay guard when the session is started.

The device signs `glados-terminal-auth-v1:` followed by the nonce as ASCII.
Public keys and signatures travel as base64url without padding.

The access token is a JWT with its own scope and audience, signed with a key
derived from the non-persistent secret for terminals alone. A web session
decoder therefore never accepts a terminal token, and the terminal decoder
never accepts a web token, whatever claims either carries.

Infoscreen thumbnail links carry their own HMAC token naming one item
picture and an expiry rounded to an hourly bucket, so a display's image
cache survives feed refetches.
"""

import base64
import binascii
import hashlib
import hmac
import secrets
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Any
from typing import Final

import jwt
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from src.modules.platform.infrastructure.config.settings import cfg

SIGNED_PREFIX: Final = b"glados-terminal-auth-v1:"
TERMINAL_TOKEN_SCOPE: Final = "terminal"
TERMINAL_TOKEN_AUDIENCE: Final = "glados-terminal"

_PUBLIC_KEY_BYTES = 32
_SIGNATURE_BYTES = 64
_NONCE_VERSION = "v1"
_NONCE_RANDOM_BYTES = 18
_FINGERPRINT_HEX_CHARS = 16
_B64URL_ALPHABET = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")


def _b64url_decode(value: str) -> bytes | None:
    """Bytes of an unpadded base64url string, or None when it is not one."""
    if not value or any(c not in _B64URL_ALPHABET for c in value):
        return None
    try:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (binascii.Error, ValueError):
        return None


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def public_key_bytes(public_key: str) -> bytes | None:
    """The raw key, or None when it is not 32 bytes of unpadded base64url."""
    raw = _b64url_decode(public_key)
    if raw is None or len(raw) != _PUBLIC_KEY_BYTES:
        return None
    return raw


def is_valid_public_key(public_key: str) -> bool:
    raw = public_key_bytes(public_key)
    if raw is None:
        return False
    try:
        Ed25519PublicKey.from_public_bytes(raw)
    except ValueError:
        return False
    return True


def public_key_fingerprint(public_key: str) -> str:
    """The first 16 hex characters of SHA-256 over the raw key."""
    raw = public_key_bytes(public_key) or public_key.encode("ascii", "replace")
    return hashlib.sha256(raw).hexdigest()[:_FINGERPRINT_HEX_CHARS]


def _derived_key(purpose: bytes) -> bytes:
    return hmac.new(
        cfg.security.secret_key_non_persistent.encode("utf-8"), purpose, hashlib.sha256
    ).digest()


def _nonce_mac(public_key: str, expires: int, random_part: str) -> str:
    message = f"{_NONCE_VERSION}|{public_key}|{expires}|{random_part}".encode()
    digest = hmac.new(_derived_key(b"glados-terminal-nonce-v1"), message, hashlib.sha256)
    return _b64url_encode(digest.digest())


def issue_nonce(public_key: str, now: datetime, ttl_seconds: int) -> tuple[str, datetime]:
    """A nonce for `public_key` and the moment it expires."""
    expires = int(now.timestamp()) + ttl_seconds
    random_part = _b64url_encode(secrets.token_bytes(_NONCE_RANDOM_BYTES))
    nonce = ".".join(
        (_NONCE_VERSION, str(expires), random_part, _nonce_mac(public_key, expires, random_part))
    )
    return nonce, datetime.fromtimestamp(expires, UTC)


def nonce_valid_for(nonce: str, public_key: str, now: datetime) -> bool:
    """Whether `nonce` was issued here for `public_key` and has not expired.
    It says nothing about whether it was used before."""
    parts = nonce.split(".")
    if len(parts) != 4 or parts[0] != _NONCE_VERSION or not parts[1].isdigit():
        return False
    expires = int(parts[1])
    expected = _nonce_mac(public_key, expires, parts[2])
    if not hmac.compare_digest(expected.encode("ascii"), parts[3].encode("ascii", "replace")):
        return False
    return now.timestamp() < expires


def signature_valid(public_key: str, nonce: str, signature: str) -> bool:
    """Whether `signature` is the Ed25519 signature of the signed prefix plus
    `nonce` under `public_key`."""
    raw_key = public_key_bytes(public_key)
    raw_signature = _b64url_decode(signature)
    if raw_key is None or raw_signature is None or len(raw_signature) != _SIGNATURE_BYTES:
        return False
    try:
        message = SIGNED_PREFIX + nonce.encode("ascii")
        Ed25519PublicKey.from_public_bytes(raw_key).verify(raw_signature, message)
    except (InvalidSignature, ValueError, UnicodeEncodeError):
        return False
    return True


def _token_key() -> bytes:
    return _derived_key(b"glados-terminal-token-v1")


def create_terminal_access_token(
    terminal_id: int, now: datetime, ttl: timedelta
) -> tuple[str, datetime]:
    """A signed access token naming the terminal, and its expiry."""
    expires_at = now + ttl
    payload: dict[str, Any] = {
        "sub": str(terminal_id),
        "scope": TERMINAL_TOKEN_SCOPE,
        "aud": TERMINAL_TOKEN_AUDIENCE,
        "iat": int(now.timestamp()),
        "exp": expires_at,
    }
    token: str = jwt.encode(payload, _token_key(), algorithm="HS256")
    return token, expires_at


def terminal_id_from_token(token: str) -> int | None:
    """The terminal a valid, unexpired terminal token names, or None."""
    if not token:
        return None
    try:
        claims = jwt.decode(
            token,
            _token_key(),
            algorithms=["HS256"],
            audience=TERMINAL_TOKEN_AUDIENCE,
            options={"require": ["exp", "sub", "aud"]},
        )
    except jwt.PyJWTError:
        return None
    if claims.get("scope") != TERMINAL_TOKEN_SCOPE:
        return None
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject.isdigit():
        return None
    return int(subject)


# ── Infoscreen thumbnail links ───────────────────────────────────────────

# A thumbnail link expires at the end of the current hour plus half an hour,
# so it stays valid for 30 to 90 minutes and every feed built within the
# same hour carries the same link, which keeps the browser cache working.
THUMBNAIL_BUCKET_SECONDS: Final = 3600
THUMBNAIL_GRACE_SECONDS: Final = 1800
_THUMBNAIL_VERSION = "t1"


def _thumbnail_mac(kind: str, item_id: int, variant: str, expires: int) -> str:
    message = f"{_THUMBNAIL_VERSION}|{kind}|{item_id}|{variant}|{expires}".encode()
    digest = hmac.new(_derived_key(b"glados-infoscreen-thumbnail-v1"), message, hashlib.sha256)
    return _b64url_encode(digest.digest()[:18])


def thumbnail_expiry(now: datetime) -> int:
    """The expiry, in unix seconds, of a link issued at `now`."""
    bucket_end = (int(now.timestamp()) // THUMBNAIL_BUCKET_SECONDS + 1) * THUMBNAIL_BUCKET_SECONDS
    return bucket_end + THUMBNAIL_GRACE_SECONDS


def create_thumbnail_token(kind: str, item_id: int, variant: str, now: datetime) -> str:
    """A signed, URL-safe token naming one item picture variant. It grants
    nothing else and carries no user."""
    expires = thumbnail_expiry(now)
    mac = _thumbnail_mac(kind, item_id, variant, expires)
    return ".".join((_THUMBNAIL_VERSION, kind, str(item_id), variant, str(expires), mac))


def read_thumbnail_token(token: str, now: datetime) -> tuple[str, int, str, int] | None:
    """(kind, item id, variant, expiry) of a valid, unexpired token, or None."""
    parts = token.split(".")
    if len(parts) != 6 or parts[0] != _THUMBNAIL_VERSION:
        return None
    _, kind, raw_id, variant, raw_expires, mac = parts
    if not raw_id.isdigit() or not raw_expires.isdigit():
        return None
    item_id, expires = int(raw_id), int(raw_expires)
    expected = _thumbnail_mac(kind, item_id, variant, expires)
    if not hmac.compare_digest(expected.encode("ascii"), mac.encode("ascii", "replace")):
        return None
    if now.timestamp() >= expires:
        return None
    return kind, item_id, variant, expires


# ── Infoscreen drawing links ─────────────────────────────────────────────

# A drawing link names one drawing file of one made item and expires like a
# thumbnail link. It is signed under its own derived key, so a thumbnail
# token can never be passed off as a drawing token or the other way round.
_DRAWING_VERSION = "d1"


def _drawing_mac(item_id: int, file_id: int, expires: int) -> str:
    message = f"{_DRAWING_VERSION}|{item_id}|{file_id}|{expires}".encode()
    digest = hmac.new(_derived_key(b"glados-infoscreen-drawing-v1"), message, hashlib.sha256)
    return _b64url_encode(digest.digest()[:18])


def create_drawing_token(item_id: int, file_id: int, now: datetime) -> str:
    """A signed, URL-safe token naming one drawing file of a made item. It
    grants nothing else and carries no user."""
    expires = thumbnail_expiry(now)
    mac = _drawing_mac(item_id, file_id, expires)
    return ".".join((_DRAWING_VERSION, str(item_id), str(file_id), str(expires), mac))


def read_drawing_token(token: str, now: datetime) -> tuple[int, int, int] | None:
    """(made item id, file id, expiry) of a valid, unexpired token, or None."""
    parts = token.split(".")
    if len(parts) != 5 or parts[0] != _DRAWING_VERSION:
        return None
    _, raw_item, raw_file, raw_expires, mac = parts
    if not (raw_item.isdigit() and raw_file.isdigit() and raw_expires.isdigit()):
        return None
    item_id, file_id, expires = int(raw_item), int(raw_file), int(raw_expires)
    expected = _drawing_mac(item_id, file_id, expires)
    if not hmac.compare_digest(expected.encode("ascii"), mac.encode("ascii", "replace")):
        return None
    if now.timestamp() >= expires:
        return None
    return item_id, file_id, expires
