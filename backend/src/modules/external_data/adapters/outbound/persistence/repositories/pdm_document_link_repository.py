"""
Concrete implementation of IPdmDocumentLinkRepository using SQLAlchemy.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.catalogue.domain.value_objects.item_kind import ItemKind
from src.modules.external_data.adapters.outbound.persistence.models.pdm_document_link_model import (
    PdmDocumentLinkOrmModel,
)
from src.modules.external_data.domain.entities.pdm_document_link import PdmDocumentLink


def _orm_to_entity(orm: PdmDocumentLinkOrmModel) -> PdmDocumentLink:
    return PdmDocumentLink(
        id=orm.id,
        public_id=orm.public_id,
        kind=ItemKind(orm.kind),
        item_id=orm.item_id,
        item_file_id=orm.item_file_id,
        vault_id=orm.vault_id,
        file_id=orm.file_id,
        version=orm.version,
        item_picture_id=orm.item_picture_id,
    )


def _entity_to_dict(link: PdmDocumentLink) -> dict[str, Any]:
    return {
        "kind": link.kind.value,
        "item_id": link.item_id,
        "item_file_id": link.item_file_id,
        "vault_id": link.vault_id,
        "file_id": link.file_id,
        "version": link.version,
        "item_picture_id": link.item_picture_id,
    }


class SqlAlchemyPdmDocumentLinkRepository:
    """Implements IPdmDocumentLinkRepository."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_pdm_file(self, vault_id: str, file_id: int) -> PdmDocumentLink | None:
        orm = await self._db.scalar(
            select(PdmDocumentLinkOrmModel)
            .where(
                PdmDocumentLinkOrmModel.vault_id == vault_id,
                PdmDocumentLinkOrmModel.file_id == file_id,
            )
            .limit(1)
        )
        return _orm_to_entity(orm) if orm else None

    async def get_by_pdm_files(self, vault_id: str, file_ids: list[int]) -> list[PdmDocumentLink]:
        if not file_ids:
            return []
        rows = (
            await self._db.scalars(
                select(PdmDocumentLinkOrmModel).where(
                    PdmDocumentLinkOrmModel.vault_id == vault_id,
                    PdmDocumentLinkOrmModel.file_id.in_(file_ids),
                )
            )
        ).all()
        return [_orm_to_entity(r) for r in rows]

    async def upsert(self, link: PdmDocumentLink) -> PdmDocumentLink:
        existing = await self._db.scalar(
            select(PdmDocumentLinkOrmModel)
            .where(
                PdmDocumentLinkOrmModel.vault_id == link.vault_id,
                PdmDocumentLinkOrmModel.file_id == link.file_id,
            )
            .limit(1)
        )
        if existing is None:
            orm = PdmDocumentLinkOrmModel(**_entity_to_dict(link))
            self._db.add(orm)
        else:
            for k, v in _entity_to_dict(link).items():
                setattr(existing, k, v)
            orm = existing
        await self._db.flush()
        return _orm_to_entity(orm)

    async def delete(self, link: PdmDocumentLink) -> None:
        orm = await self._db.get(PdmDocumentLinkOrmModel, link.id)
        if orm is not None:
            await self._db.delete(orm)
            await self._db.flush()

    async def get_linked_item_file_ids(self, item_file_ids: list[int]) -> set[int]:
        if not item_file_ids:
            return set()
        rows = await self._db.scalars(
            select(PdmDocumentLinkOrmModel.item_file_id).where(
                PdmDocumentLinkOrmModel.item_file_id.in_(item_file_ids)
            )
        )
        return {file_id for file_id in rows if file_id is not None}

    async def all_for_vault(self, vault_id: str) -> list[PdmDocumentLink]:
        rows = (
            await self._db.scalars(
                select(PdmDocumentLinkOrmModel).where(PdmDocumentLinkOrmModel.vault_id == vault_id)
            )
        ).all()
        return [_orm_to_entity(r) for r in rows]
