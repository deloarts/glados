"""
Concrete implementation of IPatUsageLogRepository using SQLAlchemy.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.outbound.persistence.models.pat_model import PatUsageLogOrmModel
from src.modules.platform.adapters.outbound.persistence.statements import fetch_page
from src.modules.platform.domain.entities.pat_usage_log import PatUsageLogEntry
from src.modules.platform.ports.outbound.repositories.pat_usage_log_repository import (
    IPatUsageLogRepository,
)
from src.modules.platform.ports.outbound.repositories.pat_usage_log_repository import (
    PatUsageLogFilterDto,
)


def _orm_to_entity(orm: PatUsageLogOrmModel) -> PatUsageLogEntry:
    return PatUsageLogEntry(
        id=orm.id,
        public_id=orm.public_id,
        pat_id=orm.pat_id,
        called_at=orm.called_at,
        method=orm.method,
        path=orm.path,
        status_code=orm.status_code,
    )


class SqlAlchemyPatUsageLogRepository(IPatUsageLogRepository):
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def append(self, entry: PatUsageLogEntry) -> PatUsageLogEntry:
        orm = PatUsageLogOrmModel(
            pat_id=entry.pat_id,
            called_at=entry.called_at,
            method=entry.method,
            path=entry.path,
            status_code=entry.status_code,
        )
        self._db.add(orm)
        await self._db.flush()
        await self._db.refresh(orm)
        return _orm_to_entity(orm)

    async def get_by_pat_id(
        self, pat_id: int, filters: PatUsageLogFilterDto
    ) -> tuple[int, list[PatUsageLogEntry]]:
        q = (
            select(PatUsageLogOrmModel)
            .where(PatUsageLogOrmModel.pat_id == pat_id)
            .order_by(PatUsageLogOrmModel.id.desc())
        )
        total, rows = await fetch_page(self._db, q, filters.skip, filters.limit)
        return total, [_orm_to_entity(o) for o in rows]
