"""
Concrete implementation of IPdmSyncRunRepository using SQLAlchemy.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import asc
from sqlalchemy import delete
from sqlalchemy import desc
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.external_data.adapters.outbound.persistence.models.pdm_sync_run_model import (
    PdmSyncRunEntryOrmModel,
)
from src.modules.external_data.adapters.outbound.persistence.models.pdm_sync_run_model import (
    PdmSyncRunOrmModel,
)
from src.modules.external_data.domain.entities.pdm_sync_run import PdmSyncRun
from src.modules.external_data.domain.entities.pdm_sync_run import PdmSyncRunEntry
from src.modules.external_data.domain.value_objects.pdm_sync_trigger import PdmSyncTrigger
from src.modules.external_data.ports.outbound.repositories.pdm_sync_run_repository import (
    PdmSyncRunFilterDto,
)
from src.modules.platform.adapters.outbound.persistence.date_range import day_after_utc
from src.modules.platform.adapters.outbound.persistence.date_range import day_start_utc
from src.modules.platform.adapters.outbound.persistence.like_escape import contains_ci
from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.adapters.outbound.persistence.statements import by_id
from src.modules.platform.adapters.outbound.persistence.statements import fetch_page
from src.modules.platform.adapters.outbound.persistence.tenant_zone import date_filter_zone


def _run_to_entity(orm: PdmSyncRunOrmModel) -> PdmSyncRun:
    return PdmSyncRun(
        id=orm.id,
        public_id=orm.public_id,
        started_at=utc_aware(orm.started_at),
        finished_at=utc_aware(orm.finished_at),
        trigger=PdmSyncTrigger(orm.trigger),
        files_seen=orm.files_seen,
        changed=orm.changed,
        ingested=orm.ingested,
        skipped=orm.skipped,
        conflicts=orm.conflicts,
        errors=orm.errors,
        missing=orm.missing,
        error=orm.error,
        summary=orm.summary,
        folders_walked=orm.folders_walked,
        folders_skipped_cold=orm.folders_skipped_cold,
        phase=orm.phase,
        current_path=orm.current_path,
        files_queued=orm.files_queued,
        files_processed=orm.files_processed,
        progress_at=utc_aware(orm.progress_at),
        change_reason=orm.change_reason,
        change_state=orm.change_state,
        requested_by_name=orm.requested_by_name,
    )


def _run_to_dict(run: PdmSyncRun) -> dict[str, Any]:
    return {
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "trigger": run.trigger.value,
        "files_seen": run.files_seen,
        "changed": run.changed,
        "ingested": run.ingested,
        "skipped": run.skipped,
        "conflicts": run.conflicts,
        "errors": run.errors,
        "missing": run.missing,
        "error": run.error,
        "summary": run.summary,
        "folders_walked": run.folders_walked,
        "folders_skipped_cold": run.folders_skipped_cold,
        "phase": run.phase,
        "current_path": run.current_path,
        "files_queued": run.files_queued,
        "files_processed": run.files_processed,
        "progress_at": run.progress_at,
        "change_reason": run.change_reason,
        "change_state": run.change_state,
        "requested_by_name": run.requested_by_name,
    }


def _entry_to_entity(orm: PdmSyncRunEntryOrmModel) -> PdmSyncRunEntry:
    return PdmSyncRunEntry(
        id=orm.id,
        public_id=orm.public_id,
        run_id=orm.run_id,
        vault_id=orm.vault_id,
        file_id=orm.file_id,
        name=orm.name,
        path=orm.path,
        kind=orm.kind,
        action=orm.action,
        item_id=orm.item_id,
        message=orm.message,
        created_at=utc_aware(orm.created_at),
    )


class SqlAlchemyPdmSyncRunRepository:
    """Implements IPdmSyncRunRepository."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def start(self, run: PdmSyncRun) -> PdmSyncRun:
        orm = PdmSyncRunOrmModel(**_run_to_dict(run))
        self._db.add(orm)
        await self._db.flush()
        await self._db.refresh(orm)
        return _run_to_entity(orm)

    async def finish(self, run: PdmSyncRun) -> None:
        await self._write(run)

    async def save_progress(self, run: PdmSyncRun) -> None:
        await self._write(run)

    async def latest_unfinished(self, triggers: list[str]) -> PdmSyncRun | None:
        orm = await self._db.scalar(
            select(PdmSyncRunOrmModel)
            .where(
                PdmSyncRunOrmModel.trigger.in_(triggers),
                PdmSyncRunOrmModel.finished_at.is_(None),
            )
            .order_by(desc(PdmSyncRunOrmModel.started_at))
            .limit(1)
        )
        return _run_to_entity(orm) if orm else None

    async def recent_entries(self, limit: int) -> list[PdmSyncRunEntry]:
        # Insertion order, newest first, served by the primary key index.
        rows = (
            await self._db.scalars(
                select(PdmSyncRunEntryOrmModel)
                .order_by(desc(PdmSyncRunEntryOrmModel.id))
                .limit(limit)
            )
        ).all()
        return [_entry_to_entity(r) for r in rows]

    async def _write(self, run: PdmSyncRun) -> None:
        orm = await self._db.scalar(
            select(PdmSyncRunOrmModel).where(PdmSyncRunOrmModel.id == run.id).limit(1)
        )
        if orm is None:
            raise ValueError(f"PdmSyncRunOrmModel id={run.id} not found.")
        for key, value in _run_to_dict(run).items():
            setattr(orm, key, value)
        await self._db.flush()

    async def add_entries(self, run_id: int, entries: list[PdmSyncRunEntry]) -> None:
        for entry in entries:
            self._db.add(
                PdmSyncRunEntryOrmModel(
                    run_id=run_id,
                    vault_id=entry.vault_id,
                    file_id=entry.file_id,
                    name=entry.name,
                    path=entry.path,
                    kind=entry.kind,
                    action=entry.action,
                    item_id=entry.item_id,
                    message=entry.message,
                    created_at=entry.created_at,
                )
            )
        await self._db.flush()

    async def get_multi(
        self, skip: int | None, limit: int | None, filters: PdmSyncRunFilterDto | None = None
    ) -> tuple[int, list[PdmSyncRun]]:
        q = select(PdmSyncRunOrmModel)
        if filters is not None:
            zone = await date_filter_zone(self._db, filters.started_from, filters.started_to)
            if filters.triggers:
                q = q.where(PdmSyncRunOrmModel.trigger.in_(filters.triggers))
            if filters.started_from:
                q = q.where(
                    PdmSyncRunOrmModel.started_at >= day_start_utc(filters.started_from, zone)
                )
            if filters.started_to:
                q = q.where(PdmSyncRunOrmModel.started_at < day_after_utc(filters.started_to, zone))
            if filters.error:
                q = q.where(contains_ci(PdmSyncRunOrmModel.error, filters.error))
        total, rows = await fetch_page(
            self._db, q, skip, limit, desc(PdmSyncRunOrmModel.started_at)
        )
        return total, [_run_to_entity(r) for r in rows]

    async def get_by_id(self, id: int) -> PdmSyncRun | None:
        orm = await self._db.scalar(by_id(PdmSyncRunOrmModel, id).limit(1))
        return _run_to_entity(orm) if orm else None

    async def latest_by_trigger(self, trigger: str) -> PdmSyncRun | None:
        orm = await self._db.scalar(
            select(PdmSyncRunOrmModel)
            .where(PdmSyncRunOrmModel.trigger == trigger)
            .order_by(desc(PdmSyncRunOrmModel.started_at))
            .limit(1)
        )
        return _run_to_entity(orm) if orm else None

    async def get_entries(
        self,
        run_id: int,
        skip: int | None,
        limit: int | None,
        action: str | None,
        search: str | None = None,
        kind: str | None = None,
    ) -> tuple[int, list[PdmSyncRunEntry]]:
        q = select(PdmSyncRunEntryOrmModel).where(PdmSyncRunEntryOrmModel.run_id == run_id)
        if action:
            q = q.where(PdmSyncRunEntryOrmModel.action == action)
        if kind:
            q = q.where(PdmSyncRunEntryOrmModel.kind == kind)
        if search:
            q = q.where(
                or_(
                    contains_ci(PdmSyncRunEntryOrmModel.name, search),
                    contains_ci(PdmSyncRunEntryOrmModel.path, search),
                )
            )
        total, rows = await fetch_page(self._db, q, skip, limit, asc(PdmSyncRunEntryOrmModel.id))
        return total, [_entry_to_entity(r) for r in rows]

    async def list_file_history(
        self, vault_id: str, file_ids: list[int], limit: int
    ) -> list[tuple[PdmSyncRunEntry, PdmSyncRun]]:
        if not file_ids:
            return []
        rows = (
            await self._db.execute(
                select(PdmSyncRunEntryOrmModel, PdmSyncRunOrmModel)
                .join(PdmSyncRunOrmModel, PdmSyncRunOrmModel.id == PdmSyncRunEntryOrmModel.run_id)
                .where(
                    PdmSyncRunEntryOrmModel.vault_id == vault_id,
                    PdmSyncRunEntryOrmModel.file_id.in_(file_ids),
                )
                .order_by(
                    desc(PdmSyncRunEntryOrmModel.created_at), desc(PdmSyncRunEntryOrmModel.id)
                )
                .limit(limit)
            )
        ).all()
        return [(_entry_to_entity(entry), _run_to_entity(run)) for entry, run in rows]

    async def prune(self, older_than: datetime) -> int:
        """Deletes runs started before `older_than`, and their entries
        explicitly (not relying only on the FK's ondelete="CASCADE"):
        Postgres enforces that at the DB level regardless, but SQLite (the
        test suite's DB) only does when a per-connection PRAGMA is set,
        which nothing here assumes."""
        stale_ids = list(
            (
                await self._db.scalars(
                    select(PdmSyncRunOrmModel.id).where(PdmSyncRunOrmModel.started_at < older_than)
                )
            ).all()
        )
        count = len(stale_ids)
        if stale_ids:
            await self._db.execute(
                delete(PdmSyncRunEntryOrmModel).where(
                    PdmSyncRunEntryOrmModel.run_id.in_(stale_ids)
                ),
                execution_options={"synchronize_session": False},
            )
            await self._db.execute(
                delete(PdmSyncRunOrmModel).where(PdmSyncRunOrmModel.id.in_(stale_ids)),
                execution_options={"synchronize_session": False},
            )
        await self._db.flush()
        return count
