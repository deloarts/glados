"""
The backup archive cipher (src/modules/platform/infrastructure/security/
backup_cipher.py): a round trip of any size, and a clear refusal of the
wrong key, a damaged, truncated or extended archive and a foreign file.
"""

import io
import os

import pytest

from src.modules.platform.infrastructure.security import backup_cipher
from src.modules.platform.infrastructure.security.backup_cipher import BackupArchiveError
from src.modules.platform.infrastructure.security.backup_cipher import BackupKeyMismatchError
from src.modules.platform.infrastructure.security.backup_cipher import decrypt_stream
from src.modules.platform.infrastructure.security.backup_cipher import encrypt_archive
from src.modules.platform.infrastructure.security.backup_cipher import encrypt_chunks
from src.modules.platform.infrastructure.security.backup_cipher import is_encrypted_archive

KEY = "a-backup-key"


def _decrypt(data: bytes, key: str = KEY) -> bytes:
    return b"".join(decrypt_stream(io.BytesIO(data), key))


class TestRoundTrip:
    @pytest.mark.parametrize("size", [0, 1, 1024, 1024 * 1024, 1024 * 1024 + 1, 3 * 1024 * 1024])
    def test_any_size_comes_back_unchanged(self, size):
        plain = os.urandom(size)

        archive = encrypt_archive(plain, KEY)

        assert is_encrypted_archive(archive)
        assert _decrypt(archive) == plain

    def test_the_input_chunking_does_not_matter(self):
        plain = os.urandom(2 * 1024 * 1024 + 17)
        pieces = [plain[i : i + 7000] for i in range(0, len(plain), 7000)]

        archive = b"".join(encrypt_chunks(pieces, KEY))

        assert _decrypt(archive) == plain

    def test_two_archives_of_the_same_data_differ(self):
        """A fresh salt per archive, so equal dumps never look equal."""
        assert encrypt_archive(b"same", KEY) != encrypt_archive(b"same", KEY)


class TestRefusals:
    def test_the_wrong_key_is_named_as_such(self):
        archive = encrypt_archive(b"secret rows", KEY)

        with pytest.raises(BackupKeyMismatchError):
            _decrypt(archive, "another-key")

    def test_a_flipped_byte_fails_authentication(self):
        archive = bytearray(encrypt_archive(b"secret rows" * 100, KEY))
        archive[-5] ^= 0x01

        with pytest.raises(BackupArchiveError, match="authentication"):
            _decrypt(bytes(archive))

    def test_a_truncated_archive_is_refused(self):
        archive = encrypt_archive(os.urandom(2 * 1024 * 1024), KEY)

        with pytest.raises(BackupArchiveError, match="truncated"):
            _decrypt(archive[:-10])

    def test_an_archive_cut_at_a_frame_boundary_is_refused(self):
        """Dropping the final frame leaves a well-formed prefix, which the
        missing final flag still exposes."""
        archive = encrypt_archive(os.urandom(2 * 1024 * 1024), KEY)
        header = len(backup_cipher.MAGIC) + 16 + 8
        first_frame_end = header + 5 + 1024 * 1024 + 16

        with pytest.raises(BackupArchiveError, match="truncated"):
            _decrypt(archive[:first_frame_end])

    def test_data_after_the_final_frame_is_refused(self):
        archive = encrypt_archive(b"rows", KEY)

        with pytest.raises(BackupArchiveError, match="follows its final part"):
            _decrypt(archive + b"x")

    def test_a_plain_gzip_file_is_not_an_encrypted_archive(self):
        assert not is_encrypted_archive(b"\x1f\x8b\x08\x00")

        with pytest.raises(BackupArchiveError, match="not an encrypted"):
            _decrypt(b"\x1f\x8b\x08\x00" + b"\x00" * 64)
