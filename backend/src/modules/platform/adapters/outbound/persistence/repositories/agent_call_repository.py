"""
Concrete implementation of IAgentCallRepository using SQLAlchemy.
"""

from datetime import datetime

from sqlalchemy import ColumnElement
from sqlalchemy import String
from sqlalchemy import cast
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.adapters.outbound.persistence.models.agent_call_model import (
    AgentCallOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.agent_created_record_model import (
    AgentCreatedRecordOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.statements import fetch_page
from src.modules.platform.domain.entities.agent_call import AgentCall
from src.modules.platform.domain.value_objects.agent_call import AgentCallOutcome
from src.modules.platform.domain.value_objects.agent_call import AgentTokenKind
from src.modules.platform.ports.outbound.repositories.agent_call_repository import (
    AgentCallFilterDto,
)
from src.modules.platform.ports.outbound.repositories.agent_call_repository import (
    IAgentCallRepository,
)


def _orm_to_entity(orm: AgentCallOrmModel) -> AgentCall:
    called_at = utc_aware(orm.called_at)
    assert called_at is not None  # non-null column
    return AgentCall(
        id=orm.id,
        public_id=orm.public_id,
        called_at=called_at,
        user_id=orm.user_id,
        token_kind=AgentTokenKind(orm.token_kind),
        pat_id=orm.pat_id,
        api_key_id=orm.api_key_id,
        token_name=orm.token_name,
        tool=orm.tool,
        arguments=dict(orm.arguments or {}),
        outcome=AgentCallOutcome(orm.outcome),
        duration_ms=orm.duration_ms,
        error=orm.error,
        request_id=orm.request_id,
        created_refs=list(orm.created_refs or []),
        idempotency_key=orm.idempotency_key,
    )


def _token_column(kind: AgentTokenKind) -> InstrumentedAttribute[int | None]:
    if kind is AgentTokenKind.PAT:
        return AgentCallOrmModel.pat_id
    return AgentCallOrmModel.api_key_id


def _refs_text() -> ColumnElement[str]:
    return cast(AgentCallOrmModel.created_refs, String)


class SqlAlchemyAgentCallRepository(IAgentCallRepository):
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def append(self, entry: AgentCall) -> AgentCall:
        orm = AgentCallOrmModel(
            called_at=entry.called_at,
            user_id=entry.user_id,
            token_kind=entry.token_kind.value,
            pat_id=entry.pat_id,
            api_key_id=entry.api_key_id,
            token_name=entry.token_name,
            tool=entry.tool,
            arguments=entry.arguments,
            outcome=entry.outcome.value,
            duration_ms=entry.duration_ms,
            error=entry.error,
            request_id=entry.request_id,
            created_refs=list(entry.created_refs),
            idempotency_key=entry.idempotency_key,
        )
        self._db.add(orm)
        await self._db.flush()
        for ref in dict.fromkeys(entry.created_refs):
            self._db.add(
                AgentCreatedRecordOrmModel(call_id=orm.id, ref=ref, called_at=entry.called_at)
            )
        await self._db.flush()
        await self._db.refresh(orm)
        return _orm_to_entity(orm)

    async def get_page(self, filters: AgentCallFilterDto) -> tuple[int, list[AgentCall]]:
        q = select(AgentCallOrmModel)
        if filters.user_id is not None:
            q = q.where(AgentCallOrmModel.user_id == filters.user_id)
        if filters.pat_id is not None:
            q = q.where(AgentCallOrmModel.pat_id == filters.pat_id)
        if filters.api_key_id is not None:
            q = q.where(AgentCallOrmModel.api_key_id == filters.api_key_id)
        if filters.tool is not None:
            q = q.where(AgentCallOrmModel.tool == filters.tool)
        if filters.created_ref is not None:
            q = q.where(
                AgentCallOrmModel.id.in_(
                    select(AgentCreatedRecordOrmModel.call_id).where(
                        AgentCreatedRecordOrmModel.ref == filters.created_ref
                    )
                )
            )
        q = q.order_by(AgentCallOrmModel.id.desc())
        total, rows = await fetch_page(self._db, q, filters.skip, filters.limit)
        return total, [_orm_to_entity(o) for o in rows]

    async def count_since(
        self, kind: AgentTokenKind, token_id: int, since: datetime, *, drafts_only: bool = False
    ) -> int:
        q = (
            select(func.count())
            .select_from(AgentCallOrmModel)
            .where(
                AgentCallOrmModel.token_kind == kind.value,
                _token_column(kind) == token_id,
                AgentCallOrmModel.called_at >= since,
            )
        )
        if drafts_only:
            q = q.where(
                AgentCallOrmModel.outcome == AgentCallOutcome.OK.value,
                _refs_text() != "[]",
            )
        return int((await self._db.execute(q)).scalar_one())

    async def find_by_idempotency_key(
        self, kind: AgentTokenKind, token_id: int, tool: str, key: str
    ) -> AgentCall | None:
        q = (
            select(AgentCallOrmModel)
            .where(
                AgentCallOrmModel.token_kind == kind.value,
                _token_column(kind) == token_id,
                AgentCallOrmModel.tool == tool,
                AgentCallOrmModel.idempotency_key == key,
                AgentCallOrmModel.outcome == AgentCallOutcome.OK.value,
            )
            .order_by(AgentCallOrmModel.id.desc())
            .limit(1)
        )
        orm = (await self._db.execute(q)).scalar_one_or_none()
        return _orm_to_entity(orm) if orm is not None else None

    async def find_creators(self, refs: list[str]) -> dict[str, AgentCall]:
        if not refs:
            return {}
        q = (
            select(AgentCreatedRecordOrmModel.ref, AgentCallOrmModel)
            .join(AgentCallOrmModel, AgentCallOrmModel.id == AgentCreatedRecordOrmModel.call_id)
            .where(AgentCreatedRecordOrmModel.ref.in_(refs))
            .order_by(AgentCreatedRecordOrmModel.id)
        )
        # A repeated reference keeps its first creator.
        result: dict[str, AgentCall] = {}
        for ref, orm in (await self._db.execute(q)).all():
            result.setdefault(ref, _orm_to_entity(orm))
        return result

    async def last_called_at(
        self, kind: AgentTokenKind, token_ids: list[int]
    ) -> dict[int, datetime]:
        if not token_ids:
            return {}
        column = _token_column(kind)
        q = (
            select(column, func.max(AgentCallOrmModel.called_at))
            .where(AgentCallOrmModel.token_kind == kind.value, column.in_(token_ids))
            .group_by(column)
        )
        result: dict[int, datetime] = {}
        for token_id, called_at in (await self._db.execute(q)).all():
            aware = utc_aware(called_at)
            if token_id is not None and aware is not None:
                result[int(token_id)] = aware
        return result
