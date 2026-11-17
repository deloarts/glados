"""
Symmetric encryption for secrets the app must read back in plaintext, such
as the SMTP password it logs in with, so they can't be hashed like a user
password. Encrypting them at rest keeps them out of database dumps,
backups and SQL-injection reads. It does not protect against a compromised
host, where the key sits next to the app.

The key is cfg.security.encryption_key, a free-form secret like the signing
keys. HKDF-SHA256 derives the 32-byte Fernet key from it, so any
sufficiently random string works and the env value is never used as key
material directly. Fernet (AES-128-CBC with an HMAC-SHA256 tag) is
authenticated, so a tampered or foreign value fails to decrypt instead of
returning garbage.

Stored values carry the `enc:v1:` prefix. It marks a value as written by
encrypt_secret, so anything else is rejected instead of being mistaken for
a token, and leaves room to change the scheme later without guessing what a
stored value is.

Rotation: set the old key as encryption_key_previous and the new one as
encryption_key. MultiFernet decrypts with either and encrypts with the new
one, and the boot-time pass in persistence/encrypted_type.py re-encrypts
every stored value, after which the previous key can be removed.
"""

import base64
from functools import cache

from cryptography.fernet import Fernet
from cryptography.fernet import InvalidToken
from cryptography.fernet import MultiFernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from src.modules.platform.infrastructure.config.settings import cfg

ENCRYPTED_PREFIX = "enc:v1:"
_HKDF_INFO = b"glados-secret-at-rest-v1"


class SecretDecryptionError(Exception):
    """A stored secret could not be decrypted with any configured key."""


class EncryptionKeyMissingError(RuntimeError):
    """A secret had to be encrypted or decrypted but no key is configured."""


@cache
def _fernet_for(secret: str) -> Fernet:
    derived = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=_HKDF_INFO).derive(
        secret.encode("utf-8")
    )
    return Fernet(base64.urlsafe_b64encode(derived))


@cache
def _box(current: str, previous: str | None) -> MultiFernet:
    keys = [_fernet_for(current)]
    if previous:
        keys.append(_fernet_for(previous))
    return MultiFernet(keys)


def _configured_box() -> MultiFernet:
    current = cfg.security.encryption_key
    if not current:
        raise EncryptionKeyMissingError(
            "SECURITY__ENCRYPTION_KEY is not set, stored secrets cannot be encrypted or read."
        )
    return _box(current, cfg.security.encryption_key_previous)


def is_encrypted(stored: str) -> bool:
    return stored.startswith(ENCRYPTED_PREFIX)


def encryption_configured() -> bool:
    return bool(cfg.security.encryption_key)


def encrypt_secret(plain: str) -> str:
    token = _configured_box().encrypt(plain.encode("utf-8"))
    return ENCRYPTED_PREFIX + token.decode("ascii")


def decrypt_secret(stored: str) -> str:
    """Decrypt a value written by encrypt_secret. Raises SecretDecryptionError
    when no configured key matches, which usually means the key was changed
    without keeping the old one as encryption_key_previous."""
    if not is_encrypted(stored):
        raise SecretDecryptionError("Value is not an encrypted secret.")
    token = stored[len(ENCRYPTED_PREFIX) :].encode("ascii")
    try:
        return _configured_box().decrypt(token).decode("utf-8")
    except InvalidToken as exc:
        raise SecretDecryptionError("No configured encryption key matches.") from exc


def needs_reencryption(stored: str) -> bool:
    """True for values encrypted with the previous key, so the boot pass can
    move them onto the current one. Values without the encrypted prefix and
    undecryptable values return False, there is nothing to re-encrypt them
    from."""
    if not is_encrypted(stored):
        return False
    token = stored[len(ENCRYPTED_PREFIX) :].encode("ascii")
    current = cfg.security.encryption_key
    if not current:
        return False
    try:
        _fernet_for(current).decrypt(token)
        return False
    except InvalidToken:
        pass
    try:
        _configured_box().decrypt(token)
        return True
    except InvalidToken:
        return False
