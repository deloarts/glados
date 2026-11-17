"""
Two workers booting at the same time both run InitDatabase. Each seed step
checks for its row and then inserts it, so both can find a row absent and
both insert it; the loser must repeat the pass and succeed instead of
crashing its worker, leaving exactly one system user and one row per
settings singleton.
"""

import asyncio
from pathlib import Path

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine

import src.modules.platform.adapters.outbound.persistence.alembic_imports  # noqa: F401
from src.bootstrap.adapters.outbound.persistence.init_db import InitDatabase
from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.general import (
    AdminGeneralSettingsOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel
from src.modules.platform.adapters.outbound.persistence.repositories.user_repository import (
    SqlAlchemyUserRepository,
)
from src.modules.platform.const import SYSTEM_USER
from src.modules.quality.adapters.outbound.persistence.repositories.print_template_repository import (
    SqlAlchemyPrintTemplateRepository,
)


async def test_two_concurrent_seed_passes_both_succeed(tmp_path: Path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'seed.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def boot() -> None:
        async with sessions() as db:
            await InitDatabase(
                user_repo=SqlAlchemyUserRepository(db),
                admin_settings_repo=SqlAlchemyAdminSettingsRepository(db),
                print_template_repo=SqlAlchemyPrintTemplateRepository(db),
                db=db,
            ).run()

    try:
        await asyncio.gather(boot(), boot())
        async with sessions() as db:
            system_users = await db.scalar(
                select(func.count())
                .select_from(UserOrmModel)
                .where(UserOrmModel.username == SYSTEM_USER)
            )
            general_rows = await db.scalar(
                select(func.count()).select_from(AdminGeneralSettingsOrmModel)
            )
        assert system_users == 1
        assert general_rows == 1
    finally:
        await engine.dispose()
