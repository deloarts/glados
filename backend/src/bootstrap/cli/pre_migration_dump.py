"""
The dump the container entrypoint takes before it applies pending
migrations, run as `admin pre-migration-dump`. A migration that destroys or
garbles data is then undone by restoring this dump with `restore --file`,
whatever the scheduled backups look like.

The command compares the database's alembic revision with the heads of the
migration scripts in the image. Only when they differ, and the database
already holds tables, does it dump: an up to date database needs no dump,
and a fresh install has nothing to lose. The dump uses the same pg_dump call
and archive format as the scheduled backup, encrypted when
SECURITY__BACKUP_ENCRYPTION_KEY is set. Without the key it is written
unencrypted, because it stays on the host's own volume next to the
database it copies and must not stop an upgrade of a deployment that never
configured backups.

The dump goes to BACKUP__PRE_MIGRATION_DUMP_DIR as
`<timestamp>_<revision><suffix>`, written under a temporary name and
renamed once complete, so a dump that is there is whole. Only the newest
BACKUP__PRE_MIGRATION_DUMP_KEEP dumps are kept.

Exit code 0 means a dump was written or none was needed, 1 that the dump
failed, in which case the entrypoint refuses to migrate.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from functools import partial
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_DUMP_SUFFIXES = (".sql.gz", ".sql.gz.enc")


@dataclass(frozen=True)
class SchemaState:
    """The revisions the database is at, the heads the image brings, and
    whether the database holds any table at all."""

    current: frozenset[str]
    heads: frozenset[str]
    has_tables: bool

    @property
    def pending(self) -> bool:
        return self.current != self.heads


def schema_state(db_url: str) -> SchemaState:
    """Reads the database's alembic revision and the image's script heads."""
    from sqlalchemy import create_engine
    from sqlalchemy import inspect
    from sqlalchemy.pool import NullPool

    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory

    config = Config(str(_BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_BACKEND_ROOT / "alembic"))
    heads = frozenset(ScriptDirectory.from_config(config).get_heads())

    engine = create_engine(db_url, poolclass=NullPool)
    try:
        with engine.connect() as connection:
            current = frozenset(MigrationContext.configure(connection).get_current_heads())
            has_tables = bool(inspect(connection).get_table_names())
    finally:
        engine.dispose()
    return SchemaState(current=current, heads=heads, has_tables=has_tables)


def prune(directory: Path, keep: int) -> list[Path]:
    """Deletes all but the newest `keep` dumps in `directory` (at least one
    is always kept) and returns the deleted paths. The timestamp leads every
    name, so name order is age order."""
    dumps = sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.name.endswith(_DUMP_SUFFIXES)
    )
    excess = dumps[: max(0, len(dumps) - max(1, keep))]
    for path in excess:
        path.unlink()
    return excess


def write_dump(directory: Path, name: str, data: bytes) -> Path:
    """Writes `data` to `directory/name` under a temporary name first, so a
    crash never leaves a partial dump behind under the final name. The
    directory and the file are readable by the owner only."""
    directory.mkdir(parents=True, exist_ok=True)
    directory.chmod(0o700)
    final = directory / name
    partial_path = directory / f".{name}.partial"
    descriptor = os.open(partial_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "wb") as out:
        out.write(data)
        out.flush()
        os.fsync(out.fileno())
    partial_path.replace(final)
    return final


async def run() -> int:
    from anyio import to_thread

    from src.modules.platform.adapters.outbound.external.schedules.database_dump import (
        build_archive,
    )
    from src.modules.platform.adapters.outbound.external.schedules.database_dump import (
        dump_database,
    )
    from src.modules.platform.domain.exceptions import BackupError
    from src.modules.platform.infrastructure.config.settings import cfg
    from src.shared_kernel.domain.services.clock import now_utc

    db_url = cfg.database.url
    if not db_url.startswith("postgresql"):
        print("Pre-migration dump: not a Postgres database, nothing to dump.", flush=True)
        return 0

    try:
        state = await to_thread.run_sync(schema_state, db_url)
    except Exception as exc:
        print(
            f"Pre-migration dump FAILED: cannot read the schema revision: {exc}",
            file=sys.stderr,
            flush=True,
        )
        return 1

    if not state.pending:
        print("Pre-migration dump: no pending migration, no dump needed.", flush=True)
        return 0
    if not state.current and not state.has_tables:
        print("Pre-migration dump: empty database, nothing to dump.", flush=True)
        return 0

    revision = "-".join(sorted(state.current)) or "none"
    print(
        f"Pre-migration dump: the database is at {revision}, the image brings "
        f"{', '.join(sorted(state.heads))}. Dumping before the migrations run …",
        flush=True,
    )
    key = cfg.security.backup_encryption_key or None
    if key is None:
        print(
            "Pre-migration dump: SECURITY__BACKUP_ENCRYPTION_KEY is not set, so the dump is "
            "written unencrypted.",
            flush=True,
        )
    directory = Path(cfg.backup.pre_migration_dump_dir)
    try:
        dump = await dump_database(db_url)
        archive = await to_thread.run_sync(partial(build_archive, dump, key))
        name = f"{now_utc().strftime('%Y-%m-%dT%H-%M-%S')}_{revision}{archive.suffix}"
        path = await to_thread.run_sync(write_dump, directory, name, archive.data)
        pruned = await to_thread.run_sync(prune, directory, cfg.backup.pre_migration_dump_keep)
    except (BackupError, OSError) as exc:
        print(f"Pre-migration dump FAILED: {exc}", file=sys.stderr, flush=True)
        return 1

    print(f"Pre-migration dump written: {path} ({len(archive.data):,} bytes).", flush=True)
    for old in pruned:
        print(f"Pre-migration dump: removed the older dump {old.name}.", flush=True)
    return 0
