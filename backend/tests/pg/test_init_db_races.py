"""
Server workers seed the database one at a time under an advisory lock, on a
real Postgres. A worker queued behind the others waits for as long as they
take, past the pool's lock_timeout, instead of failing to boot.
"""

import asyncio
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import create_async_engine

from src.bootstrap.adapters.outbound.persistence.init_db import InitDatabase
from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.platform.adapters.outbound.persistence.advisory_lock import AdvisoryLockKey
from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel
from src.modules.platform.adapters.outbound.persistence.repositories.user_repository import (
    SqlAlchemyUserRepository,
)
from src.modules.platform.adapters.outbound.persistence.session import postgres_connect_args
from src.modules.platform.const import SYSTEM_USER
from src.modules.platform.infrastructure.config.settings import cfg
from src.modules.quality.adapters.outbound.persistence.repositories.print_template_repository import (
    SqlAlchemyPrintTemplateRepository,
)
from tests.pg._race import WAIT_SECONDS
from tests.pg._race import sessions
from tests.pg._race import start
from tests.pg._race import wait_for_lock
from tests.pg.conftest import RACE_B

_LOCK_TIMEOUT_SECONDS = 1


@pytest.fixture
async def short_lock_timeout_engine(
    _postgres: str, schema_engine: object
) -> AsyncIterator[AsyncEngine]:
    """Like engine_b, with a lock_timeout short enough to outlast quickly."""
    settings = cfg.database.model_copy(update={"lock_timeout_seconds": _LOCK_TIMEOUT_SECONDS})
    engine = create_async_engine(_postgres, connect_args=postgres_connect_args(settings, RACE_B))
    yield engine
    await engine.dispose()


async def _seed(engine: AsyncEngine) -> None:
    async with sessions(engine)() as db:
        await InitDatabase(
            user_repo=SqlAlchemyUserRepository(db),
            admin_settings_repo=SqlAlchemyAdminSettingsRepository(db),
            print_template_repo=SqlAlchemyPrintTemplateRepository(db),
            db=db,
        ).run()


async def test_a_worker_queued_for_the_seed_lock_waits_past_the_lock_timeout(
    engine_a: AsyncEngine, short_lock_timeout_engine: AsyncEngine, watcher: AsyncEngine
) -> None:
    async with engine_a.connect() as holder:
        await holder.execute(
            text("SELECT pg_advisory_xact_lock(:key)"), {"key": int(AdvisoryLockKey.INIT_DB_SEED)}
        )
        seeding = start(_seed(short_lock_timeout_engine))
        await wait_for_lock(watcher, RACE_B)
        await asyncio.sleep(_LOCK_TIMEOUT_SECONDS * 2)
        assert not seeding.done(), seeding.exception() if seeding.done() else None
        await holder.rollback()

    await asyncio.wait_for(seeding, WAIT_SECONDS)
    async with sessions(engine_a)() as db:
        found = await db.scalar(select(UserOrmModel.id).where(UserOrmModel.username == SYSTEM_USER))
    assert found is not None
