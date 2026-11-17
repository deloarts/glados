"""
Concrete implementation of IPrinterRepository using SQLAlchemy + Postgres.
"""

from functools import lru_cache
from typing import Any

from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.interfaces import ORMOption

from src.modules.catalogue.adapters.outbound.persistence.mappers.bought_item_mappers import (
    item_orm_to_entity as _bought_item_orm_to_entity,
)
from src.modules.catalogue.adapters.outbound.persistence.models.article_group_model import (
    ArticleGroupOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.bought_item_model import (
    BoughtItemOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.like_escape import contains_ci
from src.modules.platform.adapters.outbound.persistence.mapping_common import archived_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import changed_by_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.adapters.outbound.persistence.statements import by_id
from src.modules.platform.adapters.outbound.persistence.statements import fetch_page
from src.modules.platform.adapters.outbound.persistence.statements import load_by_ids
from src.modules.platform.adapters.outbound.persistence.statements import order_term
from src.modules.platform.adapters.outbound.persistence.user_loading import load_user
from src.modules.quality.adapters.outbound.persistence.models.printer_model import PrinterOrmModel
from src.modules.quality.domain.entities.printer import Printer
from src.modules.quality.domain.value_objects.printer_kind import PrinterKind
from src.modules.quality.ports.outbound.repositories.printer_repository import PrinterFilterDto


@lru_cache(maxsize=1)
def _load_options() -> tuple[ORMOption, ...]:
    """Everything _orm_to_entity() dereferences, including what the nested
    bought item mapper reads. Built on first call rather than at import,
    because constructing a loader option configures the mapper registry before
    every model module is registered."""
    return (
        load_user(PrinterOrmModel.creator),
        load_user(PrinterOrmModel.changed_by),
        load_user(PrinterOrmModel.bought_items, BoughtItemOrmModel.creator),
        load_user(PrinterOrmModel.bought_items, BoughtItemOrmModel.changed_by),
        selectinload(PrinterOrmModel.bought_items).selectinload(BoughtItemOrmModel.manufacturer),
        selectinload(PrinterOrmModel.bought_items).selectinload(BoughtItemOrmModel.product_family),
        load_user(
            PrinterOrmModel.bought_items,
            BoughtItemOrmModel.article_groups,
            ArticleGroupOrmModel.creator,
        ),
        load_user(
            PrinterOrmModel.bought_items,
            BoughtItemOrmModel.article_groups,
            ArticleGroupOrmModel.changed_by,
        ),
    )


def _orm_to_entity(orm: PrinterOrmModel) -> Printer:
    return Printer(
        id=orm.id,
        public_id=orm.public_id,
        created=utc_aware(orm.created),
        **archived_kwargs(utc_aware(orm.changed), orm.changes, orm.archived),
        name=orm.name,
        internal_name=orm.internal_name,
        kind=PrinterKind(orm.kind),
        host=orm.host,
        port=orm.port,
        timeout_seconds=orm.timeout_seconds,
        transport=orm.transport,
        ipp_uri_path=orm.ipp_uri_path,
        head_dpi=orm.head_dpi,
        format_convert_factor=orm.format_convert_factor,
        default_media=orm.default_media,
        location=orm.location,
        vendor=orm.vendor,
        model=orm.model,
        firmware=orm.firmware,
        bought_item_ids=[b.id for b in orm.bought_items],
        enabled=orm.enabled,
        is_default=orm.is_default,
        note=orm.note,
        creator_id=orm.creator_id,
        creator_full_name=orm.creator.full_name if orm.creator else "",
        **changed_by_kwargs(orm.changed_by_id, orm.changed_by),
        bought_items=[_bought_item_orm_to_entity(b) for b in orm.bought_items],
    )


def _entity_to_dict(item: Printer) -> dict[str, Any]:
    return {
        "created": item.created,
        "changed": item.changed,
        "changes": item.changes,
        "archived": item.archived,
        "name": item.name,
        "internal_name": item.internal_name,
        "kind": item.kind.value,
        "host": item.host,
        "port": item.port,
        "timeout_seconds": item.timeout_seconds,
        "transport": item.transport,
        "ipp_uri_path": item.ipp_uri_path,
        "head_dpi": item.head_dpi,
        "format_convert_factor": item.format_convert_factor,
        "default_media": item.default_media,
        "location": item.location,
        "vendor": item.vendor,
        "model": item.model,
        "firmware": item.firmware,
        "enabled": item.enabled,
        "is_default": item.is_default,
        "note": item.note,
        "creator_id": item.creator_id,
    }


# ── Repository ────────────────────────────────────────────────────────


class SqlAlchemyPrinterRepository:
    """Implements IPrinterRepository."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, id: int) -> Printer | None:
        orm = await self._db.scalar(by_id(PrinterOrmModel, id, *_load_options()).limit(1))
        return _orm_to_entity(orm) if orm else None

    async def get_multi(self, filters: PrinterFilterDto) -> tuple[int, list[Printer]]:
        q = select(PrinterOrmModel)
        if not filters.include_archived:
            q = q.where(PrinterOrmModel.archived.is_(False))

        if filters.id:
            q = q.where(PrinterOrmModel.id == filters.id)
        if filters.name:
            q = q.where(contains_ci(PrinterOrmModel.name, filters.name))
        if filters.kind:
            q = q.where(PrinterOrmModel.kind == filters.kind)
        if filters.enabled is not None:
            q = q.where(PrinterOrmModel.enabled.is_(filters.enabled))
        if filters.creator_id:
            q = q.where(PrinterOrmModel.creator_id == filters.creator_id)
        if filters.changed_by_id:
            q = q.where(PrinterOrmModel.changed_by_id == filters.changed_by_id)
        if filters.search:
            term = filters.search
            q = q.where(
                or_(
                    contains_ci(PrinterOrmModel.name, term),
                    contains_ci(PrinterOrmModel.location, term),
                    func.similarity(PrinterOrmModel.name, term) > 0.25,
                )
            )

        _sort_column_map = {
            "id": PrinterOrmModel.id,
            "name": PrinterOrmModel.name,
            "changed": PrinterOrmModel.changed,
            "created": PrinterOrmModel.created,
        }
        sort_col = _sort_column_map.get(filters.order_by or "id", PrinterOrmModel.id)
        total, rows = await fetch_page(
            self._db,
            q,
            filters.skip,
            filters.limit,
            order_term(sort_col, filters.order_dir, default="desc"),
            options=_load_options(),
        )
        return total, [_orm_to_entity(r) for r in rows]

    async def _sync_bought_items(self, orm: PrinterOrmModel, bought_item_ids: list[int]) -> None:
        orm.bought_items = await load_by_ids(self._db, BoughtItemOrmModel, bought_item_ids)

    async def save(self, item: Printer) -> Printer:
        if item.id == 0:
            orm = PrinterOrmModel(**_entity_to_dict(item))
            await self._sync_bought_items(orm, item.bought_item_ids)
            self._db.add(orm)
            await self._db.flush()
            new_id = orm.id
            return _orm_to_entity(await self._reload(new_id))
        existing = await self._fetch_for_update(item.id)
        if not existing:
            raise ValueError(f"PrinterOrmModel id={item.id} not found.")
        orm = existing
        for k, v in _entity_to_dict(item).items():
            setattr(orm, k, v)
        await self._sync_bought_items(orm, item.bought_item_ids)
        await self._db.flush()
        return _orm_to_entity(await self._reload(item.id))

    async def _fetch_for_update(self, id: int) -> PrinterOrmModel | None:
        """Loads bought_items with the row, since _sync_bought_items() reassigns
        the collection and assignment reads the old one first."""
        orm: PrinterOrmModel | None = await self._db.scalar(
            select(PrinterOrmModel)
            .where(PrinterOrmModel.id == id)
            .options(selectinload(PrinterOrmModel.bought_items))
            .execution_options(populate_existing=True)
            .limit(1)
        )
        return orm

    async def _reload(self, id: int) -> PrinterOrmModel:
        return (
            await self._db.scalars(by_id(PrinterOrmModel, id, *_load_options(), refresh=True))
        ).one()

    async def delete(self, item: Printer) -> None:
        """Soft delete, sets archived=True and saves."""
        item.archived = True
        await self.save(item)
