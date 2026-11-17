"""
Concrete SQLAlchemy implementation for the BoughtItem aggregate.
"""

from typing import Any

import sqlalchemy as sa
from sqlalchemy import ColumnElement
from sqlalchemy import Select
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.modules.catalogue.adapters.outbound.persistence.mappers.bought_item_mappers import (
    bought_item_load_options,
)
from src.modules.catalogue.adapters.outbound.persistence.mappers.bought_item_mappers import (
    item_entity_to_dict,
)
from src.modules.catalogue.adapters.outbound.persistence.mappers.bought_item_mappers import (
    item_file_orm_to_entity,
)
from src.modules.catalogue.adapters.outbound.persistence.mappers.bought_item_mappers import (
    item_orm_to_entity,
)
from src.modules.catalogue.adapters.outbound.persistence.models.article_group_model import (
    ArticleGroupOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.article_group_model import (
    bought_item_article_group_table,
)
from src.modules.catalogue.adapters.outbound.persistence.models.bought_item_file_model import (
    BoughtItemFileOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.bought_item_model import (
    BoughtItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.made_item_model import (
    MadeItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.supplier_model import (
    SupplierOrmModel,
)
from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.entities.bought_item_file import BoughtItemFile
from src.modules.catalogue.domain.policies.order_code import ORDER_CODE_SEPARATORS
from src.modules.catalogue.domain.policies.order_code import normalize_order_code
from src.modules.catalogue.domain.value_objects.bought_item_file_category import (
    BoughtItemFileCategory,
)
from src.modules.catalogue.ports.outbound.catalogue_queries import BoughtItemFilterDto
from src.modules.platform.adapters.outbound.persistence.like_escape import contains_ci
from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel
from src.modules.platform.adapters.outbound.persistence.query_filters import FilterSpec
from src.modules.platform.adapters.outbound.persistence.query_filters import apply_filters
from src.modules.platform.adapters.outbound.persistence.query_filters import when
from src.modules.platform.adapters.outbound.persistence.query_filters import when_not_none
from src.modules.platform.adapters.outbound.persistence.statements import by_id
from src.modules.platform.adapters.outbound.persistence.statements import fetch_page
from src.modules.platform.adapters.outbound.persistence.statements import load_by_ids
from src.modules.platform.adapters.outbound.persistence.statements import lock_row
from src.modules.platform.adapters.outbound.persistence.statements import order_term

# Keeps each IN (...) clause well under SQLite's SQLITE_MAX_VARIABLE_NUMBER
# (999 on older builds) when existing_part_numbers is called with a large
# batch, e.g. the whole part-number registry.
_PART_NUMBER_CHUNK_SIZE = 500

# Referencing SupplierOrmModel here has no join dependency of its own: a
# plain attribute reference only turns into SQL once it reaches
# .where()/.order_by(), by which point get_multi's join step has already run.
_SORT_COLUMNS: dict[str, Any] = {
    "id": BoughtItemOrmModel.id,
    "article_name": BoughtItemOrmModel.article_name,
    "manufacturer_name": SupplierOrmModel.name,
    "changed": BoughtItemOrmModel.changed,
    "created": BoughtItemOrmModel.created,
}


async def _pdf_files(db: AsyncSession, bought_item_id: int) -> list[BoughtItemFile]:
    rows = (
        await db.scalars(
            select(BoughtItemFileOrmModel)
            .where(
                BoughtItemFileOrmModel.bought_item_id == bought_item_id,
                BoughtItemFileOrmModel.category == BoughtItemFileCategory.PDF.value,
            )
            .order_by(BoughtItemFileOrmModel.created.asc())
        )
    ).all()
    return [item_file_orm_to_entity(r) for r in rows]


async def _pdf_files_by_item(
    db: AsyncSession, bought_item_ids: list[int]
) -> dict[int, list[BoughtItemFile]]:
    """One query for a whole result page, avoids an N+1 over the listed items."""
    if not bought_item_ids:
        return {}
    rows = (
        await db.scalars(
            select(BoughtItemFileOrmModel)
            .where(
                BoughtItemFileOrmModel.bought_item_id.in_(bought_item_ids),
                BoughtItemFileOrmModel.category == BoughtItemFileCategory.PDF.value,
            )
            .order_by(BoughtItemFileOrmModel.created.asc())
        )
    ).all()
    grouped: dict[int, list[BoughtItemFile]] = {}
    for row in rows:
        grouped.setdefault(row.bought_item_id, []).append(item_file_orm_to_entity(row))
    return grouped


# ══════════════════════════════════════════════════════════════════════
# BoughtItem repository
# ══════════════════════════════════════════════════════════════════════


class SqlAlchemyBoughtItemRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, id: int) -> BoughtItem | None:
        orm = await self._db.scalar(
            by_id(BoughtItemOrmModel, id, *bought_item_load_options()).limit(1)
        )
        return item_orm_to_entity(orm, await _pdf_files(self._db, orm.id)) if orm else None

    async def lock_for_update(self, id: int) -> None:
        await lock_row(self._db, BoughtItemOrmModel, id)

    async def get_by_part_number(self, part_number: str) -> BoughtItem | None:
        orm = await self._db.scalar(
            select(BoughtItemOrmModel)
            .where(
                BoughtItemOrmModel.part_number == part_number,
                BoughtItemOrmModel.archived.is_(False),
            )
            .options(*bought_item_load_options())
            .limit(1)
        )
        return item_orm_to_entity(orm, await _pdf_files(self._db, orm.id)) if orm else None

    async def existing_part_numbers(self, part_numbers: list[str]) -> set[str]:
        """Which of `part_numbers` have a live (non-archived) row, without
        fetching the rows themselves, using one IN query per chunk of
        `_PART_NUMBER_CHUNK_SIZE` instead of one get_by_part_number call
        per part number."""
        if not part_numbers:
            return set()
        found: set[str] = set()
        for start in range(0, len(part_numbers), _PART_NUMBER_CHUNK_SIZE):
            chunk = part_numbers[start : start + _PART_NUMBER_CHUNK_SIZE]
            rows = (
                await self._db.execute(
                    select(BoughtItemOrmModel.part_number)
                    .where(
                        BoughtItemOrmModel.part_number.in_(chunk),
                        BoughtItemOrmModel.archived.is_(False),
                    )
                    .distinct()
                )
            ).all()
            found.update(r.part_number for r in rows)
        return found

    async def get_by_gtin(self, gtin: str) -> BoughtItem | None:
        orm = await self._db.scalar(
            select(BoughtItemOrmModel)
            .where(
                BoughtItemOrmModel.gtin == gtin,
                BoughtItemOrmModel.archived.is_(False),
            )
            .options(*bought_item_load_options())
            .limit(1)
        )
        return item_orm_to_entity(orm, await _pdf_files(self._db, orm.id)) if orm else None

    async def get_by_pdm_file(self, vault_id: str, pdm_file_id: int) -> BoughtItem | None:
        orm = await self._db.scalar(
            select(BoughtItemOrmModel)
            .where(
                BoughtItemOrmModel.vault_id == vault_id,
                BoughtItemOrmModel.pdm_file_id == pdm_file_id,
                BoughtItemOrmModel.archived.is_(False),
            )
            .options(*bought_item_load_options())
            .limit(1)
        )
        return item_orm_to_entity(orm, await _pdf_files(self._db, orm.id)) if orm else None

    async def find_by_order_code(self, manufacturer_id: int, order_code: str) -> list[BoughtItem]:
        normalized = normalize_order_code(order_code)
        if not normalized:
            return []
        column: ColumnElement[str] = func.lower(BoughtItemOrmModel.order_code_1)
        for separator in ORDER_CODE_SEPARATORS:
            column = func.replace(column, separator, "")
        rows = (
            await self._db.scalars(
                select(BoughtItemOrmModel)
                .where(
                    BoughtItemOrmModel.manufacturer_id == manufacturer_id,
                    BoughtItemOrmModel.archived.is_(False),
                    column == normalized,
                )
                .options(*bought_item_load_options())
                .order_by(BoughtItemOrmModel.id)
            )
        ).all()
        return [item_orm_to_entity(r) for r in rows]

    async def find_by_edp_part_id(self, edp_part_id: int) -> list[BoughtItem]:
        rows = (
            await self._db.scalars(
                select(BoughtItemOrmModel)
                .where(
                    BoughtItemOrmModel.edp_part_id == edp_part_id,
                    BoughtItemOrmModel.archived.is_(False),
                )
                .options(*bought_item_load_options())
                .order_by(BoughtItemOrmModel.id)
            )
        ).all()
        return [item_orm_to_entity(r) for r in rows]

    async def find_by_ean(self, ean: str) -> list[BoughtItem]:
        rows = (
            await self._db.scalars(
                select(BoughtItemOrmModel)
                .where(BoughtItemOrmModel.ean == ean, BoughtItemOrmModel.archived.is_(False))
                .options(*bought_item_load_options())
                .order_by(BoughtItemOrmModel.id)
            )
        ).all()
        return [item_orm_to_entity(r) for r in rows]

    async def find_claim_candidate(
        self,
        *,
        gtin: str | None,
        manufacturer_id: int | None,
        order_code_1: str | None,
    ) -> BoughtItem | None:
        q = (
            select(BoughtItemOrmModel)
            .where(
                BoughtItemOrmModel.pdm_file_id.is_(None),
                BoughtItemOrmModel.archived.is_(False),
            )
            .options(*bought_item_load_options())
        )
        if gtin:
            rows = (await self._db.scalars(q.where(BoughtItemOrmModel.gtin == gtin))).all()
        elif manufacturer_id is not None and order_code_1:
            rows = (
                await self._db.scalars(
                    q.where(
                        BoughtItemOrmModel.manufacturer_id == manufacturer_id,
                        BoughtItemOrmModel.order_code_1 == order_code_1,
                    )
                )
            ).all()
        else:
            rows = []
        if len(rows) != 1:
            return None
        orm = rows[0]
        return item_orm_to_entity(orm, await _pdf_files(self._db, orm.id))

    async def list_cad_items_with_links(
        self, skip: int | None, limit: int | None
    ) -> tuple[int, list[BoughtItem]]:
        q = select(BoughtItemOrmModel).where(
            BoughtItemOrmModel.archived.is_(False),
            BoughtItemOrmModel.data_source == "CAD",
        )
        total, rows = await fetch_page(
            self._db, q, skip, limit, BoughtItemOrmModel.id, options=bought_item_load_options()
        )
        # No item-file hydration: ReconcilePdmVault only reads the link
        # columns and identity fields, unlike get_multi's catalogue rows.
        return total, [item_orm_to_entity(r) for r in rows]

    def _filter_specs(self, filters: BoughtItemFilterDto) -> list[FilterSpec]:
        return [
            when(not filters.include_archived, lambda _: BoughtItemOrmModel.archived.is_(False)),
            when(filters.id, lambda id: BoughtItemOrmModel.id == id),
            when(filters.status, lambda status: BoughtItemOrmModel.status == status),
            when(
                filters.manufacturer_id,
                lambda manufacturer_id: BoughtItemOrmModel.manufacturer_id == manufacturer_id,
            ),
            when(
                filters.creator_id, lambda creator_id: BoughtItemOrmModel.creator_id == creator_id
            ),
            when(
                filters.changed_by_id,
                lambda changed_by_id: BoughtItemOrmModel.changed_by_id == changed_by_id,
            ),
            when(
                filters.approver_id,
                lambda approver_id: BoughtItemOrmModel.approver_id == approver_id,
            ),
            when(
                filters.successor_item_id,
                lambda successor_item_id: BoughtItemOrmModel.successor_item_id == successor_item_id,
            ),
            when(
                filters.order_code_1,
                lambda order_code_1: contains_ci(BoughtItemOrmModel.order_code_1, order_code_1),
            ),
            when(
                filters.order_code_2,
                lambda order_code_2: contains_ci(BoughtItemOrmModel.order_code_2, order_code_2),
            ),
            when(filters.gtin, lambda gtin: contains_ci(BoughtItemOrmModel.gtin, gtin)),
            when(filters.ean, lambda ean: contains_ci(BoughtItemOrmModel.ean, ean)),
            when(
                filters.tariff_number,
                lambda tariff_number: contains_ci(BoughtItemOrmModel.tariff_number, tariff_number),
            ),
            when(
                filters.article_name,
                lambda article_name: contains_ci(BoughtItemOrmModel.article_name, article_name),
            ),
            when(
                filters.article_group_id,
                lambda article_group_id: BoughtItemOrmModel.article_groups.any(
                    ArticleGroupOrmModel.id == article_group_id
                ),
            ),
            when(
                filters.product_family_id,
                lambda product_family_id: BoughtItemOrmModel.product_family_id == product_family_id,
            ),
            when(
                filters.data_source,
                lambda data_source: BoughtItemOrmModel.data_source == data_source,
            ),
            when(
                filters.part_number,
                lambda part_number: contains_ci(BoughtItemOrmModel.part_number, part_number),
            ),
            when_not_none(filters.mass, lambda mass: BoughtItemOrmModel.mass == mass),
            when(filters.note, lambda note: contains_ci(BoughtItemOrmModel.note, note)),
            when(filters.weblink, lambda weblink: contains_ci(BoughtItemOrmModel.weblink, weblink)),
            when(
                filters.manufacturer_name,
                lambda manufacturer_name: contains_ci(SupplierOrmModel.name, manufacturer_name),
            ),
            when(
                filters.creator_full_name,
                lambda creator_full_name: contains_ci(UserOrmModel.full_name, creator_full_name),
            ),
            when(filters.search, lambda search: self._search_clause(search)),
            when(
                filters.created_from,
                lambda created_from: BoughtItemOrmModel.created >= created_from,
            ),
            when(filters.created_to, lambda created_to: BoughtItemOrmModel.created <= created_to),
            when(
                filters.changed_from,
                lambda changed_from: BoughtItemOrmModel.changed >= changed_from,
            ),
            when(filters.changed_to, lambda changed_to: BoughtItemOrmModel.changed <= changed_to),
        ]

    def _search_clause(self, term: str) -> ColumnElement[bool]:
        return or_(
            contains_ci(BoughtItemOrmModel.order_code_1, term),
            contains_ci(BoughtItemOrmModel.article_name, term),
            contains_ci(BoughtItemOrmModel.order_code_2, term),
            contains_ci(BoughtItemOrmModel.part_number, term),
            contains_ci(BoughtItemOrmModel.gtin, term),
            contains_ci(BoughtItemOrmModel.ean, term),
            contains_ci(BoughtItemOrmModel.note, term),
            func.similarity(BoughtItemOrmModel.order_code_1, term) > 0.25,
            func.similarity(BoughtItemOrmModel.article_name, term) > 0.25,
            func.similarity(SupplierOrmModel.name, term) > 0.25,
            func.similarity(UserOrmModel.full_name, term) > 0.25,
        )

    def _apply_supplier_and_creator_joins(
        self, q: Select[tuple[BoughtItemOrmModel]], filters: BoughtItemFilterDto
    ) -> Select[tuple[BoughtItemOrmModel]]:
        """Supplier/creator are joined at most once each, regardless of how
        many of manufacturer_name/creator_full_name/search/order_by ask for
        them, since the filters and sort column below only ever reference
        the joined tables, never re-join them."""
        needs_supplier_join = any(
            [
                filters.manufacturer_name,
                filters.search,
                filters.order_by == "manufacturer_name",
            ]
        )
        if needs_supplier_join:
            q = q.join(SupplierOrmModel, BoughtItemOrmModel.manufacturer_id == SupplierOrmModel.id)
        needs_creator_join = any([filters.creator_full_name, filters.search])
        if needs_creator_join:
            q = q.join(UserOrmModel, BoughtItemOrmModel.creator_id == UserOrmModel.id)
        return q

    async def get_multi(self, filters: BoughtItemFilterDto) -> tuple[int, list[BoughtItem]]:
        q = select(BoughtItemOrmModel)
        q = self._apply_supplier_and_creator_joins(q, filters)
        q = apply_filters(q, self._filter_specs(filters))

        sort_col = _SORT_COLUMNS.get(filters.order_by or "id", BoughtItemOrmModel.id)
        # Eager-load what the mapper dereferences, to avoid N+1 across the page.
        total, rows = await fetch_page(
            self._db,
            q,
            filters.skip,
            filters.limit,
            order_term(sort_col, filters.order_dir, default="desc"),
            options=bought_item_load_options(),
        )
        pdf_files = await _pdf_files_by_item(self._db, [r.id for r in rows])
        return total, [item_orm_to_entity(r, pdf_files.get(r.id, [])) for r in rows]

    async def _reload(self, id: int) -> BoughtItemOrmModel:
        """Re-reads a just written row with everything the mapper needs.
        populate_existing refreshes every column, so server defaults arrive
        as they would through refresh(), and applies the loader options to
        the instance already in the session."""
        return (
            await self._db.scalars(
                by_id(BoughtItemOrmModel, id, *bought_item_load_options(), refresh=True)
            )
        ).one()

    async def _get_for_update(self, id: int) -> BoughtItemOrmModel | None:
        """Assigning article_groups reads the old collection first, so it is
        loaded up front."""
        return await self._db.get(
            BoughtItemOrmModel,
            id,
            options=[selectinload(BoughtItemOrmModel.article_groups)],
            populate_existing=True,
        )

    async def _get_for_delete(self, id: int) -> BoughtItemOrmModel | None:
        """The flush that deletes the row processes these collections (FK
        nulling, association rows), so they are loaded up front."""
        return await self._db.get(
            BoughtItemOrmModel,
            id,
            options=[
                selectinload(BoughtItemOrmModel.article_groups),
                selectinload(BoughtItemOrmModel.files),
            ],
            populate_existing=True,
        )

    async def save(self, item: BoughtItem) -> BoughtItem:
        article_groups = await load_by_ids(self._db, ArticleGroupOrmModel, item.article_group_ids)
        if item.id == 0:
            orm = BoughtItemOrmModel(**item_entity_to_dict(item))
            orm.article_groups = article_groups
            self._db.add(orm)
            await self._db.flush()
            return item_orm_to_entity(await self._reload(orm.id))
        existing = await self._get_for_update(item.id)
        if not existing:
            raise ValueError(f"BoughtItemOrmModel id={item.id} not found.")
        orm = existing
        for k, v in item_entity_to_dict(item).items():
            setattr(orm, k, v)
        orm.article_groups = article_groups
        await self._db.flush()
        orm = await self._reload(orm.id)
        return item_orm_to_entity(orm, await _pdf_files(self._db, orm.id))

    async def delete(self, item: BoughtItem) -> None:
        orm = await self._get_for_delete(item.id)
        if orm:
            await self._db.delete(orm)
            await self._db.flush()

    async def merge_catalogue_references(self, source_id: int, target_id: int) -> None:
        """Points the made items and successor links that name the source
        item at the target. The other modules' references move first,
        through the bought item usages port. A Core UPDATE passes the edit
        version listener by, so each one moves the version itself."""
        await self._db.execute(
            sa.update(MadeItemOrmModel)
            .where(MadeItemOrmModel.bought_item_id == source_id)
            .values(bought_item_id=target_id, edit_version=MadeItemOrmModel.edit_version + 1)
            .execution_options(synchronize_session=False)
        )
        await self._db.execute(
            sa.update(BoughtItemOrmModel)
            .where(
                BoughtItemOrmModel.successor_item_id == source_id,
                BoughtItemOrmModel.id != target_id,
            )
            .values(successor_item_id=target_id, edit_version=BoughtItemOrmModel.edit_version + 1)
            .execution_options(synchronize_session=False)
        )
        await self._db.execute(
            sa.update(BoughtItemOrmModel)
            .where(
                BoughtItemOrmModel.id == target_id,
                BoughtItemOrmModel.successor_item_id == source_id,
            )
            .values(successor_item_id=None, edit_version=BoughtItemOrmModel.edit_version + 1)
            .execution_options(synchronize_session=False)
        )
        await self._db.flush()

    async def merge_article_groups(self, source_id: int, target_id: int) -> None:
        source_group_ids = (
            (
                await self._db.execute(
                    sa.select(bought_item_article_group_table.c.article_group_id).where(
                        bought_item_article_group_table.c.bought_item_id == source_id
                    )
                )
            )
            .scalars()
            .all()
        )

        existing_target_ids = set(
            (
                await self._db.execute(
                    sa.select(bought_item_article_group_table.c.article_group_id).where(
                        bought_item_article_group_table.c.bought_item_id == target_id
                    )
                )
            )
            .scalars()
            .all()
        )

        for group_id in source_group_ids:
            if group_id not in existing_target_ids:
                await self._db.execute(
                    bought_item_article_group_table.insert().values(
                        bought_item_id=target_id, article_group_id=group_id
                    )
                )

        await self._db.execute(
            bought_item_article_group_table.delete().where(
                bought_item_article_group_table.c.bought_item_id == source_id
            )
        )
        await self._db.flush()
