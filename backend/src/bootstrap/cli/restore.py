"""
Out-of-process database restore command. Run via the container entrypoint:

    docker compose run --rm backend restore --backup backups/db/2026-07-13T02-00-00.sql.gz.enc
    docker compose run --rm -v /srv/dumps:/dumps backend restore --file /dumps/glados.sql.gz.enc

Or, without a host shell (e.g. a Portainer console into the `maintenance`
sidecar profile, never the live `backend`, see docs/OPERATIONS.md section
4.2): a console/`docker exec` skips the entrypoint script, so the `restore`
shorthand doesn't apply there, call the script directly instead:

    /entrypoint.sh restore --backup backups/db/2026-07-13T02-00-00.sql.gz.enc

The restore never writes into the database it replaces. It creates a fresh
database next to it, loads the archive there with psql in a single
transaction that stops at the first error, checks that the result is a
Glados database, and only then swaps it in by renaming: the current
database becomes `<name>_pre_restore_<timestamp>` and the restored one
takes its name. Any failure before the swap drops the fresh database and
leaves the current one untouched, so the command either ends with the
backup's data in place or with an error, never with a half restored
database reported as a success.

`--backup KEY` downloads the archive from the storage configured in the
current database. `--file PATH` reads a local archive instead and needs no
readable database at all, which is the way back when the database is lost
or broken. Both accept plain `.sql.gz` archives and archives encrypted with
SECURITY__BACKUP_ENCRYPTION_KEY; the format is read from the file itself.

The database user needs the right to create databases and to rename the
current one, which the bundled Postgres's POSTGRES_USER has.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import subprocess
import sys
import tempfile
import time
import zlib
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from typing import BinaryIO

if TYPE_CHECKING:
    import psycopg

_READ_BYTES = 1024 * 1024
_MAX_IDENTIFIER_BYTES = 63
# How often the swap retries renaming a database that a just terminated
# connection still holds, and how long it waits between tries.
_RENAME_ATTEMPTS = 10
_RENAME_RETRY_SECONDS = 0.5


class RestoreError(Exception):
    """A restore step failed. The message says what failed and the state the
    databases are left in."""


class _SwapStuckError(RestoreError):
    """The swap moved the current database aside but could neither finish
    nor undo it, so both databases must stay for the operator."""


@dataclass(frozen=True)
class RestoreOutcome:
    """The result of a restore: the database that now holds the backup, the
    name the replaced database is kept under (None when there was none),
    and the schema revision the backup carries."""

    database: str
    previous: str | None
    revision: str


# ── Reading archives ──────────────────────────────────────────────────


def _file_chunks(source: BinaryIO) -> Iterator[bytes]:
    while chunk := source.read(_READ_BYTES):
        yield chunk


def iter_sql(path: Path, encryption_key: str | None) -> Iterator[bytes]:
    """Yields the SQL held by the archive at `path`, plain or encrypted.

    Raises RestoreError for a file that is no backup archive, an encrypted
    archive without the right key, and a damaged or truncated archive. The
    last two can surface only after part of the SQL was yielded, so a
    caller must treat everything it received as void when this raises."""
    from src.modules.platform.infrastructure.security.backup_cipher import GZIP_MAGIC
    from src.modules.platform.infrastructure.security.backup_cipher import BackupArchiveError
    from src.modules.platform.infrastructure.security.backup_cipher import BackupKeyMismatchError
    from src.modules.platform.infrastructure.security.backup_cipher import decrypt_stream
    from src.modules.platform.infrastructure.security.backup_cipher import is_encrypted_archive

    try:
        source = path.open("rb")
    except OSError as exc:
        raise RestoreError(f"Cannot open the archive {str(path)!r}: {exc}") from exc

    with source:
        head = source.read(16)
        source.seek(0)
        compressed: Iterator[bytes]
        if is_encrypted_archive(head):
            if not encryption_key:
                raise RestoreError(
                    "The archive is encrypted, but SECURITY__BACKUP_ENCRYPTION_KEY is not set. "
                    "Set it to the key the archive was written with and run the restore again."
                )
            compressed = decrypt_stream(source, encryption_key)
        elif head.startswith(GZIP_MAGIC):
            compressed = _file_chunks(source)
        else:
            raise RestoreError(
                f"{str(path)!r} is not a Glados backup archive (a .sql.gz or .sql.gz.enc file)."
            )

        # wbits=31 reads the gzip container that build_archive writes.
        decompressor = zlib.decompressobj(wbits=31)
        try:
            for chunk in compressed:
                sql = decompressor.decompress(chunk)
                if sql:
                    yield sql
            tail = decompressor.flush()
        except BackupKeyMismatchError as exc:
            raise RestoreError(
                "The archive was encrypted with a different SECURITY__BACKUP_ENCRYPTION_KEY. "
                "Set the key it was written with and run the restore again."
            ) from exc
        except BackupArchiveError as exc:
            raise RestoreError(str(exc)) from exc
        except zlib.error as exc:
            raise RestoreError(
                f"The archive is damaged: its compressed data is invalid ({exc})."
            ) from exc
        if tail:
            yield tail
        if not decompressor.eof:
            raise RestoreError("The archive is truncated: its compressed data ends early.")


# ── Database names and connections ────────────────────────────────────


def _suffixed(name: str, suffix: str) -> str:
    """`name` plus `suffix`, with `name` shortened so the result stays
    within Postgres's 63 byte identifier limit."""
    room = _MAX_IDENTIFIER_BYTES - len(suffix.encode("utf-8"))
    shortened = name.encode("utf-8")[:room].decode("utf-8", errors="ignore")
    return shortened + suffix


