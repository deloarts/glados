"""SQLAlchemy repository for EmailNotification entities, supporting queries by receiver and
batch operations."""

from typing import Literal
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.outbound.persistence.models.email_notification_model import (
    EmailNotificationOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.statements import by_id
from src.modules.platform.domain.entities.email_notification import EmailNotification


def _orm_to_entity(orm: EmailNotificationOrmModel) -> EmailNotification:
    return EmailNotification(
        id=orm.id,
        public_id=orm.public_id,
        reason=cast(Literal["delivered", "meeting"], orm.reason),
        receiver_id=orm.receiver_id,
        demand_item_id=orm.demand_item_id,
        order_item_id=orm.order_item_id,
        meeting_id=orm.meeting_id,
        message=orm.message,
    )


class SqlAlchemyEmailNotificationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_all(self) -> list[EmailNotification]:
        return [
            _orm_to_entity(o)
            for o in (await self._db.scalars(select(EmailNotificationOrmModel))).all()
        ]

    async def get_by_receiver_id(self, receiver_id: int) -> list[EmailNotification]:
        rows = (
            await self._db.scalars(
                select(EmailNotificationOrmModel).where(
                    EmailNotificationOrmModel.receiver_id == receiver_id
                )
            )
        ).all()
        return [_orm_to_entity(r) for r in rows]

    async def get_distinct_receiver_ids(self) -> list[int]:
        rows = (
            await self._db.execute(select(EmailNotificationOrmModel.receiver_id).distinct())
        ).all()
        return [r[0] for r in rows]

    async def save(self, notification: EmailNotification) -> EmailNotification:
        if notification.id == 0:
            orm = EmailNotificationOrmModel(
                reason=notification.reason,
                receiver_id=notification.receiver_id,
                demand_item_id=notification.demand_item_id,
                order_item_id=notification.order_item_id,
                meeting_id=notification.meeting_id,
                message=notification.message,
            )
            self._db.add(orm)
            await self._db.flush()
            await self._db.refresh(orm)
            return _orm_to_entity(orm)
        existing = await self._db.scalar(
            select(EmailNotificationOrmModel)
            .where(EmailNotificationOrmModel.id == notification.id)
            .limit(1)
        )
        if not existing:
            raise ValueError(f"EmailNotificationOrmModel id={notification.id} not found.")
        orm = existing
        orm.reason = notification.reason
        orm.receiver_id = notification.receiver_id
        orm.demand_item_id = notification.demand_item_id
        orm.order_item_id = notification.order_item_id
        orm.meeting_id = notification.meeting_id
        orm.message = notification.message
        await self._db.flush()
        await self._db.refresh(orm)
        return _orm_to_entity(orm)

    async def delete_by_id(self, id: int) -> None:
        orm = await self._db.scalar(by_id(EmailNotificationOrmModel, id).limit(1))
        if orm:
            await self._db.delete(orm)
            await self._db.flush()
