"""
Concrete implementation of IMeetingNotificationQueue using SQLAlchemy: one
row per meeting and recipient holds the mentions and todo assignments that
wait to go out as one notification.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.adapters.outbound.persistence.statements import lock_row
from src.modules.workspace.adapters.outbound.persistence.models.meeting_model import (
    MeetingNotificationOrmModel,
)
from src.modules.workspace.domain.entities.meeting import PendingMeetingNotification


def _to_entity(orm: MeetingNotificationOrmModel) -> PendingMeetingNotification:
    return PendingMeetingNotification(
        id=orm.id,
        public_id=orm.public_id,
        meeting_id=orm.meeting_id,
        recipient_id=orm.recipient_id,
        actor_ids=list(orm.actor_ids or []),
        mention_count=orm.mention_count,
        todo_count=orm.todo_count,
        first_at=utc_aware(orm.first_at),
    )


class SqlAlchemyMeetingNotificationQueue:
    """Implements IMeetingNotificationQueue."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def add(
        self,
        *,
        meeting_id: int,
        recipient_id: int,
        actor_id: int,
        mentions: int,
        todos: int,
        now: datetime,
    ) -> None:
        orm = await self._db.scalar(
            select(MeetingNotificationOrmModel).where(
                MeetingNotificationOrmModel.meeting_id == meeting_id,
                MeetingNotificationOrmModel.recipient_id == recipient_id,
            )
        )
        if orm is None:
            self._db.add(
                MeetingNotificationOrmModel(
                    meeting_id=meeting_id,
                    recipient_id=recipient_id,
                    actor_ids=[actor_id],
                    mention_count=mentions,
                    todo_count=todos,
                    first_at=now,
                )
            )
        else:
            await lock_row(self._db, MeetingNotificationOrmModel, orm.id)
            await self._db.refresh(orm)
            actors = list(orm.actor_ids or [])
            if actor_id not in actors:
                # A new list, since the JSON column only sees an assignment.
                orm.actor_ids = [*actors, actor_id]
            orm.mention_count += mentions
            orm.todo_count += todos
        await self._db.flush()

    async def get_due(self, started_before: datetime) -> list[PendingMeetingNotification]:
        rows = await self._db.scalars(
            select(MeetingNotificationOrmModel)
            .where(MeetingNotificationOrmModel.first_at <= started_before)
            .order_by(MeetingNotificationOrmModel.first_at, MeetingNotificationOrmModel.id)
        )
        return [_to_entity(row) for row in rows]

    async def delete(self, pending: PendingMeetingNotification) -> None:
        orm = await self._db.get(MeetingNotificationOrmModel, pending.id)
        if orm is not None:
            await self._db.delete(orm)
            await self._db.flush()
