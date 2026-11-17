"""
Opt-in integration test for the full Alembic migration chain against a
REAL Postgres: skipped unless env GLADOS_TEST_PG_URL is set, same
pattern as test_advisory_lock_postgres.py (see that module's docstring for
why this repo needs a real-Postgres opt-in tier at all). The default
suite builds its schema straight from `Base.metadata.create_all` on
SQLite (tests/integration/conftest.py's `_schema` fixture), and
test_alembic_migrations.py applies the chain to SQLite only, so nothing
else proves the migration chain works on Postgres, or that it produces
the schema the ORM models describe.

This test proves two things: that `alembic upgrade head` succeeds end to
end against Postgres, and that the resulting schema matches the ORM
metadata exactly, modulo the objects declared in
`autogenerate_filters.HAND_MAINTAINED_OBJECTS`. A gap in that exclusion
list means a developer's `alembic revision --autogenerate` against a real
database would propose spurious drop/add operations for hand-maintained
indexes (trigram GIN indexes created via raw `op.execute()`, never
declared on any model); this test is the regression net for that list
staying complete as new hand-maintained objects are added.

This file opens its own engine, entirely separate from
tests/integration/conftest.py's `_guard_throwaway_database`, which only
ever inspects the app's own SQLite engine (built from `DATABASE__URL`,
untouched by GLADOS_TEST_PG_URL). The safety guard here is
`_assert_database_is_empty`: the database GLADOS_TEST_PG_URL names must
not contain a single table before this test touches it, or it fails
loudly instead of upgrading/downgrading a real, populated database.
Teardown drops every table the migration chain created, `alembic_version`
included, so the database is left empty again regardless of whether the
test passed, and never touches anything it did not create itself.
"""

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy import inspect
from sqlalchemy import text
from sqlalchemy.engine import Connection

# Populates Base.metadata with every ORM model, the same import env.py
# uses; without it target_metadata would be empty and compare_metadata
# would report every table in the database as "should not exist".
import src.modules.platform.adapters.outbound.persistence.alembic_imports  # noqa: F401
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config as AlembicConfig
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from src.modules.platform.adapters.outbound.persistence.autogenerate_filters import (
    compare_server_default,
)
from src.modules.platform.adapters.outbound.persistence.autogenerate_filters import include_object
from src.modules.platform.adapters.outbound.persistence.models.base import Base

_PG_URL = os.environ.get("GLADOS_TEST_PG_URL")

pytestmark = pytest.mark.skipif(
    not _PG_URL,
    reason="set GLADOS_TEST_PG_URL to a real, empty Postgres database to run this test",
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ALEMBIC_INI = _REPO_ROOT / "alembic.ini"
_ALEMBIC_SCRIPT_LOCATION = _REPO_ROOT / "alembic"


def _assert_database_is_empty(connection: Connection) -> None:
    existing_tables = inspect(connection).get_table_names(schema="public")
    if existing_tables:
        pytest.fail(
            "GLADOS_TEST_PG_URL must point at an empty throwaway database, found "
            f"existing tables in schema 'public': {existing_tables}"
        )


def _alembic_config(connection: Connection) -> AlembicConfig:
    """A Config wired the way alembic/env.py's `run_migrations_online`
    expects a programmatic caller to hand in a connection: absolute paths
    (this test's working directory is not guaranteed to be the repo root)
    and `attributes["connection"]` set, so env.py reuses this connection
    instead of building its own engine from `sqlalchemy.url`."""
    config = AlembicConfig(str(_ALEMBIC_INI))
    config.set_main_option("script_location", str(_ALEMBIC_SCRIPT_LOCATION))
    config.attributes["connection"] = connection
    return config


def _metadata_diff(connection: Connection) -> list[object]:
    migration_context = MigrationContext.configure(
        connection,
        opts={"compare_server_default": compare_server_default, "include_object": include_object},
    )
    return list(compare_metadata(migration_context, Base.metadata))


def _drop_everything(connection: Connection) -> None:
    """Drops every table the migration chain created, `alembic_version`
    included, so the database is empty again. Uses the reflected table
    list rather than `Base.metadata.drop_all()` alone: migrations can
    create objects that are not declared on any ORM model (this repo's
    hand-maintained trigram indexes live on real tables so drop_all would
    catch those, but alembic_version itself never has a model), so only
    reflection is guaranteed to see everything that was actually created.
    Leaves the `pg_trgm` extension in place, that is shared infrastructure
    this test did not create.
    """
    connection.rollback()
    table_names = inspect(connection).get_table_names(schema="public")
    if not table_names:
        return
    quoted = ", ".join(f'"{name}"' for name in table_names)
    connection.execute(text(f"DROP TABLE IF EXISTS {quoted} CASCADE"))  # reflected names
    connection.commit()


def test_migration_chain_upgrades_cleanly_and_matches_orm_metadata() -> None:
    engine = create_engine(_PG_URL)
    try:
        with engine.connect() as connection:
            _assert_database_is_empty(connection)
            config = _alembic_config(connection)
            try:
                command.upgrade(config, "head")

                diff = _metadata_diff(connection)
                assert not diff, (
                    "alembic/env.py's autogenerate exclusion list is incomplete, "
                    f"compare_metadata found {len(diff)} unexpected difference(s): {diff}"
                )

                # Round-trip the newest revision: it must downgrade cleanly, and
                # re-applying it must land back on the exact same schema, not
                # just "upgrade from empty" working. The initial migration
                # refuses to downgrade, so the round trip starts with the
                # first revision after it.
                head = ScriptDirectory.from_config(config).get_current_head()
                if ScriptDirectory.from_config(config).get_revision(head).down_revision:
                    command.downgrade(config, "-1")
                    command.upgrade(config, "head")

                    diff = _metadata_diff(connection)
                    assert not diff, (
                        "schema drifted after downgrading and re-upgrading the newest "
                        f"revision, compare_metadata found: {diff}"
                    )
            finally:
                _drop_everything(connection)
    finally:
        engine.dispose()
