"""
Authenticated encryption for database backup archives, with a key from the
environment (cfg.security.backup_encryption_key) that is deliberately
separate from SECURITY__ENCRYPTION_KEY. That key protects the secrets inside
the database, so an archive encrypted with it would put the ciphertext and
the key that opens the secrets in the same place, and losing it would lose
both the stored secrets and every backup at once.

An encrypted archive is the gzip-compressed dump wrapped in a small framed
format, so it can be written and read in chunks without holding the whole
archive twice:

    header  = MAGIC (8 bytes) | salt (16 bytes) | key id (8 bytes)
    chunk   = final flag (1 byte) | ciphertext length (4 bytes, big endian)
              | ciphertext (AES-256-GCM, plaintext plus a 16 byte tag)

HKDF-SHA256 derives a fresh AES-256 key from the env key and the random
salt for every archive, so the chunk counter can serve as the nonce. Each
chunk authenticates the header and its own final flag, so a reordered,
truncated or extended archive fails to decrypt instead of restoring part
of a database. The key id is derived from the env key alone and tells a
wrong key apart from a damaged archive, without revealing the key.
"""

from __future__ import annotations

import os
import struct
from collections.abc import Iterable
from collections.abc import Iterator
from typing import BinaryIO

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

MAGIC = b"GLDBAK\x00\x01"
ENCRYPTED_SUFFIX = ".sql.gz.enc"
PLAIN_SUFFIX = ".sql.gz"
GZIP_MAGIC = b"\x1f\x8b"

_SALT_BYTES = 16
_KEY_ID_BYTES = 8
_HEADER_BYTES = len(MAGIC) + _SALT_BYTES + _KEY_ID_BYTES
_CHUNK_HEADER = struct.Struct(">BI")
_TAG_BYTES = 16
_CHUNK_BYTES = 1024 * 1024
# A frame longer than this cannot have come from this module, so the reader
# refuses it before allocating anything for it.
_MAX_FRAME_BYTES = _CHUNK_BYTES + _TAG_BYTES
_ARCHIVE_INFO = b"glados-backup-archive-v1"
_KEY_ID_INFO = b"glados-backup-key-id-v1"


class BackupArchiveError(Exception):
    """An encrypted archive could not be read: the wrong key, a damaged or
    truncated file, or a file that is no encrypted archive at all."""


class BackupKeyMismatchError(BackupArchiveError):
    """The archive was encrypted with a different key than the one given."""


def key_id(secret: str) -> bytes:
    """A short fingerprint of the env key, stored in every archive header."""
    return HKDF(
        algorithm=hashes.SHA256(), length=_KEY_ID_BYTES, salt=None, info=_KEY_ID_INFO
    ).derive(secret.encode("utf-8"))


def _archive_key(secret: str, salt: bytes) -> AESGCM:
    derived = HKDF(algorithm=hashes.SHA256(), length=32, salt=salt, info=_ARCHIVE_INFO).derive(
        secret.encode("utf-8")
    )
    return AESGCM(derived)


def _nonce(counter: int) -> bytes:
    return counter.to_bytes(12, "big")


def is_encrypted_archive(head: bytes) -> bool:
    """True when `head`, the first bytes of a file, start an encrypted archive."""
    return head.startswith(MAGIC)


def encrypt_chunks(chunks: Iterable[bytes], secret: str) -> Iterator[bytes]:
    """Yields the encrypted archive for the plaintext `chunks`, header first.
    The plaintext is re-cut into fixed frames, so the caller's chunk sizes
    do not matter; an empty input still yields one final frame."""
    salt = os.urandom(_SALT_BYTES)
    header = MAGIC + salt + key_id(secret)
    aead = _archive_key(secret, salt)
    yield header

    counter = 0
    buffer = bytearray()

    def frame(data: bytes, final: bool) -> bytes:
        flag = 1 if final else 0
        sealed = aead.encrypt(_nonce(counter), data, header + bytes([flag]))
        return _CHUNK_HEADER.pack(flag, len(sealed)) + sealed

    for chunk in chunks:
        buffer.extend(chunk)
        # Keep at least one byte back, so the last frame is always the one
        # marked final, even when the input ends on a frame boundary.
        while len(buffer) > _CHUNK_BYTES:
            yield frame(bytes(buffer[:_CHUNK_BYTES]), final=False)
            del buffer[:_CHUNK_BYTES]
            counter += 1
    yield frame(bytes(buffer), final=True)


def encrypt_archive(data: bytes, secret: str) -> bytes:
    """The encrypted archive for `data`, in one piece."""
    return b"".join(encrypt_chunks([data], secret))


def _read_exactly(source: BinaryIO, size: int) -> bytes:
    parts: list[bytes] = []
    remaining = size
    while remaining:
        part = source.read(remaining)
        if not part:
            break
        parts.append(part)
        remaining -= len(part)
    return b"".join(parts)


def decrypt_stream(source: BinaryIO, secret: str) -> Iterator[bytes]:
    """Yields the plaintext of the encrypted archive read from `source`.

    Raises BackupKeyMismatchError when the archive names another key, and
    BackupArchiveError when it is damaged, truncated, extended or no
    encrypted archive at all. Every frame is authenticated before it is
    yielded, so what was yielded before an error is genuine, but the caller
    must still treat the whole read as failed."""
    header = _read_exactly(source, _HEADER_BYTES)
    if len(header) < _HEADER_BYTES or not is_encrypted_archive(header):
        raise BackupArchiveError("The file is not an encrypted Glados backup archive.")
    salt = header[len(MAGIC) : len(MAGIC) + _SALT_BYTES]
    stored_key_id = header[len(MAGIC) + _SALT_BYTES :]
    if stored_key_id != key_id(secret):
        raise BackupKeyMismatchError(
            "The archive was encrypted with a different backup encryption key."
        )
    aead = _archive_key(secret, salt)

    counter = 0
    while True:
        frame_header = _read_exactly(source, _CHUNK_HEADER.size)
        if len(frame_header) < _CHUNK_HEADER.size:
            raise BackupArchiveError("The archive is truncated: its final part is missing.")
        flag, length = _CHUNK_HEADER.unpack(frame_header)
        if flag not in (0, 1) or length < _TAG_BYTES or length > _MAX_FRAME_BYTES:
            raise BackupArchiveError("The archive is damaged: a part has an invalid header.")
        sealed = _read_exactly(source, length)
        if len(sealed) < length:
            raise BackupArchiveError("The archive is truncated in the middle of a part.")
        try:
            plain = aead.decrypt(_nonce(counter), sealed, header + bytes([flag]))
        except InvalidTag as exc:
            raise BackupArchiveError(
                "The archive is damaged: a part fails authentication."
            ) from exc
        yield plain
        counter += 1
        if flag == 1:
            break

    if source.read(1):
        raise BackupArchiveError("The archive is damaged: data follows its final part.")
