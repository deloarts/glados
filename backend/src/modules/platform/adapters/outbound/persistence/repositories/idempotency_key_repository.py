"""
SQLAlchemy repository for idempotency keys. A claim inserts with ON
CONFLICT DO NOTHING on the (user, key) index, so a duplicate inserts
nothing and the request's transaction goes on to read the row already
there. On Postgres an insert that meets a concurrent uncommitted one waits
for that transaction to end before it decides.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.adapters.outbound.persistence.models.idempotency_key_model import (
    IdempotencyKeyOrmModel,
)
from src.modules.platform.domain.entities.idempotency_key import IdempotencyKey
from src.modules.platform.domain.entities.idempotency_key import IdempotencyKeyStatus
from src.modules.platform.domain.entities.idempotency_key import ResourceRef


def _to_entity(orm: IdempotencyKeyOrmModel) -> IdempotencyKey:
    return IdempotencyKey(
        id=orm.id,
        public_id=orm.public_id,
        user_id=orm.user_id,
        key=orm.key,
        route=orm.route,
        request_hash=orm.request_hash,
        status=IdempotencyKeyStatus(orm.status),
        created_at=utc_aware(orm.created_at),
        completed_at=utc_aware(orm.completed_at),
        resources=[ResourceRef(kind=r["kind"], id=int(r["id"])) for r in orm.resources or []],
    )


def _resource_rows(resources: list[ResourceRef]) -> list[dict[str, object]]:
    return [{"kind": r.kind, "id": r.id} for r in resources]


class SqlAlchemyIdempotencyKeyRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def claim(self, record: IdempotencyKey) -> bool:
        dialect = self._db.get_bind().dialect.name
        insert = pg_insert if dialect == "postgresql" else sqlite_insert
        claimed = await self._db.scalar(
            insert(IdempotencyKeyOrmModel)
            .values(
                user_id=record.user_id,
                key=record.key,
                route=record.route,
                request_hash=record.request_hash,
                status=record.status.value,
                resources=_resource_rows(record.resources),
                created_at=record.created_at,
            )
            .on_conflict_do_nothing(index_elements=["user_id", "key"])
            .returning(IdempotencyKeyOrmModel.id)
        )
        if claimed is None:
            return False
        record.id = int(claimed)
        return True

    async def get_by_user_and_key(self, user_id: int, key: str) -> IdempotencyKey | None:
        orm = await self._db.scalar(
            select(IdempotencyKeyOrmModel)
            .where(IdempotencyKeyOrmModel.user_id == user_id, IdempotencyKeyOrmModel.key == key)
            .execution_options(populate_existing=True)
        )
        return _to_entity(orm) if orm is not None else None

    async def mark_completed(
        self, record_id: int, resources: list[ResourceRef], completed_at: datetime
    ) -> None:
        await self._db.execute(
            update(IdempotencyKeyOrmModel)
            .where(IdempotencyKeyOrmModel.id == record_id)
            .values(
                status=IdempotencyKeyStatus.COMPLETED.value,
                resources=_resource_rows(resources),
                completed_at=completed_at,
            )
        )
        await self._db.flush()
