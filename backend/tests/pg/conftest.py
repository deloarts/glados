"""
The race tests run against a real Postgres, because only Postgres has the
row locks, advisory locks and READ COMMITTED behaviour they exercise; SQLite
ignores FOR UPDATE. They are skipped unless GLADOS_TEST_PG_URL names a
database, for example postgresql+psycopg://glados_ci:glados_ci@localhost:5432/glados_race.

That database must be an empty throwaway one: the session creates every
table from the ORM models (Base.metadata.create_all) and refuses to start
when the public schema already holds a table, so a development or
production database is never touched. Every table is emptied after each
test, and every table is dropped when the session ends, so the database is
empty again afterwards.

Each test gets two independent engines, one per racing request, whose
connections carry the application's server-side timeouts and the
application names glados-race-a and glados-race-b and which raise the
application's ConstraintViolationError on a unique violation, and a third engine that
watches pg_stat_activity to see one request wait for the other's lock. The
engines are built per test, because pytest-asyncio gives every test its own
event loop and an async connection cannot cross loops. The schema is
created and emptied over a synchronous engine, which no loop owns. The
`floor` fixture seeds the rows a test starts from on a session of the first
engine and closes that session at teardown, so no connection stays open in
a transaction past the test.
"""

import importlib
import os
from collections.abc import AsyncIterator
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import Engine
from sqlalchemy import create_engine
from sqlalchemy import inspect
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import create_async_engine

if TYPE_CHECKING:
    from tests.pg._floor import Floor

PG_URL = os.environ.get("GLADOS_TEST_PG_URL")

RACE_A = "glados-race-a"
RACE_B = "glados-race-b"


@pytest.fixture(scope="session")
def _postgres() -> str:
    if not PG_URL:
        pytest.skip("set GLADOS_TEST_PG_URL to an empty throwaway Postgres database")
    if not PG_URL.startswith("postgresql"):
        pytest.fail(f"GLADOS_TEST_PG_URL must name a Postgres database, not {PG_URL!r}.")
    if os.environ.get("PYTEST_XDIST_WORKER"):
        # Every worker would create the schema in the same database, and the
        # tests make their own concurrency, so they run in one process.
        pytest.fail("the race tests share one database; run tests/pg without -n")
    return PG_URL


def _import_all_models() -> None:
    """Loads every model module, so Base.metadata knows every table."""
    from src.modules.platform.adapters.outbound.persistence.alembic_imports import (
        model_module_names,
    )

    for name in model_module_names():
        importlib.import_module(name)


def _drop_everything(engine: Engine) -> None:
    """Drops every table in the public schema, those create_all made and
    any a failed run left behind, so the database is empty again."""
    with engine.begin() as connection:
        names = inspect(connection).get_table_names(schema="public")
        if names:
            quoted = ", ".join(f'"{name}"' for name in names)
            connection.execute(text(f"DROP TABLE IF EXISTS {quoted} CASCADE"))


class DatabaseNotEmptyError(Exception):
    """GLADOS_TEST_PG_URL names a database whose public schema holds tables."""


@contextmanager
def throwaway_schema(url: str) -> Iterator[Engine]:
    """A synchronous engine on the database `url` names, with every table
    created from the models and dropped again on exit. A database that
    already holds a table is refused before anything is created, and then
    nothing is dropped either."""
    from src.modules.platform.adapters.outbound.persistence.models.base import Base

    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            existing = inspect(connection).get_table_names(schema="public")
    except BaseException:
        engine.dispose()
        raise
    if existing:
        engine.dispose()
        raise DatabaseNotEmptyError(
            "GLADOS_TEST_PG_URL must name an empty throwaway database; its public "
            f"schema holds {sorted(existing)}."
        )
    try:
        _import_all_models()
        Base.metadata.create_all(engine)
        yield engine
    finally:
        _drop_everything(engine)
        engine.dispose()


@pytest.fixture(scope="session")
def schema_engine(_postgres: str) -> Iterator[Engine]:
    """The throwaway database's engine, with the schema created on it for
    the whole session and dropped afterwards."""
    try:
        with throwaway_schema(_postgres) as engine:
            yield engine
    except DatabaseNotEmptyError as refused:
        pytest.fail(str(refused))


@pytest.fixture(autouse=True)
def _empty_tables(schema_engine: Engine) -> Iterator[None]:
    """Empties every table after each test, so no test sees another's rows.
    Depending on the schema, it is also what skips every test here when no
    database is named."""
    yield
    with schema_engine.begin() as connection:
        # A session a test left open would otherwise hold the TRUNCATE until
        # the server's idle timeout; a short wait makes such a leak fail fast.
        connection.execute(text("SET LOCAL lock_timeout = '5s'"))
        names = inspect(connection).get_table_names(schema="public")
        if names:
            quoted = ", ".join(f'"{name}"' for name in names)
            connection.execute(text(f"TRUNCATE {quoted} RESTART IDENTITY CASCADE"))


def _engine(url: str, application_name: str) -> AsyncEngine:
    """An engine like the application's: its connections carry the server-side
    timeouts, and a unique violation surfaces as the port's
    ConstraintViolationError, which the numbering retry catches."""
    from src.modules.platform.adapters.outbound.persistence.constraint_violation import (
        register_constraint_violation_translation,
    )
    from src.modules.platform.adapters.outbound.persistence.session import postgres_connect_args
    from src.modules.platform.infrastructure.config.settings import cfg

    engine = create_async_engine(
        url, connect_args=postgres_connect_args(cfg.database, application_name)
    )
    register_constraint_violation_translation(engine.sync_engine)
    return engine


@pytest.fixture
async def engine_a(_postgres: str, schema_engine: Engine) -> AsyncIterator[AsyncEngine]:
    engine = _engine(_postgres, RACE_A)
    yield engine
    await engine.dispose()


@pytest.fixture
async def engine_b(_postgres: str, schema_engine: Engine) -> AsyncIterator[AsyncEngine]:
    engine = _engine(_postgres, RACE_B)
    yield engine
    await engine.dispose()


@pytest.fixture
async def watcher(_postgres: str, schema_engine: Engine) -> AsyncIterator[AsyncEngine]:
    engine = _engine(_postgres, "glados-race-watcher")
    yield engine
    await engine.dispose()


@pytest.fixture
async def floor(engine_a: AsyncEngine) -> AsyncIterator["Floor"]:
    """The seeded rows (tests/pg/_floor.py) on a session of engine_a that
    the floor keeps using for further rows and closes at teardown."""
    from tests.pg._floor import seed
    from tests.pg._race import sessions

    async with sessions(engine_a)() as db:
        yield await seed(db)
