"""
IRetentionPurger over the log and audit tables. Deletes in id batches with a
commit after each, so no single statement runs long enough to hit
statement_timeout or holds row locks across a large table, and a purge that
stops halfway (shutdown, timeout) has still made durable progress.
"""

from datetime import datetime
from typing import Any
from typing import cast

from sqlalchemy import delete
from sqlalchemy import select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.audit import (
    AdminSettingsAuditOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.agent_call_model import (
    AgentCallOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.agent_created_record_model import (
    AgentCreatedRecordOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.api_key_model import (
    ApiKeyUsageLogOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.idempotency_key_model import (
    IdempotencyKeyOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.log_model import LogOrmModel
from src.modules.platform.adapters.outbound.persistence.models.pat_model import PatUsageLogOrmModel

_BATCH_SIZE = 5_000


class SqlAlchemyRetentionPurger:
    def __init__(self, db: AsyncSession, batch_size: int = _BATCH_SIZE) -> None:
        self._db = db
        self._batch_size = batch_size

    async def purge_logs_before(self, cutoff: datetime) -> int:
        return await self._purge(LogOrmModel.id, LogOrmModel.timestamp, cutoff)

    async def purge_audit_before(self, cutoff: datetime) -> int:
        # The created records belong to their call and are not counted apart;
        # they go first so no database depends on the cascade.
        await self._purge(
            AgentCreatedRecordOrmModel.id, AgentCreatedRecordOrmModel.called_at, cutoff
        )
        return (
            await self._purge(PatUsageLogOrmModel.id, PatUsageLogOrmModel.called_at, cutoff)
            + await self._purge(ApiKeyUsageLogOrmModel.id, ApiKeyUsageLogOrmModel.called_at, cutoff)
            + await self._purge(AgentCallOrmModel.id, AgentCallOrmModel.called_at, cutoff)
            + await self._purge(
                AdminSettingsAuditOrmModel.id, AdminSettingsAuditOrmModel.changed_at, cutoff
            )
        )

    async def purge_idempotency_keys_before(self, cutoff: datetime) -> int:
        return await self._purge(
            IdempotencyKeyOrmModel.id, IdempotencyKeyOrmModel.created_at, cutoff
        )

    async def _purge(
        self,
        id_column: InstrumentedAttribute[int],
        timestamp_column: InstrumentedAttribute[datetime],
        cutoff: datetime,
    ) -> int:
        table = id_column.class_
        removed = 0
        while True:
            batch = (
                select(id_column)
                .where(timestamp_column < cutoff)
                .limit(self._batch_size)
                .scalar_subquery()
            )
            result = cast(
                CursorResult[Any],
                await self._db.execute(
                    delete(table).where(id_column.in_(batch)),
                    execution_options={"synchronize_session": False},
                ),
            )
            await self._db.commit()
            count = result.rowcount or 0
            removed += count
            if count < self._batch_size:
                return removed
