"""
Concrete implementation of IAgentConsentRepository using SQLAlchemy.
"""

from typing import Any
from typing import cast

from sqlalchemy import CursorResult
from sqlalchemy import delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.adapters.outbound.persistence.models.agent_consent_model import (
    AgentConsentOrmModel,
)
from src.modules.platform.domain.entities.agent_consent import AgentConsent
from src.modules.platform.ports.outbound.repositories.agent_consent_repository import (
    IAgentConsentRepository,
)


def _orm_to_entity(orm: AgentConsentOrmModel) -> AgentConsent:
    consented_at = utc_aware(orm.consented_at)
    assert consented_at is not None  # non-null column
    return AgentConsent(
        id=orm.id,
        public_id=orm.public_id,
        user_id=orm.user_id,
        consent_version=orm.consent_version,
        consented_at=consented_at,
    )


class SqlAlchemyAgentConsentRepository(IAgentConsentRepository):
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def _row_for(self, user_id: int) -> AgentConsentOrmModel | None:
        result = await self._db.execute(
            select(AgentConsentOrmModel).where(AgentConsentOrmModel.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_for_user(self, user_id: int) -> AgentConsent | None:
        orm = await self._row_for(user_id)
        return _orm_to_entity(orm) if orm is not None else None

    async def save(self, consent: AgentConsent) -> AgentConsent:
        orm = await self._row_for(consent.user_id)
        if orm is None:
            orm = AgentConsentOrmModel(user_id=consent.user_id)
            self._db.add(orm)
        orm.consent_version = consent.consent_version
        orm.consented_at = consent.consented_at
        await self._db.flush()
        return _orm_to_entity(orm)

    async def delete_for_user(self, user_id: int) -> bool:
        result = cast(
            CursorResult[Any],
            await self._db.execute(
                delete(AgentConsentOrmModel).where(AgentConsentOrmModel.user_id == user_id)
            ),
        )
        return result.rowcount > 0
