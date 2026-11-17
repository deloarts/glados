"""
Concrete implementation of IApiKeyUsageLogRepository using SQLAlchemy.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.outbound.persistence.models.api_key_model import (
    ApiKeyUsageLogOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.statements import fetch_page
from src.modules.platform.domain.entities.api_key_usage_log import ApiKeyUsageLogEntry
from src.modules.platform.ports.outbound.repositories.api_key_usage_log_repository import (
    ApiKeyUsageLogFilterDto,
)
from src.modules.platform.ports.outbound.repositories.api_key_usage_log_repository import (
    IApiKeyUsageLogRepository,
)


def _orm_to_entity(orm: ApiKeyUsageLogOrmModel) -> ApiKeyUsageLogEntry:
    return ApiKeyUsageLogEntry(
        id=orm.id,
        public_id=orm.public_id,
        key_id=orm.key_id,
        called_at=orm.called_at,
        method=orm.method,
        path=orm.path,
        status_code=orm.status_code,
    )


class SqlAlchemyApiKeyUsageLogRepository(IApiKeyUsageLogRepository):
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def append(self, entry: ApiKeyUsageLogEntry) -> ApiKeyUsageLogEntry:
        orm = ApiKeyUsageLogOrmModel(
            key_id=entry.key_id,
            called_at=entry.called_at,
            method=entry.method,
            path=entry.path,
            status_code=entry.status_code,
        )
        self._db.add(orm)
        await self._db.flush()
        await self._db.refresh(orm)
        return _orm_to_entity(orm)

    async def get_by_key_id(
        self, key_id: int, filters: ApiKeyUsageLogFilterDto
    ) -> tuple[int, list[ApiKeyUsageLogEntry]]:
        q = (
            select(ApiKeyUsageLogOrmModel)
            .where(ApiKeyUsageLogOrmModel.key_id == key_id)
            .order_by(ApiKeyUsageLogOrmModel.id.desc())
        )
        total, rows = await fetch_page(self._db, q, filters.skip, filters.limit)
        return total, [_orm_to_entity(o) for o in rows]
