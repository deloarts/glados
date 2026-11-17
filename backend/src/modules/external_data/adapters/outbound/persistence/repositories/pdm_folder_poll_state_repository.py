"""
Concrete implementation of IPdmFolderPollStateRepository using SQLAlchemy.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.external_data.adapters.outbound.persistence.models.pdm_folder_poll_state_model import (
    PdmFolderPollStateOrmModel,
)
from src.modules.external_data.domain.entities.pdm_folder_poll_state import PdmFolderPollState
from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.shared_kernel.domain.services.clock import now_utc


def _orm_to_entity(orm: PdmFolderPollStateOrmModel) -> PdmFolderPollState:
    return PdmFolderPollState(
        id=orm.id,
        public_id=orm.public_id,
        vault_id=orm.vault_id,
        folder_key=orm.folder_key,
        consecutive_unchanged_runs=orm.consecutive_unchanged_runs,
        next_due_at=utc_aware(orm.next_due_at),
        last_changed_at=utc_aware(orm.last_changed_at),
        updated_at=utc_aware(orm.updated_at),
    )


def _entity_to_dict(state: PdmFolderPollState) -> dict[str, Any]:
    return {
        "vault_id": state.vault_id,
        "folder_key": state.folder_key,
        "consecutive_unchanged_runs": state.consecutive_unchanged_runs,
        "next_due_at": state.next_due_at,
        "last_changed_at": state.last_changed_at,
        "updated_at": state.updated_at,
    }


class SqlAlchemyPdmFolderPollStateRepository:
    """Implements IPdmFolderPollStateRepository."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def _get(self, vault_id: str, folder_key: str) -> PdmFolderPollStateOrmModel | None:
        orm: PdmFolderPollStateOrmModel | None = await self._db.scalar(
            select(PdmFolderPollStateOrmModel)
            .where(
                PdmFolderPollStateOrmModel.vault_id == vault_id,
                PdmFolderPollStateOrmModel.folder_key == folder_key,
            )
            .limit(1)
        )
        return orm

    async def get_all_for_vault(self, vault_id: str) -> dict[str, PdmFolderPollState]:
        rows = (
            await self._db.scalars(
                select(PdmFolderPollStateOrmModel).where(
                    PdmFolderPollStateOrmModel.vault_id == vault_id
                )
            )
        ).all()
        return {row.folder_key: _orm_to_entity(row) for row in rows}

    async def upsert(self, state: PdmFolderPollState) -> None:
        existing = await self._get(state.vault_id, state.folder_key)
        if existing is None:
            self._db.add(PdmFolderPollStateOrmModel(**_entity_to_dict(state)))
        else:
            for key, value in _entity_to_dict(state).items():
                setattr(existing, key, value)
        await self._db.flush()

    async def reset(self, vault_id: str, folder_key: str) -> None:
        existing = await self._get(vault_id, folder_key)
        if existing is None:
            return
        now = now_utc()
        existing.consecutive_unchanged_runs = 0
        existing.next_due_at = None
        existing.last_changed_at = now
        existing.updated_at = now
        await self._db.flush()
