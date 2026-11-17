"""
Concrete SQLAlchemy implementation for the MadeItem aggregate + its owned
MadeItemProcess children.
"""

from typing import Any

import sqlalchemy as sa
from sqlalchemy import ColumnElement
from sqlalchemy import Select
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from sqlalchemy.orm import selectinload

from src.modules.catalogue.adapters.outbound.persistence.mappers.made_item_mappers import (
    item_entity_to_dict,
)
from src.modules.catalogue.adapters.outbound.persistence.mappers.made_item_mappers import (
    item_load_options,
)
from src.modules.catalogue.adapters.outbound.persistence.mappers.made_item_mappers import (
    item_orm_to_entity,
)
from src.modules.catalogue.adapters.outbound.persistence.mappers.made_item_mappers import (
    made_item_load_options,
)
from src.modules.catalogue.adapters.outbound.persistence.mappers.made_item_mappers import (
    process_entity_to_dict,
)
from src.modules.catalogue.adapters.outbound.persistence.mappers.made_item_mappers import (
    process_load_options,
)
from src.modules.catalogue.adapters.outbound.persistence.mappers.made_item_mappers import (
    process_orm_to_entity,
)
from src.modules.catalogue.adapters.outbound.persistence.models.article_group_model import (
    ArticleGroupOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.article_group_model import (
    made_item_article_group_table,
)
from src.modules.catalogue.adapters.outbound.persistence.models.made_item_model import (
    MadeItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.made_item_process_model import (
    MadeItemProcessOrmModel,
)
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.entities.made_item_process import MadeItemProcess
from src.modules.catalogue.domain.policies.made_item_rules import normalize_process_groups
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.ports.outbound.catalogue_queries import MadeItemFilterDto
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

# ══════════════════════════════════════════════════════════════════════
# MadeItem repository
# ══════════════════════════════════════════════════════════════════════


class SqlAlchemyMadeItemRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def _reload(self, id: int) -> MadeItemOrmModel:
        return (
            await self._db.scalars(
                by_id(MadeItemOrmModel, id, *made_item_load_options(), refresh=True)
            )
        ).one()

    async def _get_for_update(self, id: int) -> MadeItemOrmModel | None:
        """Assigning article_groups reads the old collection first, so the
        row comes with it loaded."""
        row: MadeItemOrmModel | None = await self._db.scalar(
            select(MadeItemOrmModel)
            .where(MadeItemOrmModel.id == id)
            .options(selectinload(MadeItemOrmModel.article_groups))
        )
        return row

    async def _get_for_delete(self, id: int) -> MadeItemOrmModel | None:
        """Deleting a made item cascades to its processes, so the row comes
        with them loaded."""
        row: MadeItemOrmModel | None = await self._db.scalar(
            select(MadeItemOrmModel)
            .where(MadeItemOrmModel.id == id)
            .options(selectinload(MadeItemOrmModel.processes))
        )
        return row

    async def get_by_id(self, id: int) -> MadeItem | None:
        orm = await self._db.scalar(by_id(MadeItemOrmModel, id, *made_item_load_options()))
        return item_orm_to_entity(orm) if orm else None

    async def lock_for_update(self, id: int) -> None:
        await lock_row(self._db, MadeItemOrmModel, id)

    async def get_revisions(self, part_number: str) -> list[MadeItem]:
        rows = (
            await self._db.scalars(
                select(MadeItemOrmModel)
                .where(
                    MadeItemOrmModel.part_number == part_number,
                    MadeItemOrmModel.archived.is_(False),
                )
                .order_by(MadeItemOrmModel.id)
                .options(*made_item_load_options())
            )
        ).all()
        return [item_orm_to_entity(r) for r in rows]

    async def existing_part_numbers(self, part_numbers: list[str]) -> set[str]:
        """Which of `part_numbers` have at least one non-archived row,
        without fetching the rows themselves, using one IN query per chunk of
        `_PART_NUMBER_CHUNK_SIZE` instead of one get_revisions call per
        part number."""
        if not part_numbers:
            return set()
        found: set[str] = set()
        for start in range(0, len(part_numbers), _PART_NUMBER_CHUNK_SIZE):
            chunk = part_numbers[start : start + _PART_NUMBER_CHUNK_SIZE]
            rows = (
                await self._db.execute(
                    select(MadeItemOrmModel.part_number)
                    .where(
                        MadeItemOrmModel.part_number.in_(chunk),
                        MadeItemOrmModel.archived.is_(False),
                    )
                    .distinct()
                )
            ).all()
            found.update(r.part_number for r in rows)
        return found

    async def get_by_part_number_and_revision(
        self, part_number: str, revision: str
    ) -> MadeItem | None:
        orm = await self._db.scalar(
            select(MadeItemOrmModel)
            .where(
                MadeItemOrmModel.part_number == part_number,
                MadeItemOrmModel.revision == revision,
                MadeItemOrmModel.archived.is_(False),
            )
            .options(*made_item_load_options())
            .limit(1)
        )
        return item_orm_to_entity(orm) if orm else None

    async def get_family(self, part_number: str) -> list[MadeItem]:
        rows = (
            await self._db.scalars(
                select(MadeItemOrmModel)
                .where(MadeItemOrmModel.part_number == part_number)
                .order_by(MadeItemOrmModel.id)
                .options(*made_item_load_options())
            )
        ).all()
        return [item_orm_to_entity(r) for r in rows]

    async def get_family_by_pdm_file(self, vault_id: str, pdm_file_id: int) -> list[MadeItem]:
        rows = (
            await self._db.scalars(
                select(MadeItemOrmModel)
                .where(
                    MadeItemOrmModel.vault_id == vault_id,
                    MadeItemOrmModel.pdm_file_id == pdm_file_id,
                    MadeItemOrmModel.archived.is_(False),
                )
                # Same "newest first" ordering as get_multi's latest_only
                # window: highest (len(revision), revision) first, ties by
                # created desc then id desc. See revision_scheme.sort_key.
                .order_by(
                    func.length(MadeItemOrmModel.revision).desc(),
                    MadeItemOrmModel.revision.desc(),
                    MadeItemOrmModel.created.desc(),
                    MadeItemOrmModel.id.desc(),
                )
                .options(*made_item_load_options())
            )
        ).all()
        return [item_orm_to_entity(r) for r in rows]

    async def list_cad_items_with_links(
        self, skip: int | None, limit: int | None
    ) -> tuple[int, list[MadeItem]]:
        q = select(MadeItemOrmModel).where(
            MadeItemOrmModel.archived.is_(False),
            MadeItemOrmModel.data_source == DataSource.CAD.value,
        )
        total, rows = await fetch_page(
            self._db, q, skip, limit, MadeItemOrmModel.id, options=made_item_load_options()
        )
        return total, [item_orm_to_entity(r) for r in rows]

    def _filter_specs(self, filters: MadeItemFilterDto) -> list[FilterSpec]:
        return [
            when(not filters.include_archived, lambda _: MadeItemOrmModel.archived.is_(False)),
            when(filters.id, lambda id: MadeItemOrmModel.id == id),
            when(filters.status, lambda status: MadeItemOrmModel.status == status),
            when(
                filters.bought_item_id,
                lambda bought_item_id: MadeItemOrmModel.bought_item_id == bought_item_id,
            ),
            when(
                filters.source_item_id,
                lambda source_item_id: MadeItemOrmModel.source_item_id == source_item_id,
            ),
            when(
                filters.customer_id,
                lambda customer_id: MadeItemOrmModel.customer_id == customer_id,
            ),
            when(filters.creator_id, lambda creator_id: MadeItemOrmModel.creator_id == creator_id),
            when(
                filters.approver_id, lambda approver_id: MadeItemOrmModel.approver_id == approver_id
            ),
            when(
                filters.successor_item_id,
                lambda successor_item_id: MadeItemOrmModel.successor_item_id == successor_item_id,
            ),
            when(
                filters.article_name,
                lambda article_name: contains_ci(MadeItemOrmModel.article_name, article_name),
            ),
            when(
                filters.article_group_id,
                lambda article_group_id: MadeItemOrmModel.article_groups.any(
                    ArticleGroupOrmModel.id == article_group_id
                ),
            ),
            when(
                filters.data_source, lambda data_source: MadeItemOrmModel.data_source == data_source
            ),
            when(
                filters.part_number,
                lambda part_number: contains_ci(MadeItemOrmModel.part_number, part_number),
            ),
            when(
                filters.revision, lambda revision: contains_ci(MadeItemOrmModel.revision, revision)
            ),
            when(
                filters.material, lambda material: contains_ci(MadeItemOrmModel.material, material)
            ),
            when_not_none(filters.mass, lambda mass: MadeItemOrmModel.mass == mass),
            when(filters.note, lambda note: contains_ci(MadeItemOrmModel.note, note)),
            when(filters.weblink, lambda weblink: contains_ci(MadeItemOrmModel.weblink, weblink)),
            when(
                filters.creator_full_name,
                lambda creator_full_name: contains_ci(UserOrmModel.full_name, creator_full_name),
            ),
            when(filters.search, lambda search: self._search_clause(search)),
            when(
                filters.created_from, lambda created_from: MadeItemOrmModel.created >= created_from
            ),
            when(filters.created_to, lambda created_to: MadeItemOrmModel.created <= created_to),
            when(
                filters.changed_from, lambda changed_from: MadeItemOrmModel.changed >= changed_from
            ),
            when(filters.changed_to, lambda changed_to: MadeItemOrmModel.changed <= changed_to),
        ]

    def _search_clause(self, term: str) -> ColumnElement[bool]:
        return or_(
            contains_ci(MadeItemOrmModel.article_name, term),
            contains_ci(MadeItemOrmModel.part_number, term),
            contains_ci(MadeItemOrmModel.revision, term),
            contains_ci(MadeItemOrmModel.note, term),
            contains_ci(MadeItemOrmModel.customer_part_number, term),
            func.similarity(MadeItemOrmModel.article_name, term) > 0.25,
            func.similarity(UserOrmModel.full_name, term) > 0.25,
        )

    def _apply_creator_join(self, q: Select[Any], filters: MadeItemFilterDto) -> Select[Any]:
        """Joined at most once, regardless of whether creator_full_name,
        search, or both ask for it."""
        if filters.creator_full_name or filters.search:
            q = q.join(UserOrmModel, MadeItemOrmModel.creator_id == UserOrmModel.id)
        return q

    async def get_multi(self, filters: MadeItemFilterDto) -> tuple[int, list[MadeItem]]:
        q: Select[Any] = select(MadeItemOrmModel)
        q = self._apply_creator_join(q, filters)
        q = apply_filters(q, self._filter_specs(filters))

        item_model: Any = MadeItemOrmModel
        if filters.latest_only:
            # newest = highest (len(revision), revision), ties by created
            # desc, id desc, the same key as revision_scheme.sort_key.
            # Rows with a NULL part_number have no family to rank against,
            # so they pass regardless of `rn`.
            rn = (
                func.row_number()
                .over(
                    partition_by=MadeItemOrmModel.part_number,
                    order_by=(
                        func.length(MadeItemOrmModel.revision).desc(),
                        MadeItemOrmModel.revision.desc(),
                        MadeItemOrmModel.created.desc(),
                        MadeItemOrmModel.id.desc(),
                    ),
                )
                .label("rn")
            )
            ranked = q.add_columns(rn).subquery()
            item_model = aliased(MadeItemOrmModel, ranked)
            q = select(item_model).where(or_(ranked.c.part_number.is_(None), ranked.c.rn == 1))

        _sort_column_map = {
            "id": item_model.id,
            "article_name": item_model.article_name,
            "changed": item_model.changed,
            "created": item_model.created,
        }
        sort_col = _sort_column_map.get(filters.order_by or "id", item_model.id)
        total, page = await fetch_page(
            self._db,
            q,
            filters.skip,
            filters.limit,
            order_term(sort_col, filters.order_dir, default="desc"),
            options=item_load_options(item_model),
        )
        rows: list[Any] = list(page)
        return total, [item_orm_to_entity(r) for r in rows]

    async def save(self, item: MadeItem) -> MadeItem:
        article_groups = await load_by_ids(self._db, ArticleGroupOrmModel, item.article_group_ids)
        if item.id == 0:
            orm = MadeItemOrmModel(**item_entity_to_dict(item))
            orm.article_groups = article_groups
            self._db.add(orm)
            await self._db.flush()
            return item_orm_to_entity(await self._reload(orm.id))
        existing = await self._get_for_update(item.id)
        if not existing:
            raise ValueError(f"MadeItemOrmModel id={item.id} not found.")
        orm = existing
        for k, v in item_entity_to_dict(item).items():
            setattr(orm, k, v)
        orm.article_groups = article_groups
        await self._db.flush()
        return item_orm_to_entity(await self._reload(orm.id))

    async def delete(self, item: MadeItem) -> None:
        orm = await self._get_for_delete(item.id)
        if orm:
            await self._db.delete(orm)
            await self._db.flush()

    async def merge_references(self, source_id: int, target_id: int) -> None:
        """Points the successor links that name the source item at the
        target. The lots and demands move first, through the made item
        usages port."""
        # A revision chain that ran through the source runs through the
        # target; the target never names itself. A Core UPDATE passes the
        # edit version listener by, so it moves the version itself.
        await self._db.execute(
            sa.update(MadeItemOrmModel)
            .where(
                MadeItemOrmModel.successor_item_id == source_id, MadeItemOrmModel.id != target_id
            )
            .values(successor_item_id=target_id, edit_version=MadeItemOrmModel.edit_version + 1)
            .execution_options(synchronize_session=False)
        )
        await self._db.execute(
            sa.update(MadeItemOrmModel)
            .where(
                MadeItemOrmModel.id == target_id, MadeItemOrmModel.successor_item_id == source_id
            )
            .values(successor_item_id=None, edit_version=MadeItemOrmModel.edit_version + 1)
            .execution_options(synchronize_session=False)
        )
        await self._db.flush()

    async def merge_article_groups(self, source_id: int, target_id: int) -> None:
        source_group_ids = (
            (
                await self._db.execute(
                    sa.select(made_item_article_group_table.c.article_group_id).where(
                        made_item_article_group_table.c.made_item_id == source_id
                    )
                )
            )
            .scalars()
            .all()
        )

        existing_target_ids = set(
            (
                await self._db.execute(
                    sa.select(made_item_article_group_table.c.article_group_id).where(
                        made_item_article_group_table.c.made_item_id == target_id
                    )
                )
            )
            .scalars()
            .all()
        )

        for group_id in source_group_ids:
            if group_id not in existing_target_ids:
                await self._db.execute(
                    made_item_article_group_table.insert().values(
                        made_item_id=target_id, article_group_id=group_id
                    )
                )

        await self._db.execute(
            made_item_article_group_table.delete().where(
                made_item_article_group_table.c.made_item_id == source_id
            )
        )
        await self._db.flush()

    # ── Process steps ───────────────────────────────────────────────────

    async def get_processes(self, made_item_id: int) -> list[MadeItemProcess]:
        rows = (
            await self._db.scalars(
                select(MadeItemProcessOrmModel)
                .where(MadeItemProcessOrmModel.made_item_id == made_item_id)
                .order_by(MadeItemProcessOrmModel.position)
                .options(*process_load_options())
            )
        ).all()
        return [process_orm_to_entity(r) for r in rows]

    async def _reload_process(self, id: int) -> MadeItemProcessOrmModel:
        return (
            await self._db.scalars(
                by_id(MadeItemProcessOrmModel, id, *process_load_options(), refresh=True)
            )
        ).one()

    async def get_process_by_id(self, process_id: int) -> MadeItemProcess | None:
        orm = await self._db.scalar(
            by_id(MadeItemProcessOrmModel, process_id, *process_load_options())
        )
        return process_orm_to_entity(orm) if orm else None

    async def save_process(self, process: MadeItemProcess) -> MadeItemProcess:
        if process.id == 0:
            orm = MadeItemProcessOrmModel(**process_entity_to_dict(process))
            self._db.add(orm)
            await self._db.flush()
            return process_orm_to_entity(await self._reload_process(orm.id))
        existing = await self._db.get(MadeItemProcessOrmModel, process.id)
        if not existing:
            raise ValueError(f"MadeItemProcessOrmModel id={process.id} not found.")
        orm = existing
        for k, v in process_entity_to_dict(process).items():
            setattr(orm, k, v)
        await self._db.flush()
        return process_orm_to_entity(await self._reload_process(orm.id))

    async def delete_process(self, process: MadeItemProcess) -> None:
        orm = await self._db.get(MadeItemProcessOrmModel, process.id)
        if orm:
            await self._db.delete(orm)
            await self._db.flush()

    async def reorder_processes(
        self, made_item_id: int, ordered_process_ids: list[int]
    ) -> list[MadeItemProcess]:
        rows = {
            r.id: r
            for r in (
                await self._db.scalars(
                    select(MadeItemProcessOrmModel)
                    .where(MadeItemProcessOrmModel.made_item_id == made_item_id)
                    .options(*process_load_options())
                )
            ).all()
        }
        ordered_rows = [rows[process_id] for process_id in ordered_process_ids]
        for position, row in enumerate(ordered_rows):
            row.position = position

        # A group whose steps stay adjacent in the new order survives; one
        # torn apart by the reorder splits into separate groups.
        new_group_indexes = normalize_process_groups(
            [process_orm_to_entity(row) for row in ordered_rows]
        )
        for row, group_index in zip(ordered_rows, new_group_indexes, strict=True):
            row.group_index = group_index

        await self._db.flush()
        return await self.get_processes(made_item_id)

    async def set_process_groups(
        self, made_item_id: int, groups: list[list[int]]
    ) -> list[MadeItemProcess]:
        rows = {
            r.id: r
            for r in (
                await self._db.scalars(
                    select(MadeItemProcessOrmModel).where(
                        MadeItemProcessOrmModel.made_item_id == made_item_id
                    )
                )
            ).all()
        }
        for group_index, group in enumerate(groups):
            for process_id in group:
                rows[process_id].group_index = group_index
        await self._db.flush()
        return await self.get_processes(made_item_id)
