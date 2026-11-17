"""
The pg_dump call and the archive format shared by the scheduled database
backup and the pre-migration dump: a plain SQL dump without owners or
privileges, gzip-compressed, and encrypted with the backup key when one is
given. Plain dumps are the format the restore command reads, so every
archive written so far stays restorable.
"""

from __future__ import annotations

import asyncio
import gzip
import os
from dataclasses import dataclass
from urllib.parse import urlparse

from src.modules.platform.domain.exceptions import BackupError
from src.modules.platform.infrastructure.security.backup_cipher import ENCRYPTED_SUFFIX
from src.modules.platform.infrastructure.security.backup_cipher import PLAIN_SUFFIX
from src.modules.platform.infrastructure.security.backup_cipher import encrypt_archive

# A dump that has not finished within this many seconds is treated as failed.
# Without a limit a single stuck pg_dump wedges its worker forever, and there
# is no operator at the other end to notice: the scheduler runs headless.
DUMP_TIMEOUT_SECONDS = 1800

ENCRYPTED_CONTENT_TYPE = "application/octet-stream"
PLAIN_CONTENT_TYPE = "application/gzip"


@dataclass(frozen=True)
class Archive:
    """A finished archive: its bytes, the file suffix that names its format
    and the content type it is stored with."""

    data: bytes
    suffix: str
    content_type: str

    @property
    def encrypted(self) -> bool:
        return self.suffix == ENCRYPTED_SUFFIX


def pg_connection_env(db_url: str) -> tuple[list[str], dict[str, str]]:
    """The libpq connection arguments for `db_url` and an environment that
    carries its password, for pg_dump and psql alike."""
    parsed = urlparse(db_url)
    env = os.environ.copy()
    if parsed.password:
        env["PGPASSWORD"] = parsed.password
    args = [
        "-h",
        parsed.hostname or "localhost",
        "-p",
        str(parsed.port or 5432),
        "-U",
        parsed.username or "postgres",
    ]
    return args, env


async def dump_database(db_url: str, *, timeout_seconds: int = DUMP_TIMEOUT_SECONDS) -> bytes:
    """Runs pg_dump against `db_url` and returns the plain SQL dump. Raises
    BackupError when pg_dump is missing, fails or runs out of time."""
    connection_args, env = pg_connection_env(db_url)
    database = urlparse(db_url).path.lstrip("/")
    try:
        process = await asyncio.create_subprocess_exec(
            "pg_dump",
            "--no-owner",
            "--no-acl",
            # Never prompt: with no PGPASSWORD (or a URL that carries none)
            # pg_dump would otherwise block on a terminal password prompt
            # nobody can answer.
            "-w",
            *connection_args,
            database,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
    except FileNotFoundError as e:
        raise BackupError(
            "pg_dump not found. Install postgresql-client in the container "
            "(rebuild after the Dockerfile change) or on the host."
        ) from e
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds)
    except TimeoutError as e:
        process.kill()
        await process.wait()
        raise BackupError(f"pg_dump timed out after {timeout_seconds}s and was killed.") from e
    if process.returncode != 0:
        raise BackupError(f"pg_dump failed: {stderr.decode()}")
    return stdout


def build_archive(dump: bytes, encryption_key: str | None) -> Archive:
    """Compresses the dump and, given a key, encrypts it. CPU-bound, so an
    async caller runs it in a worker thread."""
    compressed = gzip.compress(dump, compresslevel=6)
    if encryption_key is None:
        return Archive(data=compressed, suffix=PLAIN_SUFFIX, content_type=PLAIN_CONTENT_TYPE)
    return Archive(
        data=encrypt_archive(compressed, encryption_key),
        suffix=ENCRYPTED_SUFFIX,
        content_type=ENCRYPTED_CONTENT_TYPE,
    )
