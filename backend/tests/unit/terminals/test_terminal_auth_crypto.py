"""The device sign-in cryptography: the challenge nonce, the Ed25519
signature check, the fingerprint, and the separation of terminal and web
tokens."""

import base64
import hashlib
from datetime import UTC
from datetime import datetime
from datetime import timedelta

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding
from cryptography.hazmat.primitives.serialization import PublicFormat

from src.modules.operations.infrastructure.security import terminal_auth
from src.modules.platform.infrastructure.security.token import create_access_token
from src.modules.platform.infrastructure.security.token import get_token_payload

NOW = datetime(2026, 10, 30, 12, 0, tzinfo=UTC)


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _key_pair() -> tuple[Ed25519PrivateKey, str]:
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return private, _b64(public)


def _sign(private: Ed25519PrivateKey, nonce: str) -> str:
    return _b64(private.sign(b"glados-terminal-auth-v1:" + nonce.encode("ascii")))


def test_terminal_nonce_is_bound_to_its_key_and_expires() -> None:
    _, public_key = _key_pair()
    _, other_key = _key_pair()
    nonce, expires_at = terminal_auth.issue_nonce(public_key, NOW, 60)
    assert expires_at == NOW + timedelta(seconds=60)
    assert nonce.isascii()
    assert terminal_auth.nonce_valid_for(nonce, public_key, NOW + timedelta(seconds=59))
    assert not terminal_auth.nonce_valid_for(nonce, public_key, NOW + timedelta(seconds=60))
    assert not terminal_auth.nonce_valid_for(nonce, other_key, NOW)
    tampered = nonce.replace(nonce.split(".")[1], str(int(nonce.split(".")[1]) + 3600))
    assert not terminal_auth.nonce_valid_for(tampered, public_key, NOW)
    assert not terminal_auth.nonce_valid_for("garbage", public_key, NOW)


def test_terminal_signature_verification() -> None:
    private, public_key = _key_pair()
    other_private, _ = _key_pair()
    nonce, _ = terminal_auth.issue_nonce(public_key, NOW, 60)
    assert terminal_auth.signature_valid(public_key, nonce, _sign(private, nonce))
    assert not terminal_auth.signature_valid(public_key, nonce, _sign(other_private, nonce))
    unprefixed = _b64(private.sign(nonce.encode("ascii")))
    assert not terminal_auth.signature_valid(public_key, nonce, unprefixed)
    assert not terminal_auth.signature_valid(public_key, nonce, "not base64!")
    assert not terminal_auth.signature_valid("short", nonce, _sign(private, nonce))


def test_terminal_public_key_validation_and_fingerprint() -> None:
    _, public_key = _key_pair()
    assert terminal_auth.is_valid_public_key(public_key)
    assert not terminal_auth.is_valid_public_key(public_key + "=")
    assert not terminal_auth.is_valid_public_key(_b64(b"x" * 31))
    raw = base64.urlsafe_b64decode(public_key + "=")
    expected = hashlib.sha256(raw).hexdigest()[:16]
    assert terminal_auth.public_key_fingerprint(public_key) == expected


def test_terminal_token_round_trip_and_expiry() -> None:
    now = datetime.now(UTC)
    token, expires_at = terminal_auth.create_terminal_access_token(42, now, timedelta(minutes=15))
    assert expires_at == now + timedelta(minutes=15)
    assert terminal_auth.terminal_id_from_token(token) == 42
    expired, _ = terminal_auth.create_terminal_access_token(
        42, now - timedelta(minutes=20), timedelta(minutes=15)
    )
    assert terminal_auth.terminal_id_from_token(expired) is None


def test_terminal_and_web_tokens_are_never_interchangeable() -> None:
    terminal_token, _ = terminal_auth.create_terminal_access_token(
        42, datetime.now(UTC), timedelta(minutes=15)
    )
    assert get_token_payload(terminal_token, persistent=False) is None
    assert get_token_payload(terminal_token, persistent=True) is None

    web_token = create_access_token(subject=42, persistent=False, expires_delta=None)
    assert terminal_auth.terminal_id_from_token(web_token) is None


def test_infoscreen_thumbnail_token_round_trip() -> None:
    token = terminal_auth.create_thumbnail_token("made", 12, "thumbnail", NOW)
    claims = terminal_auth.read_thumbnail_token(token, NOW)
    assert claims is not None
    assert claims[:3] == ("made", 12, "thumbnail")
    assert "/" not in token and "?" not in token


def test_infoscreen_thumbnail_token_lives_30_to_90_minutes_and_is_stable_per_hour() -> None:
    start_of_hour = NOW.replace(minute=0, second=0)
    early = terminal_auth.create_thumbnail_token("made", 12, "thumbnail", start_of_hour)
    late = terminal_auth.create_thumbnail_token(
        "made", 12, "thumbnail", start_of_hour + timedelta(minutes=59, seconds=59)
    )
    assert early == late
    expires = terminal_auth.thumbnail_expiry(start_of_hour)
    assert expires - start_of_hour.timestamp() == 90 * 60
    end_of_hour = start_of_hour + timedelta(minutes=59, seconds=59)
    assert 30 * 60 <= expires - end_of_hour.timestamp() <= 90 * 60
    next_hour = terminal_auth.create_thumbnail_token(
        "made", 12, "thumbnail", start_of_hour + timedelta(hours=1)
    )
    assert next_hour != early


def test_infoscreen_thumbnail_token_expires() -> None:
    token = terminal_auth.create_thumbnail_token("made", 12, "thumbnail", NOW)
    expires = terminal_auth.thumbnail_expiry(NOW)
    assert (
        terminal_auth.read_thumbnail_token(token, datetime.fromtimestamp(expires - 1, UTC))
        is not None
    )
    assert terminal_auth.read_thumbnail_token(token, datetime.fromtimestamp(expires, UTC)) is None


def test_infoscreen_thumbnail_token_refuses_tampering() -> None:
    token = terminal_auth.create_thumbnail_token("made", 12, "thumbnail", NOW)
    parts = token.split(".")
    for index, value in ((1, "bought"), (2, "13"), (3, "image"), (4, str(int(parts[4]) + 3600))):
        forged = parts.copy()
        forged[index] = value
        assert terminal_auth.read_thumbnail_token(".".join(forged), NOW) is None
    assert terminal_auth.read_thumbnail_token("garbage", NOW) is None
    assert terminal_auth.read_thumbnail_token(token + "x", NOW) is None