def _libpq_url(db_url: str, database: str) -> str:
    """`db_url` as a plain libpq URL for `database`, which psycopg accepts."""
    from sqlalchemy.engine import make_url

    return (
        make_url(db_url)
        .set(drivername="postgresql", database=database)
        .render_as_string(hide_password=False)
    )


def target_database(db_url: str) -> str:
    """The database name in `db_url`. Raises RestoreError for anything but
    a Postgres URL that names a database."""
    from sqlalchemy.engine import make_url

    url = make_url(db_url)
    if not url.drivername.startswith("postgresql"):
        raise RestoreError("The restore needs a Postgres DATABASE__URL.")
    if not url.database:
        raise RestoreError("DATABASE__URL names no database to restore into.")
    return url.database


def _maintenance_database(target: str) -> str:
    # Postgres cannot rename the database a session is connected to, so the
    # restore works from another one.
    return "template1" if target == "postgres" else "postgres"


def _connect(db_url: str, database: str) -> psycopg.Connection:
    import psycopg

    try:
        return psycopg.connect(_libpq_url(db_url, database), autocommit=True)
    except psycopg.Error as exc:
        raise RestoreError(
            f"Cannot connect to the database {database!r}: {_one_line(exc)}"
        ) from exc


def _one_line(exc: BaseException) -> str:
    text = str(exc).strip()
    return text.splitlines()[0] if text else type(exc).__name__


def _exists(admin: psycopg.Connection, database: str) -> bool:
    row = admin.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database,)).fetchone()
    return row is not None


def _free_name(admin: psycopg.Connection, base: str) -> str:
    """`base`, or `base` with a counter when a database of that name exists,
    so two restores within one second never collide."""
    name = base
    counter = 2
    while _exists(admin, name):
        name = _suffixed(base, f"_{counter}")
        counter += 1
    return name


def _create_database(admin: psycopg.Connection, name: str, like: str) -> None:
    """Creates the empty database `name`, with the encoding and locale of
    `like` when that database exists, so text sorts as it did before."""
    from psycopg import sql

    row = admin.execute(
        "SELECT pg_encoding_to_char(encoding), datcollate, datctype FROM pg_database "
        "WHERE datname = %s",
        (like,),
    ).fetchone()
    statement = sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(name))
    if row is not None:
        encoding, collate, ctype = row
        statement = sql.SQL("{} ENCODING {} LC_COLLATE {} LC_CTYPE {}").format(
            statement, sql.Literal(encoding), sql.Literal(collate), sql.Literal(ctype)
        )
    else:
        statement = sql.SQL("{} ENCODING 'UTF8'").format(statement)
    admin.execute(statement)


def _drop_database(admin: psycopg.Connection, name: str) -> None:
    from psycopg import sql

    admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))


def _terminate_connections(admin: psycopg.Connection, database: str) -> int:
    rows = admin.execute(
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        "WHERE datname = %s AND pid <> pg_backend_pid()",
        (database,),
    ).fetchall()
    return len(rows)


