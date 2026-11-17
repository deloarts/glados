"""SQLAlchemy repository for user acknowledgements (admin alerts acknowledged by recipients).
Handles recipient state tracking and pending-list filtering."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Select
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.adapters.outbound.persistence.models.acknowledgement_model import (
    AcknowledgementOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.acknowledgement_model import (
    AcknowledgementRecipientOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel
from src.modules.platform.domain.entities.acknowledgement import Acknowledgement
from src.modules.platform.domain.value_objects.acknowledgement_show_when import (
    AcknowledgementShowWhen,
)
from src.modules.platform.domain.value_objects.announcement_severity import AnnouncementSeverity
from src.modules.platform.ports.outbound.repositories.acknowledgement_repository import (
    AcknowledgementRecipientView,
)
from src.modules.platform.ports.outbound.repositories.acknowledgement_repository import (
    AcknowledgementSummary,
)
from src.modules.platform.ports.outbound.repositories.acknowledgement_repository import (
    IAcknowledgementRepository,
)


def _ack_orm_to_entity(orm: AcknowledgementOrmModel) -> Acknowledgement:
    created_at = utc_aware(orm.created_at)
    assert created_at is not None  # non-null column
    return Acknowledgement(
        id=orm.id,
        public_id=orm.public_id,
        text=orm.text,
        severity=AnnouncementSeverity(orm.severity),
        enabled=orm.enabled,
        show_when=AcknowledgementShowWhen(orm.show_when),
        created_at=created_at,
        created_by_id=orm.created_by_id,
    )


class SqlAlchemyAcknowledgementRepository(IAcknowledgementRepository):
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, ack: Acknowledgement, recipient_user_ids: list[int]) -> Acknowledgement:
        orm = AcknowledgementOrmModel(
            text=ack.text,
            severity=ack.severity.value,
            enabled=ack.enabled,
            show_when=ack.show_when.value,
            created_at=ack.created_at,
            created_by_id=ack.created_by_id,
        )
        self._db.add(orm)
        await self._db.flush()  # assigns orm.id before the recipient rows need it as an FK
        for user_id in recipient_user_ids:
            self._db.add(
                AcknowledgementRecipientOrmModel(acknowledgement_id=orm.id, user_id=user_id)
            )
        await self._db.flush()
        await self._db.refresh(orm)
        return _ack_orm_to_entity(orm)

    def _summary_query(self) -> Select[Any]:
        """One SELECT joining every acknowledgement with its creator's
        username and a pre-aggregated recipient-count subquery.
        list_summaries and set_enabled (which needs one freshly-updated
        row back) both build on this rather than each re-deriving it, and
        neither pays an N+1 cost regardless of how many acknowledgements
        or recipients exist. The GROUP BY lives inside the subquery only,
        so the outer query stays a plain one-row-per-acknowledgement join,
        no ambiguity about selecting a whole mapped entity alongside an
        aggregate."""
        counts = (
            select(
                AcknowledgementRecipientOrmModel.acknowledgement_id.label("ack_id"),
                func.count(AcknowledgementRecipientOrmModel.user_id).label("total"),
                func.count(AcknowledgementRecipientOrmModel.acknowledged_at).label("acknowledged"),
            )
            .group_by(AcknowledgementRecipientOrmModel.acknowledgement_id)
            .subquery()
        )
        creator = aliased(UserOrmModel)
        return (
            select(
                AcknowledgementOrmModel,
                creator.username,
                func.coalesce(counts.c.total, 0),
                func.coalesce(counts.c.acknowledged, 0),
            )
            .outerjoin(creator, AcknowledgementOrmModel.created_by_id == creator.id)
            .outerjoin(counts, counts.c.ack_id == AcknowledgementOrmModel.id)
        )

    @staticmethod
    def _row_to_summary(row: Any) -> AcknowledgementSummary:
        ack_orm, created_by_username, total, acknowledged = row
        return AcknowledgementSummary(
            acknowledgement=_ack_orm_to_entity(ack_orm),
            created_by_username=created_by_username,
            recipients_total=int(total or 0),
            recipients_acknowledged=int(acknowledged or 0),
        )

    async def list_summaries(self) -> list[AcknowledgementSummary]:
        rows = (
            await self._db.execute(
                self._summary_query().order_by(AcknowledgementOrmModel.created_at.desc())
            )
        ).all()
        return [self._row_to_summary(r) for r in rows]

    async def get_by_public_id(self, public_id: UUID) -> Acknowledgement | None:
        orm = await self._db.scalar(
            select(AcknowledgementOrmModel)
            .where(AcknowledgementOrmModel.public_id == public_id)
            .limit(1)
        )
        return _ack_orm_to_entity(orm) if orm else None

    async def set_enabled(self, public_id: UUID, enabled: bool) -> AcknowledgementSummary | None:
        orm = await self._db.scalar(
            select(AcknowledgementOrmModel)
            .where(AcknowledgementOrmModel.public_id == public_id)
            .limit(1)
        )
        if orm is None:
            return None
        orm.enabled = enabled
        await self._db.flush()
        row = (
            await self._db.execute(
                self._summary_query().where(AcknowledgementOrmModel.id == orm.id).limit(1)
            )
        ).first()
        assert row is not None  # the row we just flushed
        return self._row_to_summary(row)

    async def delete(self, public_id: UUID) -> bool:
        orm = await self._db.scalar(
            select(AcknowledgementOrmModel)
            .where(AcknowledgementOrmModel.public_id == public_id)
            .limit(1)
        )
        if orm is None:
            return False
        await self._db.delete(orm)  # cascades to recipients, see the ORM relationship's docstring
        await self._db.flush()
        return True

    async def list_recipients(self, ack_id: int) -> list[AcknowledgementRecipientView]:
        rows = (
            await self._db.execute(
                select(
                    AcknowledgementRecipientOrmModel.user_id,
                    UserOrmModel.username,
                    UserOrmModel.full_name,
                    AcknowledgementRecipientOrmModel.acknowledged_at,
                )
                .join(UserOrmModel, UserOrmModel.id == AcknowledgementRecipientOrmModel.user_id)
                .where(AcknowledgementRecipientOrmModel.acknowledgement_id == ack_id)
            )
        ).all()
        views = [
            AcknowledgementRecipientView(
                user_id=r[0], username=r[1], full_name=r[2], acknowledged_at=utc_aware(r[3])
            )
            for r in rows
        ]
        # Pending first, then alphabetically. Done in Python rather than
        # as a SQL ORDER BY on a NULL column: NULL ordering direction
        # (first vs last) differs between SQLite and Postgres, and this
        # list is bounded (one acknowledgement's recipients), so sorting
        # it in memory is simpler than a dialect-specific ORDER BY.
        views.sort(key=lambda v: (v.acknowledged_at is not None, v.full_name.lower()))
        return views

    async def get_pending_for_user(
        self, user_id: int, session_created_at: datetime | None
    ) -> list[Acknowledgement]:
        rows = (
            await self._db.scalars(
                select(AcknowledgementOrmModel)
                .join(
                    AcknowledgementRecipientOrmModel,
                    AcknowledgementRecipientOrmModel.acknowledgement_id
                    == AcknowledgementOrmModel.id,
                )
                .where(
                    AcknowledgementRecipientOrmModel.user_id == user_id,
                    AcknowledgementRecipientOrmModel.acknowledged_at.is_(None),
                    AcknowledgementOrmModel.enabled.is_(True),
                )
                .order_by(AcknowledgementOrmModel.created_at.asc())
            )
        ).all()
        pending: list[Acknowledgement] = []
        for orm in rows:
            if orm.show_when == AcknowledgementShowWhen.IMMEDIATELY.value:
                pending.append(_ack_orm_to_entity(orm))
                continue
            created_at = utc_aware(orm.created_at)
            if (
                session_created_at is not None
                and created_at is not None
                and session_created_at >= created_at
            ):
                pending.append(_ack_orm_to_entity(orm))
        return pending

    async def acknowledge(self, public_id: UUID, user_id: int, now: datetime) -> bool:
        ack_id = await self._db.scalar(
            select(AcknowledgementOrmModel.id).where(
                AcknowledgementOrmModel.public_id == public_id,
                AcknowledgementOrmModel.enabled.is_(True),
            )
        )
        if ack_id is None:
            return False
        recipient = await self._db.scalar(
            select(AcknowledgementRecipientOrmModel)
            .where(
                AcknowledgementRecipientOrmModel.acknowledgement_id == ack_id,
                AcknowledgementRecipientOrmModel.user_id == user_id,
            )
            .limit(1)
        )
        if recipient is None:
            return False
        if recipient.acknowledged_at is None:
            recipient.acknowledged_at = now
            await self._db.flush()
        return True
