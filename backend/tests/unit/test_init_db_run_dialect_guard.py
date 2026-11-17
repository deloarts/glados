"""
InitDatabase.run() (called from main.py's lifespan, not the two seeding
methods tested directly in test_init_db_system_user.py /
test_init_db_seed_defaults.py) takes a Postgres advisory lock first, to
serialize seeding across gunicorn workers. That lock statement (`SELECT
pg_advisory_xact_lock(...)`) does not exist on SQLite (the throwaway
database this whole test suite runs against, per tests/conftest.py), so
run() skips it on any other dialect; unguarded, `run()` would crash with
sqlite3.OperationalError the moment it touched a non-Postgres database.
This test proves `run()` itself works end-to-end against a real SQLite
session, the same dialect-guard pattern advisory_lock.py uses (see
test_advisory_lock.py) for the same reason: SQLite is single-process, so
there is nothing to serialize and no primitive to serialize it with.

A real session, not a fake: whether the guard takes the right branch is a
claim about `Session.get_bind().dialect.name` actually resolving to
"sqlite" and the seeding queries actually running against it, not
something a hand-rolled fake session could prove (same reasoning as
test_event_outbox.py's real-SQLite test).
"""

import importlib

from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from src.bootstrap.adapters.outbound.persistence.init_db import InitDatabase
from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.platform.adapters.outbound.persistence.alembic_imports import model_module_names
from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.adapters.outbound.persistence.repositories.user_repository import (
    SqlAlchemyUserRepository,
)
from src.modules.platform.const import SYSTEM_USER
from src.modules.quality.adapters.outbound.persistence.repositories.print_template_repository import (
    SqlAlchemyPrintTemplateRepository,
)


def _import_all_models() -> None:
    """Model modules are not imported by the package's __init__, so
    Base.metadata is empty until each one is loaded (same helper as
    tests/integration/conftest.py's _import_all_models)."""
    for name in model_module_names():
        importlib.import_module(name)


async def _engine() -> AsyncEngine:
    """An in-memory SQLite database with the full schema. StaticPool keeps
    every session on the one connection, which is the whole database."""
    _import_all_models()
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine


async def test_run_seeds_a_sqlite_database_without_crashing_on_the_postgres_only_lock():
    engine = await _engine()
    session_factory = async_sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    async with session_factory() as db:
        await InitDatabase(
            user_repo=SqlAlchemyUserRepository(db),
            admin_settings_repo=SqlAlchemyAdminSettingsRepository(db),
            print_template_repo=SqlAlchemyPrintTemplateRepository(db),
            db=db,
        ).run()
        await db.commit()

    # Both seeding steps actually ran, not just "didn't raise".
    async with session_factory() as db:
        assert await SqlAlchemyUserRepository(db).get_by_username(SYSTEM_USER) is not None
        assert await SqlAlchemyAdminSettingsRepository(db).get_security() is not None


async def test_run_is_idempotent_on_sqlite():
    """Safe to call on every startup (module docstring, point 1): a second
    run against the same already-seeded database neither raises nor
    re-seeds (existing rows are left alone; see
    test_init_db_seed_defaults.py's own cross-cutting rule test)."""
    engine = await _engine()
    session_factory = async_sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    for _ in range(2):
        async with session_factory() as db:
            await InitDatabase(
                user_repo=SqlAlchemyUserRepository(db),
                admin_settings_repo=SqlAlchemyAdminSettingsRepository(db),
                print_template_repo=SqlAlchemyPrintTemplateRepository(db),
                db=db,
            ).run()
            await db.commit()

    async with session_factory() as db:
        assert await SqlAlchemyUserRepository(db).get_by_username(SYSTEM_USER) is not None