def _set_allow_connections(admin: psycopg.Connection, database: str, allowed: bool) -> None:
    from psycopg import sql

    admin.execute(
        sql.SQL("ALTER DATABASE {} WITH ALLOW_CONNECTIONS {}").format(
            sql.Identifier(database), sql.SQL("true" if allowed else "false")
        )
    )


def _rename(admin: psycopg.Connection, old: str, new: str) -> None:
    """Renames `old`, terminating whatever connection still holds it and
    retrying while a terminated one has not exited yet."""
    import psycopg
    from psycopg import sql

    statement = sql.SQL("ALTER DATABASE {} RENAME TO {}").format(
        sql.Identifier(old), sql.Identifier(new)
    )
    for attempt in range(_RENAME_ATTEMPTS):
        _terminate_connections(admin, old)
        try:
            admin.execute(statement)
            return
        except psycopg.errors.ObjectInUse:
            if attempt == _RENAME_ATTEMPTS - 1:
                raise
            time.sleep(_RENAME_RETRY_SECONDS)


# ── The restore ───────────────────────────────────────────────────────

# pg_dump 17, which the backend image ships, writes this setting into every
# dump's preamble, and a Postgres older than 17 refuses it. The restore
# stops at the first error, so it drops the line for such a server; the
# setting only lifts a timeout the restore never runs into.
_TRANSACTION_TIMEOUT_LINE = b"\nSET transaction_timeout = 0;\n"
_PREAMBLE_BYTES = 64 * 1024


def adapt_to_server(chunks: Iterator[bytes], server_version: int) -> Iterator[bytes]:
    """Yields the SQL from `chunks`, without the settings a server of
    `server_version` (as libpq reports it, e.g. 160004) does not know. Only
    the preamble is searched, where pg_dump writes its settings."""
    if server_version >= 170000:
        yield from chunks
        return
    preamble = b""
    for chunk in chunks:
        if len(preamble) < _PREAMBLE_BYTES:
            preamble += chunk
            continue
        if preamble:
            yield preamble.replace(_TRANSACTION_TIMEOUT_LINE, b"\n", 1)
            preamble = b""
        yield chunk
    if preamble:
        yield preamble.replace(_TRANSACTION_TIMEOUT_LINE, b"\n", 1)


def _load(db_url: str, database: str, sql_chunks: Iterator[bytes]) -> None:
    """Feeds the SQL into psql against `database`, in one transaction that
    stops at the first error. Raises RestoreError when psql or the archive
    fails; psql is killed then rather than given an end of input, because
    an end of input would commit the part loaded so far."""
    from src.modules.platform.adapters.outbound.external.schedules.database_dump import (
        pg_connection_env,
    )

    connection_args, env = pg_connection_env(db_url)
    command = [
        "psql",
        "-X",
        "-q",
        "-w",
        "-v",
        "ON_ERROR_STOP=1",
        "--single-transaction",
        *connection_args,
        "-d",
        database,
    ]
    with tempfile.TemporaryFile() as stderr:
        try:
            process = subprocess.Popen(
                command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=stderr, env=env
            )
        except FileNotFoundError as exc:
            raise RestoreError("psql not found. Install postgresql-client.") from exc
        assert process.stdin is not None

        def psql_error() -> RestoreError:
            stderr.seek(0)
            detail = stderr.read().decode("utf-8", errors="replace").strip()
            return RestoreError(
                f"psql stopped with exit code {process.returncode}:\n{detail or '(no output)'}"
            )

        try:
            for chunk in sql_chunks:
                process.stdin.write(chunk)
        except BrokenPipeError:
            process.wait()
            raise psql_error() from None
        except BaseException:
            process.kill()
            process.wait()
            raise
        with contextlib.suppress(BrokenPipeError):
            process.stdin.close()
        if process.wait() != 0:
            raise psql_error()


def _verify(db_url: str, database: str) -> str:
    """The schema revision of the restored database. Raises RestoreError
    when it carries none, which no complete Glados dump lacks."""
    with _connect(db_url, database) as connection:
        row = connection.execute("SELECT to_regclass('public.alembic_version')").fetchone()
        if row is None or row[0] is None:
            raise RestoreError(
                "The restored data has no alembic_version table, so the archive is no "
                "complete Glados database."
            )
        versions = [
            str(version)
            for (version,) in connection.execute(
                "SELECT version_num FROM public.alembic_version ORDER BY version_num"
            ).fetchall()
        ]
    if not versions:
        raise RestoreError("The restored alembic_version table is empty.")
    return ", ".join(versions)


