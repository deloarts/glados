"""
Concrete implementation of ISecurityEventRepository using SQLAlchemy.
Appends flush and never commit; the calling use case owns the transaction.
"""

from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.outbound.persistence.date_range import day_after_utc
from src.modules.platform.adapters.outbound.persistence.date_range import day_start_utc
from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.adapters.outbound.persistence.models.security_event_model import (
    SecurityEventOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.statements import fetch_page
from src.modules.platform.adapters.outbound.persistence.tenant_zone import date_filter_zone
from src.modules.platform.domain.entities.security_event import SecurityEvent
from src.modules.platform.domain.value_objects.security_event_type import SecurityEventOutcome
from src.modules.platform.domain.value_objects.security_event_type import SecurityEventType
from src.modules.platform.ports.outbound.repositories.security_event_repository import (
    ISecurityEventRepository,
)
from src.modules.platform.ports.outbound.repositories.security_event_repository import (
    SecurityEventFilterDto,
)


def _orm_to_entity(orm: SecurityEventOrmModel) -> SecurityEvent:
    return SecurityEvent(
        id=orm.id,
        public_id=orm.public_id,
        occurred_at=utc_aware(orm.occurred_at),
        event_type=SecurityEventType(orm.event_type),
        outcome=SecurityEventOutcome(orm.outcome),
        actor_user_id=orm.actor_user_id,
        actor_username=orm.actor_username,
        target_user_id=orm.target_user_id,
        target_username=orm.target_username,
        target_id=orm.target_id,
        client_ip=orm.client_ip,
        user_agent=orm.user_agent,
        detail=dict(orm.detail or {}),
    )


class SqlAlchemySecurityEventRepository(ISecurityEventRepository):
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def append(self, event: SecurityEvent) -> None:
        self._db.add(
            SecurityEventOrmModel(
                public_id=event.public_id,
                occurred_at=event.occurred_at,
                event_type=event.event_type.value,
                outcome=event.outcome.value,
                actor_user_id=event.actor_user_id,
                actor_username=event.actor_username,
                target_user_id=event.target_user_id,
                target_username=event.target_username,
                target_id=event.target_id,
                client_ip=event.client_ip,
                user_agent=event.user_agent,
                detail=event.detail,
            )
        )
        await self._db.flush()

    async def list_page(self, filters: SecurityEventFilterDto) -> tuple[int, list[SecurityEvent]]:
        zone = await date_filter_zone(self._db, filters.occurred_from, filters.occurred_to)
        q = select(SecurityEventOrmModel).order_by(
            SecurityEventOrmModel.occurred_at.desc(), SecurityEventOrmModel.id.desc()
        )
        if filters.event_type is not None:
            q = q.where(SecurityEventOrmModel.event_type == filters.event_type.value)
        if filters.outcome is not None:
            q = q.where(SecurityEventOrmModel.outcome == filters.outcome.value)
        if filters.user_id is not None:
            q = q.where(
                or_(
                    SecurityEventOrmModel.actor_user_id == filters.user_id,
                    SecurityEventOrmModel.target_user_id == filters.user_id,
                )
            )
        if filters.occurred_from:
            q = q.where(
                SecurityEventOrmModel.occurred_at >= day_start_utc(filters.occurred_from, zone)
            )
        if filters.occurred_to:
            q = q.where(
                SecurityEventOrmModel.occurred_at < day_after_utc(filters.occurred_to, zone)
            )

        total, rows = await fetch_page(self._db, q, filters.skip, filters.limit)
        return total, [_orm_to_entity(o) for o in rows]
