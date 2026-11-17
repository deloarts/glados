"""
Concrete implementation of IPdmFileSnapshotRepository using SQLAlchemy.
"""

import re
from typing import Any

from sqlalchemy import desc
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from src.modules.external_data.adapters.outbound.persistence.models.pdm_file_snapshot_model import (
    PdmFileSnapshotOrmModel,
)
from src.modules.external_data.domain.entities.pdm_file_snapshot import PdmFileSnapshot
from src.modules.external_data.domain.value_objects.pdm_file_sync_state import PdmFileSyncState
from src.modules.external_data.ports.outbound.repositories.pdm_file_snapshot_repository import (
    PdmFileSnapshotFilterDto,
)
from src.modules.platform.adapters.outbound.persistence.like_escape import contains_ci
from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.adapters.outbound.persistence.statements import by_id
from src.modules.platform.adapters.outbound.persistence.statements import fetch_page

# Ids per IN query, well under every database's bound-parameter limit.
_IN_CHUNK = 1000


def _orm_to_entity(orm: PdmFileSnapshotOrmModel) -> PdmFileSnapshot:
    return PdmFileSnapshot(
        id=orm.id,
        public_id=orm.public_id,
        vault_id=orm.vault_id,
        file_id=orm.file_id,
        kind=orm.kind,
        name=orm.name,
        path=orm.path,
        parent_folder_id=orm.parent_folder_id,
        version=orm.version,
        state_id=orm.state_id,
        state=orm.state,
        modified_at=utc_aware(orm.modified_at),
        first_seen_at=utc_aware(orm.first_seen_at),
        last_seen_at=utc_aware(orm.last_seen_at),
        last_ingested_version=orm.last_ingested_version,
        sync_state=PdmFileSyncState(orm.sync_state),
        last_error=orm.last_error,
        part_number=orm.part_number,
        revision=orm.revision,
        article_name=orm.article_name,
        item_id=orm.item_id,
        parked_payload=orm.parked_payload,
    )


def _entity_to_dict(item: PdmFileSnapshot) -> dict[str, Any]:
    return {
        "vault_id": item.vault_id,
        "file_id": item.file_id,
        "kind": item.kind,
        "name": item.name,
        "path": item.path,
        "parent_folder_id": item.parent_folder_id,
        "version": item.version,
        "state_id": item.state_id,
        "state": item.state,
        "modified_at": item.modified_at,
        "first_seen_at": item.first_seen_at,
        "last_seen_at": item.last_seen_at,
        "last_ingested_version": item.last_ingested_version,
        "sync_state": item.sync_state.value,
        "last_error": item.last_error,
        "part_number": item.part_number,
        "revision": item.revision,
        "article_name": item.article_name,
        "item_id": item.item_id,
        "parked_payload": item.parked_payload,
    }