def _swap(admin: psycopg.Connection, target: str, restored: str, stamp: str) -> str | None:
    """Moves the current database aside and the restored one into its
    place. Returns the name the current database is kept under, or None
    when there was none."""
    import psycopg

    previous: str | None = None
    if _exists(admin, target):
        previous = _free_name(admin, _suffixed(target, f"_pre_restore_{stamp}"))
        try:
            # No new connection may slip in between closing the open ones
            # and the rename.
            _set_allow_connections(admin, target, False)
            closed = _terminate_connections(admin, target)
            if closed:
                print(f"Closed {closed} open connection(s) to {target!r}.", flush=True)
            _rename(admin, target, previous)
        except psycopg.Error as exc:
            with contextlib.suppress(psycopg.Error):
                _set_allow_connections(admin, target, True)
            raise RestoreError(
                f"Could not move the current database {target!r} aside: {_one_line(exc)}. "
                "It is unchanged."
            ) from exc
        _set_allow_connections(admin, previous, True)

    try:
        _rename(admin, restored, target)
    except psycopg.Error as exc:
        detail = _one_line(exc)
        if previous is not None:
            try:
                _rename(admin, previous, target)
            except psycopg.Error as undo:
                raise _SwapStuckError(
                    f"Could not rename the restored database to {target!r} ({detail}), and "
                    f"moving the previous database back failed too ({_one_line(undo)}). "
                    f"The previous data is in {previous!r} and the restored data in "
                    f"{restored!r}; rename one of them to {target!r} by hand."
                ) from exc
        raise RestoreError(
            f"Could not rename the restored database to {target!r}: {detail}. "
            f"{target!r} is unchanged."
        ) from exc
    return previous


def restore_archive(
    path: Path, db_url: str, encryption_key: str | None, *, stamp: str
) -> RestoreOutcome:
    """Restores the archive at `path` into the database `db_url` names, by
    loading a fresh database and swapping it in. `stamp` names the fresh
    and the kept database. Raises RestoreError on any failure, after which
    the database `db_url` names is as it was."""
    target = target_database(db_url)
    with _connect(db_url, _maintenance_database(target)) as admin:
        restored = _free_name(admin, _suffixed(target, f"_restore_{stamp}"))
        print(f"Creating the database {restored!r} …", flush=True)
        try:
            _create_database(admin, restored, like=target)
        except Exception as exc:
            raise RestoreError(
                f"Could not create the database {restored!r}: {_one_line(exc)}. The database "
                "user needs the right to create databases."
            ) from exc

        swapped = False
        try:
            print(f"Loading the archive into {restored!r} …", flush=True)
            sql_chunks = adapt_to_server(iter_sql(path, encryption_key), admin.info.server_version)
            _load(db_url, restored, sql_chunks)
            revision = _verify(db_url, restored)
            print(f"Loaded and verified (schema revision {revision}).", flush=True)
            previous = _swap(admin, target, restored, stamp)
            swapped = True
        except _SwapStuckError:
            # The restored database holds the only copy under a temporary
            # name now, so it must not be dropped.
            swapped = True
            raise
        finally:
            if not swapped:
                try:
                    _drop_database(admin, restored)
                except Exception as exc:
                    print(
                        f"WARNING: could not drop the incomplete database {restored!r}: "
                        f"{_one_line(exc)}. Drop it by hand.",
                        file=sys.stderr,
                        flush=True,
                    )

    # The swap is done; this only proves the name now opens the restored
    # data before the command reports success.
    try:
        _verify(db_url, target)
    except RestoreError as exc:
        kept = f"The previous database is kept as {previous!r}." if previous else ""
        raise RestoreError(
            f"The swap finished, but {target!r} does not open the restored data: {exc} {kept}"
        ) from exc
    return RestoreOutcome(database=target, previous=previous, revision=revision)


# ── Downloading from storage ──────────────────────────────────────────


