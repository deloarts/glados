"""
Concrete SQLAlchemy implementation of IBackupRunRepository.

try_claim is the exactly-once mechanism the whole design rests on: an
`INSERT ... ON CONFLICT (slot) DO NOTHING RETURNING ...`, dialect-picked so
it works identically on Postgres (prod) and SQLite (tests).
`.returning(BackupRunOrmModel)` with SQLAlchemy 2.0's ORM-enabled INSERT
hands back a fully hydrated ORM instance (Python-side defaults, e.g.
Base.public_id, included) on the row that survived, or nothing at all when
the slot was already claimed. `scalar_one_or_none()` turns that into None
with no second round trip.

Writes never commit; the use cases commit the claim, the stale cleanup and
each finish() in their own short transactions.
"""

from contextlib import AbstractAsyncContextManager
from datetime import datetime
from typing import Any
from typing import cast

from sqlalchemy import CursorResult
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.outbound.persistence.advisory_lock import AdvisoryLockKey
from src.modules.platform.adapters.outbound.persistence.advisory_lock import advisory_lock
from src.modules.platform.adapters.outbound.persistence.models.backup_run_model import (
    BackupRunOrmModel,
)
from src.modules.platform.domain.entities.backup_run import BackupRun
from src.modules.platform.domain.value_objects.backup_run_status import BackupRunStatus
from src.modules.platform.domain.value_objects.backup_run_status import BackupRunTrigger
from src.modules.platform.ports.outbound.repositories.backup_run_repository import STALE_AFTER
from src.shared_kernel.domain.services.clock import now_utc

_STALE_ERROR = "worker died or timed out"


def _to_entity(orm: BackupRunOrmModel) -> BackupRun:
    return BackupRun(
        id=orm.id,
        public_id=orm.public_id,
        slot=orm.slot,
        trigger=BackupRunTrigger(orm.trigger),
        started_at=orm.started_at,
        finished_at=orm.finished_at,
        status=BackupRunStatus(orm.status),
        db_key=orm.db_key,
        files_key=orm.files_key,
        error=orm.error,
        worker=orm.worker,
    )


class SqlAlchemyBackupRunRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def try_claim(
        self, slot: datetime, trigger: BackupRunTrigger, worker: str
    ) -> BackupRun | None:
        dialect = self._db.get_bind().dialect.name
        insert = pg_insert if dialect == "postgresql" else sqlite_insert
        stmt = (
            insert(BackupRunOrmModel)
            .values(
                slot=slot,
                trigger=trigger.value,
                started_at=now_utc(),
                status=BackupRunStatus.RUNNING.value,
                worker=worker,
            )
            .on_conflict_do_nothing(index_elements=["slot"])
            .returning(BackupRunOrmModel)
        )
        orm = (await self._db.execute(stmt)).scalar_one_or_none()
        return _to_entity(orm) if orm is not None else None

    def run_lock(self) -> AbstractAsyncContextManager[bool]:
        # AsyncSession.bind is typed AsyncEngine | AsyncConnection | None;
        # every session this class is constructed with comes from
        # SessionLocal, bound directly to the module-level engine
        # (session.py), so this is always actually an AsyncEngine. See advisory_lock.py for
        # why a dedicated connection (never this class's own `self._db`
        # session) is required here at all.
        return advisory_lock(cast(AsyncEngine, self._db.bind), AdvisoryLockKey.BACKUP_RUN)

    async def finish(
        self,
        run_id: int,
        status: BackupRunStatus,
        db_key: str | None,
        files_key: str | None,
        error: str | None,
    ) -> None:
        orm = await self._db.get(BackupRunOrmModel, run_id)
        if orm is None:
            return  # defensive: the caller always holds the id it just claimed
        orm.status = status.value
        orm.finished_at = now_utc()
        orm.db_key = db_key
        orm.files_key = files_key
        orm.error = error
        await self._db.flush()

    async def latest(self, limit: int) -> list[BackupRun]:
        rows = (
            await self._db.scalars(
                select(BackupRunOrmModel).order_by(BackupRunOrmModel.id.desc()).limit(limit)
            )
        ).all()
        return [_to_entity(r) for r in rows]

    async def last_success(self) -> BackupRun | None:
        return await self._last_with_status(BackupRunStatus.SUCCESS)

    async def last_failure(self) -> BackupRun | None:
        return await self._last_with_status(BackupRunStatus.FAILED)

    async def _last_with_status(self, status: BackupRunStatus) -> BackupRun | None:
        orm = (
            await self._db.scalars(
                select(BackupRunOrmModel)
                .where(BackupRunOrmModel.status == status.value)
                .order_by(BackupRunOrmModel.id.desc())
                .limit(1)
            )
        ).first()
        return _to_entity(orm) if orm is not None else None

    async def is_running(self) -> bool:
        # STALE_AFTER: a `running` row a dead worker never finished must
        # not read as "in progress" forever. See the port's docstring and
        # mark_stale_failed, which is what actually cleans such rows up
        # (this method never writes, it would be surprising for a read to
        # have a side effect); this just keeps that same window from
        # answering 409 in the meantime, on whichever caller asks first.
        cutoff = now_utc() - STALE_AFTER
        row = (
            await self._db.execute(
                select(BackupRunOrmModel.id)
                .where(
                    BackupRunOrmModel.status == BackupRunStatus.RUNNING.value,
                    BackupRunOrmModel.started_at >= cutoff,
                )
                .limit(1)
            )
        ).first()
        return row is not None

    async def mark_stale_failed(self, older_than: datetime) -> int:
        result = cast(
            CursorResult[Any],
            await self._db.execute(
                update(BackupRunOrmModel)
                .where(
                    BackupRunOrmModel.status == BackupRunStatus.RUNNING.value,
                    BackupRunOrmModel.started_at < older_than,
                )
                .values(
                    status=BackupRunStatus.FAILED.value,
                    finished_at=now_utc(),
                    error=_STALE_ERROR,
                )
            ),
        )
        return result.rowcount