class SqlAlchemyPdmFileSnapshotRepository:
    """Implements IPdmFileSnapshotRepository."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_file(self, vault_id: str, file_id: int) -> PdmFileSnapshot | None:
        orm = await self._db.scalar(
            select(PdmFileSnapshotOrmModel)
            .where(
                PdmFileSnapshotOrmModel.vault_id == vault_id,
                PdmFileSnapshotOrmModel.file_id == file_id,
            )
            .limit(1)
        )
        return _orm_to_entity(orm) if orm else None

    async def get_by_id(self, id: int) -> PdmFileSnapshot | None:
        orm = await self._db.scalar(by_id(PdmFileSnapshotOrmModel, id).limit(1))
        return _orm_to_entity(orm) if orm else None

    async def find_by_path_suffix(self, vault_id: str, path_suffix: str) -> PdmFileSnapshot | None:
        normalized = path_suffix.lower()
        # A matching row's own file name is the suffix's last segment, so the
        # indexed (vault_id, lower(name)) prefilter keeps this to the few rows
        # sharing that name instead of the whole vault. The suffix check that
        # decides stays in Python, where case folding is the same on every
        # database; the SQL lower() only narrows the candidates, and the
        # names it compares are plain file names.
        file_name = re.split(r"[\\/]", normalized)[-1]
        candidates = (
            await self._db.execute(
                select(PdmFileSnapshotOrmModel.id, PdmFileSnapshotOrmModel.path).where(
                    PdmFileSnapshotOrmModel.vault_id == vault_id,
                    func.lower(PdmFileSnapshotOrmModel.name) == file_name,
                    func.length(PdmFileSnapshotOrmModel.path) <= len(normalized),
                )
            )
        ).all()
        matches = [row for row in candidates if normalized.endswith(row.path.lower())]
        if not matches:
            return None
        longest = max(len(row.path) for row in matches)
        best = [row for row in matches if len(row.path) == longest]
        if len(best) != 1:
            return None
        return await self.get_by_id(best[0].id)

    async def upsert_many(self, items: list[PdmFileSnapshot]) -> None:
        existing = await self._existing_rows(items)
        for item in items:
            row = existing.get((item.vault_id, item.file_id))
            if row is None:
                row = PdmFileSnapshotOrmModel(**_entity_to_dict(item))
                self._db.add(row)
                existing[(item.vault_id, item.file_id)] = row
            else:
                for k, v in _entity_to_dict(item).items():
                    setattr(row, k, v)
        await self._db.flush()

    async def get_by_file_ids(self, vault_id: str, file_ids: list[int]) -> list[PdmFileSnapshot]:
        return await self._in_chunks(vault_id, PdmFileSnapshotOrmModel.file_id, file_ids)

    async def get_by_parent_folder_ids(
        self, vault_id: str, folder_ids: list[int]
    ) -> list[PdmFileSnapshot]:
        return await self._in_chunks(vault_id, PdmFileSnapshotOrmModel.parent_folder_id, folder_ids)

    async def _in_chunks(
        self, vault_id: str, column: InstrumentedAttribute[int], values: list[int]
    ) -> list[PdmFileSnapshot]:
        ids = sorted(set(values))
        result: list[PdmFileSnapshot] = []
        for start in range(0, len(ids), _IN_CHUNK):
            rows = await self._db.scalars(
                select(PdmFileSnapshotOrmModel).where(
                    PdmFileSnapshotOrmModel.vault_id == vault_id,
                    column.in_(ids[start : start + _IN_CHUNK]),
                )
            )
            result.extend(_orm_to_entity(r) for r in rows)
        return result

    async def _existing_rows(
        self, items: list[PdmFileSnapshot]
    ) -> dict[tuple[str, int], PdmFileSnapshotOrmModel]:
        """The stored rows for `items`, read in a few chunked IN queries
        instead of one query per file."""
        by_vault: dict[str, set[int]] = {}
        for item in items:
            by_vault.setdefault(item.vault_id, set()).add(item.file_id)
        rows: dict[tuple[str, int], PdmFileSnapshotOrmModel] = {}
        for vault_id, file_ids in by_vault.items():
            ids = sorted(file_ids)
            for start in range(0, len(ids), _IN_CHUNK):
                chunk = ids[start : start + _IN_CHUNK]
                found = await self._db.scalars(
                    select(PdmFileSnapshotOrmModel).where(
                        PdmFileSnapshotOrmModel.vault_id == vault_id,
                        PdmFileSnapshotOrmModel.file_id.in_(chunk),
                    )
                )
                for row in found:
                    rows[(row.vault_id, row.file_id)] = row
        return rows

    async def get_multi(
        self, filters: PdmFileSnapshotFilterDto
    ) -> tuple[int, list[PdmFileSnapshot]]:
        q = select(PdmFileSnapshotOrmModel)

        if filters.sync_state:
            q = q.where(PdmFileSnapshotOrmModel.sync_state == filters.sync_state)
        if filters.kind:
            q = q.where(PdmFileSnapshotOrmModel.kind == filters.kind)
        if filters.search:
            term = filters.search
            q = q.where(
                or_(
                    contains_ci(PdmFileSnapshotOrmModel.name, term),
                    contains_ci(PdmFileSnapshotOrmModel.path, term),
                    contains_ci(PdmFileSnapshotOrmModel.part_number, term),
                )
            )

        total, rows = await fetch_page(
            self._db, q, filters.skip, filters.limit, desc(PdmFileSnapshotOrmModel.last_seen_at)
        )
        return total, [_orm_to_entity(r) for r in rows]

    async def get_all_for_vault(self, vault_id: str) -> list[PdmFileSnapshot]:
        rows = (
            await self._db.scalars(
                select(PdmFileSnapshotOrmModel).where(PdmFileSnapshotOrmModel.vault_id == vault_id)
            )
        ).all()
        return [_orm_to_entity(r) for r in rows]

    async def get_preview_candidates(self, vault_id: str, kind: str) -> list[PdmFileSnapshot]:
        model = PdmFileSnapshotOrmModel
        rows = (
            await self._db.scalars(
                select(model).where(
                    model.vault_id == vault_id,
                    model.kind == kind,
                    model.part_number.is_not(None),
                    model.part_number != "",
                    model.sync_state != PdmFileSyncState.MISSING.value,
                    or_(
                        model.item_id.is_(None),
                        model.last_ingested_version.is_(None),
                        model.version > model.last_ingested_version,
                    ),
                )
            )
        ).all()
        return [_orm_to_entity(r) for r in rows]

    async def list_conflicts(self, vault_id: str) -> list[PdmFileSnapshot]:
        rows = (
            await self._db.scalars(
                select(PdmFileSnapshotOrmModel).where(
                    PdmFileSnapshotOrmModel.vault_id == vault_id,
                    PdmFileSnapshotOrmModel.sync_state == PdmFileSyncState.CONFLICT.value,
                )
            )
        ).all()
        return [_orm_to_entity(r) for r in rows]

    async def reset_skipped_to_pending(self, vault_id: str) -> int:
        rows = (
            await self._db.scalars(
                select(PdmFileSnapshotOrmModel).where(
                    PdmFileSnapshotOrmModel.vault_id == vault_id,
                    PdmFileSnapshotOrmModel.sync_state == PdmFileSyncState.SKIPPED.value,
                )
            )
        ).all()
        for row in rows:
            row.sync_state = PdmFileSyncState.PENDING.value
            row.last_error = None
        await self._db.flush()
        return len(rows)

    async def save(self, item: PdmFileSnapshot) -> PdmFileSnapshot:
        if item.id == 0:
            orm = PdmFileSnapshotOrmModel(**_entity_to_dict(item))
            self._db.add(orm)
            await self._db.flush()
            await self._db.refresh(orm)
            return _orm_to_entity(orm)
        existing = await self._db.scalar(
            select(PdmFileSnapshotOrmModel).where(PdmFileSnapshotOrmModel.id == item.id).limit(1)
        )
        if not existing:
            raise ValueError(f"PdmFileSnapshotOrmModel id={item.id} not found.")
        for k, v in _entity_to_dict(item).items():
            setattr(existing, k, v)
        await self._db.flush()
        await self._db.refresh(existing)
        return _orm_to_entity(existing)

    async def counts_by_state(self, vault_id: str) -> dict[str, int]:
        rows = (
            await self._db.execute(
                select(PdmFileSnapshotOrmModel.sync_state, func.count().label("cnt"))
                .where(PdmFileSnapshotOrmModel.vault_id == vault_id)
                .group_by(PdmFileSnapshotOrmModel.sync_state)
            )
        ).all()
        return {row.sync_state: row.cnt for row in rows}