async def _download(key: str, destination: Path) -> None:
    """Reads the storage settings from the current database and streams the
    archive to `destination`. Only this part of the restore goes through the
    app's async database and storage layers."""
    from anyio import to_thread

    from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
        SqlAlchemyAdminSettingsRepository,
    )
    from src.modules.platform.adapters.outbound.external.storage.factory import (
        create_storage_adapter,
    )
    from src.modules.platform.adapters.outbound.persistence.session import SessionLocal
    from src.modules.platform.adapters.outbound.persistence.session import engine

    try:
        try:
            async with SessionLocal() as db:
                settings = await SqlAlchemyAdminSettingsRepository(db).get_storage()
        except Exception as exc:
            raise RestoreError(
                "Cannot read the storage settings from the current database "
                f"({_one_line(exc)}). Fetch the archive from the backup storage yourself "
                "and restore it with --file PATH."
            ) from exc
        try:
            stream = await create_storage_adapter(settings).open_stream(key)
            with destination.open("wb") as out:
                async for chunk in stream.chunks:
                    await to_thread.run_sync(out.write, chunk)
        except Exception as exc:
            raise RestoreError(
                f"Cannot download {key!r} from the {settings.provider} storage: {_one_line(exc)}"
            ) from exc
    finally:
        await engine.dispose()


# ── Command line ──────────────────────────────────────────────────────


def _report(outcome: RestoreOutcome, source: str) -> None:
    print(
        f"Database restore complete: {outcome.database!r} now holds {source} "
        f"(schema revision {outcome.revision}).",
        flush=True,
    )
    if outcome.previous is None:
        print(f"There was no database {outcome.database!r} before, so none was kept.", flush=True)
    else:
        print(
            f"The previous database is kept as {outcome.previous!r}. Once the restored data "
            "is confirmed, drop it with:\n"
            f"  docker compose exec postgres psql -U <POSTGRES_USER> -d postgres -c "
            f"'DROP DATABASE \"{outcome.previous}\"'",
            flush=True,
        )
    print(
        "On its next start the backend applies any migration this backup predates, "
        "after taking a pre-migration dump.",
        flush=True,
    )


def _run(args: argparse.Namespace) -> None:
    from src.modules.platform.infrastructure.config.settings import cfg
    from src.shared_kernel.domain.services.clock import now_utc

    stamp = now_utc().strftime("%Y%m%d%H%M%S")
    key = cfg.security.backup_encryption_key
    if args.file is not None:
        path = Path(args.file)
        if not path.is_file():
            raise RestoreError(f"{args.file!r} is no file.")
        outcome = restore_archive(path, cfg.database.url, key, stamp=stamp)
        _report(outcome, repr(args.file))
        return

    from src.bootstrap.registrations import register_all

    register_all()
    with tempfile.TemporaryDirectory(prefix="glados-restore-") as scratch:
        path = Path(scratch) / "archive"
        print(f"Downloading {args.backup!r} …", flush=True)
        asyncio.run(_download(args.backup, path))
        print(f"Downloaded {path.stat().st_size:,} bytes.", flush=True)
        outcome = restore_archive(path, cfg.database.url, key, stamp=stamp)
    _report(outcome, repr(args.backup))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="restore",
        description="Restore a Glados database backup into a fresh database and swap it in.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  docker compose run --rm backend restore \\\n"
            "      --backup backups/db/2026-07-13T02-00-00.sql.gz.enc\n"
            "  docker compose run --rm -v /srv/dumps:/dumps backend restore \\\n"
            "      --file /dumps/2026-07-13T02-00-00.sql.gz.enc\n"
            "\n"
            "Without a host shell (e.g. Portainer console into the `maintenance`\n"
            "sidecar, see docs/OPERATIONS.md section 4.2):\n"
            "  /entrypoint.sh restore --backup backups/db/2026-07-13T02-00-00.sql.gz.enc"
        ),
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--backup",
        metavar="KEY",
        help="Storage key of the archive to restore, as the Backups tab shows it. The "
        "storage settings are read from the current database.",
    )
    source.add_argument(
        "--file",
        metavar="PATH",
        help="A local archive (.sql.gz or .sql.gz.enc) inside the container. Needs no "
        "readable database, so it also restores a lost one.",
    )
    args = parser.parse_args(argv)

    try:
        _run(args)
    except RestoreError as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        print("Database restore FAILED.", file=sys.stderr, flush=True)
        sys.exit(1)
    except Exception as exc:
        # Every step before the swap drops its fresh database on the way
        # out, so an unexpected error leaves the current database as it was.
        print(f"ERROR: unexpected failure: {exc!r}", file=sys.stderr, flush=True)
        print("Database restore FAILED.", file=sys.stderr, flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
