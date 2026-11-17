"""
Runs the real Alembic machinery against a throwaway, file-based SQLite
database created fresh under tmp_path, never a configured one, to catch
drift that the create_all-based schema in tests/integration/conftest.py
cannot see, since that path never touches a migration file at all.

The history starts at a single initial migration whose only Postgres-only
part, the pg_trgm extension and its GIN indexes, is skipped on other
dialects, so the whole chain applies to SQLite. Any later migration that
breaks this, typically a bare op.alter_column() outside
`op.batch_alter_table(...)`, fails here. The "does autogenerate see any
drift" check runs against a real Postgres, the dialect production applies
migrations against, see test_migrations_postgres.py (opt-in via
GLADOS_TEST_PG_URL).

SQLite also proves the revision graph has exactly one head (no accidental
branch), that every migration file defines both upgrade() and downgrade(),
and that the initial migration refuses to be rolled back, since dropping
the whole schema is never a downgrade.
"""

import importlib
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy import inspect

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from src.modules.platform.adapters.outbound.persistence.alembic_imports import model_module_names
from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.infrastructure.config.settings import cfg

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _alembic_config() -> Config:
    config = Config(str(_REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_REPO_ROOT / "alembic"))
    return config


def test_migration_history_has_exactly_one_head() -> None:
    """A second head means a forgotten down_revision, alembic upgrade head
    would silently stop applying the branch nobody merged."""
    script = ScriptDirectory.from_config(_alembic_config())
    heads = script.get_heads()
    assert len(heads) == 1, f"expected exactly one head, found {heads!r}"


def test_every_migration_defines_upgrade_and_downgrade() -> None:
    script = ScriptDirectory.from_config(_alembic_config())
    missing = [
        rev.revision
        for rev in script.walk_revisions()
        if not (
            callable(getattr(rev.module, "upgrade", None))
            and callable(getattr(rev.module, "downgrade", None))
        )
    ]
    assert missing == []


def test_alembic_upgrade_head_creates_every_model_table_on_sqlite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Applies every migration to a throwaway file under tmp_path, never a
    configured database, and checks that the result has exactly the tables
    the ORM models declare.

    alembic/env.py resolves its target URL from `cfg.database.url` (the
    process-wide Settings singleton) afresh on every invocation, not from
    anything set on the Config object built here, so redirecting it means
    monkeypatching that attribute for the duration of this test.
    """
    for name in model_module_names():
        importlib.import_module(name)
    db_path = tmp_path / "alembic_migration_test.db"
    monkeypatch.setattr(cfg.database, "url", f"sqlite:///{db_path}")

    command.upgrade(_alembic_config(), "head")
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as connection:
            tables = set(inspect(connection).get_table_names())
        assert tables == set(Base.metadata.tables) | {"alembic_version"}
    finally:
        engine.dispose()


def test_the_initial_migration_cannot_be_rolled_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "alembic_downgrade_test.db"
    monkeypatch.setattr(cfg.database, "url", f"sqlite:///{db_path}")
    config = _alembic_config()
    script = ScriptDirectory.from_config(config)
    initial = next(rev for rev in script.walk_revisions() if rev.down_revision is None)

    command.upgrade(config, initial.revision)
    with pytest.raises(NotImplementedError):
        command.downgrade(config, "base")
