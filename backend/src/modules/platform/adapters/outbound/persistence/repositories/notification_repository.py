"""
Repository for in-app notifications, handling retrieval and status updates.
"""

from sqlalchemy import delete
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.outbound.persistence.models.notification_model import (
    NotificationOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.statements import by_id
from src.modules.platform.adapters.outbound.persistence.statements import count_rows
from src.modules.platform.domain.entities.notification import Notification
from src.modules.platform.domain.value_objects.notification_type import NotificationType
from src.shared_kernel.domain.services.clock import now_utc


def _orm_to_entity(orm: NotificationOrmModel) -> Notification:
    return Notification(
        id=orm.id,
        public_id=orm.public_id,
        user_id=orm.user_id,
        type=NotificationType(orm.type),
        title=orm.title,
        message=orm.message,
        is_read=orm.is_read,
        created_at=orm.created_at,
        demand_item_id=orm.demand_item_id,
        order_id=orm.order_id,
        project_id=orm.project_id,
        product_id=orm.product_id,
        meeting_id=orm.meeting_id,
        source_event_id=orm.source_event_id,
    )


class SqlAlchemyNotificationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_user_id(self, user_id: int, unread_only: bool = False) -> list[Notification]:
        q = select(NotificationOrmModel).where(NotificationOrmModel.user_id == user_id)
        if unread_only:
            q = q.where(NotificationOrmModel.is_read.is_(False))
        rows = (await self._db.scalars(q.order_by(NotificationOrmModel.created_at.desc()))).all()
        return [_orm_to_entity(r) for r in rows]

    async def get_unread_count(self, user_id: int) -> int:
        return await count_rows(
            self._db,
            select(NotificationOrmModel).where(
                NotificationOrmModel.user_id == user_id,
                NotificationOrmModel.is_read.is_(False),
            ),
        )

    async def get_by_id(self, notification_id: int) -> Notification | None:
        orm = await self._db.scalar(by_id(NotificationOrmModel, notification_id).limit(1))
        return _orm_to_entity(orm) if orm else None

    async def exists_by_source_event_id(self, source_event_id: str) -> bool:
        return (
            await self._db.scalar(
                select(NotificationOrmModel.id)
                .where(NotificationOrmModel.source_event_id == source_event_id)
                .limit(1)
            )
            is not None
        )

    async def add_for_event(self, notification: Notification) -> bool:
        """ON CONFLICT DO NOTHING on the unique (source_event_id, user_id)
        index. On Postgres an insert that meets a concurrent uncommitted one
        waits for that transaction to end before it decides."""
        dialect = self._db.get_bind().dialect.name
        insert = pg_insert if dialect == "postgresql" else sqlite_insert
        inserted = await self._db.scalar(
            insert(NotificationOrmModel)
            .values(
                user_id=notification.user_id,
                type=notification.type.value,
                title=notification.title,
                message=notification.message,
                is_read=notification.is_read,
                created_at=notification.created_at or now_utc(),
                demand_item_id=notification.demand_item_id,
                order_id=notification.order_id,
                project_id=notification.project_id,
                product_id=notification.product_id,
                meeting_id=notification.meeting_id,
                source_event_id=notification.source_event_id,
            )
            .on_conflict_do_nothing(index_elements=["source_event_id", "user_id"])
            .returning(NotificationOrmModel.id)
        )
        return inserted is not None

    async def save(self, notification: Notification) -> Notification:
        if notification.id == 0:
            orm = NotificationOrmModel(
                user_id=notification.user_id,
                type=notification.type.value,
                title=notification.title,
                message=notification.message,
                is_read=notification.is_read,
                created_at=notification.created_at or now_utc(),
                demand_item_id=notification.demand_item_id,
                order_id=notification.order_id,
                project_id=notification.project_id,
                product_id=notification.product_id,
                meeting_id=notification.meeting_id,
                source_event_id=notification.source_event_id,
            )
            self._db.add(orm)
            await self._db.flush()
            await self._db.refresh(orm)
            return _orm_to_entity(orm)
        existing = await self._db.scalar(
            select(NotificationOrmModel).where(NotificationOrmModel.id == notification.id).limit(1)
        )
        if not existing:
            raise ValueError(f"Notification id={notification.id} not found.")
        orm = existing
        orm.is_read = notification.is_read
        await self._db.flush()
        await self._db.refresh(orm)
        return _orm_to_entity(orm)

    async def mark_read(self, notification_id: int) -> None:
        orm = await self._db.scalar(by_id(NotificationOrmModel, notification_id).limit(1))
        if orm:
            orm.is_read = True
            await self._db.flush()

    async def mark_all_read(self, user_id: int) -> None:
        await self._db.execute(
            update(NotificationOrmModel)
            .where(
                NotificationOrmModel.user_id == user_id,
                NotificationOrmModel.is_read.is_(False),
            )
            .values(is_read=True)
        )
        await self._db.flush()

    async def delete_by_id(self, notification_id: int) -> None:
        orm = await self._db.scalar(by_id(NotificationOrmModel, notification_id).limit(1))
        if orm:
            await self._db.delete(orm)
            await self._db.flush()

    async def delete_all_by_user_id(self, user_id: int) -> None:
        await self._db.execute(
            delete(NotificationOrmModel).where(NotificationOrmModel.user_id == user_id)
        )
        await self._db.flush()
