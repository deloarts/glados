"""
Concrete implementation of ISupplierRepository using SQLAlchemy + Postgres.
"""

from datetime import datetime
from functools import lru_cache
from typing import Any

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.interfaces import ORMOption

from src.modules.catalogue.adapters.outbound.persistence.mappers.catalogue_mappers import (
    article_group_orm_to_entity,
)
from src.modules.catalogue.adapters.outbound.persistence.mappers.catalogue_mappers import (
    fabrication_method_orm_to_entity,
)
from src.modules.catalogue.adapters.outbound.persistence.models.article_group_model import (
    ArticleGroupOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.fabrication_method_model import (
    FabricationMethodOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.supplier_model import (
    SupplierOrmModel,
)
from src.modules.catalogue.domain.entities.supplier import Supplier
from src.modules.catalogue.domain.value_objects.supplier_level import SupplierLevel
from src.modules.catalogue.ports.outbound.catalogue_queries import SupplierFilterDto
from src.modules.catalogue.ports.outbound.repositories.supplier_repository import (
    ISupplierRepository,
)
from src.modules.platform.adapters.outbound.persistence.like_escape import contains_ci
from src.modules.platform.adapters.outbound.persistence.mapping_common import archived_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import changed_by_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import creator_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.adapters.outbound.persistence.statements import by_id
from src.modules.platform.adapters.outbound.persistence.statements import fetch_page
from src.modules.platform.adapters.outbound.persistence.statements import load_by_ids
from src.modules.platform.adapters.outbound.persistence.statements import lock_row
from src.modules.platform.adapters.outbound.persistence.statements import order_term
from src.modules.platform.adapters.outbound.persistence.user_loading import load_user

# ── Mapping helpers ───────────────────────────────────────────────────


@lru_cache(maxsize=1)
def _load_options() -> tuple[ORMOption, ...]:
    """Everything _orm_to_entity() dereferences, including the creator and
    changer read by the nested fabrication method and article group mappers.
    Built on first call rather than at import, because constructing a loader
    option configures the mapper registry before every model module is
    registered."""
    return (
        load_user(SupplierOrmModel.creator),
        load_user(SupplierOrmModel.changed_by),
        load_user(SupplierOrmModel.capabilities, FabricationMethodOrmModel.creator),
        load_user(SupplierOrmModel.capabilities, FabricationMethodOrmModel.changed_by),
        load_user(SupplierOrmModel.article_groups, ArticleGroupOrmModel.creator),
        load_user(SupplierOrmModel.article_groups, ArticleGroupOrmModel.changed_by),
    )


def _orm_to_entity(orm: SupplierOrmModel) -> Supplier:
    return Supplier(
        id=orm.id,
        public_id=orm.public_id,
        created=utc_aware(orm.created),
        name=orm.name,
        legal_name=orm.legal_name,
        vat_id=orm.vat_id,
        level=SupplierLevel(orm.level),
        external_lead_time_days=orm.external_lead_time_days,
        edp_code=orm.edp_code,
        edp_type_number_first=orm.edp_type_number_first,
        capability_ids=[c.id for c in orm.capabilities],
        article_group_ids=[g.id for g in orm.article_groups],
        street=orm.street,
        city=orm.city,
        country=orm.country,
        postal_code=orm.postal_code,
        email=orm.email,
        phone=orm.phone,
        weblink=orm.weblink,
        order_email=orm.order_email,
        order_language=orm.order_language,
        order_template=orm.order_template,
        request_email=orm.request_email,
        request_language=orm.request_language,
        request_template=orm.request_template,
        capabilities=[fabrication_method_orm_to_entity(c) for c in orm.capabilities],
        article_groups=[article_group_orm_to_entity(g) for g in orm.article_groups],
        **archived_kwargs(utc_aware(orm.changed), orm.changes, orm.archived),
        **creator_kwargs(orm.creator_id, orm.creator),
        **changed_by_kwargs(orm.changed_by_id, orm.changed_by),
        edit_version=orm.edit_version,
    )


def _entity_to_dict(supplier: Supplier) -> dict[str, Any]:
    return {
        "created": supplier.created,
        "name": supplier.name,
        "legal_name": supplier.legal_name,
        "vat_id": supplier.vat_id,
        "level": supplier.level.value,
        "external_lead_time_days": supplier.external_lead_time_days,
        "edp_code": supplier.edp_code,
        "edp_type_number_first": supplier.edp_type_number_first,
        "street": supplier.street,
        "city": supplier.city,
        "country": supplier.country,
        "postal_code": supplier.postal_code,
        "email": supplier.email,
        "phone": supplier.phone,
        "weblink": supplier.weblink,
        "order_email": supplier.order_email,
        "order_language": supplier.order_language,
        "order_template": supplier.order_template,
        "request_email": supplier.request_email,
        "request_language": supplier.request_language,
        "request_template": supplier.request_template,
        "creator_id": supplier.creator_id,
        **archived_kwargs(supplier.changed, supplier.changes, supplier.archived),
    }


# ── Repository ────────────────────────────────────────────────────────


class SqlAlchemySupplierRepository(ISupplierRepository):
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, id: int) -> Supplier | None:
        orm = await self._db.scalar(by_id(SupplierOrmModel, id, *_load_options()).limit(1))
        return _orm_to_entity(orm) if orm else None

    async def lock_for_update(self, id: int) -> None:
        await lock_row(self._db, SupplierOrmModel, id)

    async def get_by_vat_id(self, vat_id: str) -> Supplier | None:
        orm = await self._db.scalar(
            select(SupplierOrmModel)
            .where(SupplierOrmModel.vat_id == vat_id, SupplierOrmModel.archived.is_(False))
            .options(*_load_options())
            .limit(1)
        )
        return _orm_to_entity(orm) if orm else None

    async def get_by_edp_code(self, edp_code: str) -> Supplier | None:
        orm = await self._db.scalar(
            select(SupplierOrmModel)
            .where(SupplierOrmModel.edp_code == edp_code, SupplierOrmModel.archived.is_(False))
            .options(*_load_options())
            .limit(1)
        )
        return _orm_to_entity(orm) if orm else None

    async def get_multi(self, filters: SupplierFilterDto) -> tuple[int, list[Supplier]]:
        q = select(SupplierOrmModel)
        if not filters.include_archived:
            q = q.where(SupplierOrmModel.archived.is_(False))

        if filters.id is not None:
            q = q.where(SupplierOrmModel.id == filters.id)
        if filters.name:
            q = q.where(contains_ci(SupplierOrmModel.name, filters.name))
        if filters.vat_id:
            q = q.where(contains_ci(SupplierOrmModel.vat_id, filters.vat_id))
        if filters.legal_name:
            q = q.where(contains_ci(SupplierOrmModel.legal_name, filters.legal_name))
        if filters.level:
            q = q.where(SupplierOrmModel.level == filters.level)
        if filters.address:
            q = q.where(
                contains_ci(SupplierOrmModel.street, filters.address)
                | contains_ci(SupplierOrmModel.postal_code, filters.address)
                | contains_ci(SupplierOrmModel.city, filters.address)
            )
        if filters.country:
            q = q.where(contains_ci(SupplierOrmModel.country, filters.country))
        if filters.email:
            q = q.where(contains_ci(SupplierOrmModel.email, filters.email))
        if filters.capability_id is not None:
            q = q.where(
                SupplierOrmModel.capabilities.any(
                    FabricationMethodOrmModel.id == filters.capability_id
                )
            )
        if filters.article_group_id is not None:
            q = q.where(
                SupplierOrmModel.article_groups.any(
                    ArticleGroupOrmModel.id == filters.article_group_id
                )
            )
        if filters.creator_id is not None:
            q = q.where(SupplierOrmModel.creator_id == filters.creator_id)
        if filters.changed_by_id is not None:
            q = q.where(SupplierOrmModel.changed_by_id == filters.changed_by_id)
        if filters.created_from:
            q = q.where(SupplierOrmModel.created >= filters.created_from)
        if filters.created_to:
            q = q.where(SupplierOrmModel.created <= filters.created_to)
        if filters.changed_from:
            q = q.where(SupplierOrmModel.changed >= filters.changed_from)
        if filters.changed_to:
            q = q.where(SupplierOrmModel.changed <= filters.changed_to)
        if filters.search:
            term = filters.search
            q = q.where(
                (contains_ci(SupplierOrmModel.name, term))
                | (contains_ci(SupplierOrmModel.legal_name, term))
                | (contains_ci(SupplierOrmModel.vat_id, term))
            )

        _sort_column_map = {
            "id": SupplierOrmModel.id,
            "name": SupplierOrmModel.name,
            "created": SupplierOrmModel.created,
            "changed": SupplierOrmModel.changed,
        }
        sort_col = _sort_column_map.get(filters.order_by or "name", SupplierOrmModel.name)
        total, rows = await fetch_page(
            self._db,
            q,
            filters.skip,
            filters.limit,
            order_term(sort_col, filters.order_dir, default="asc"),
            options=_load_options(),
        )
        return total, [_orm_to_entity(r) for r in rows]

    async def get_aggregate(self) -> tuple[int, datetime | None]:
        count, max_changed = (
            await self._db.execute(
                select(func.count(SupplierOrmModel.id), func.max(SupplierOrmModel.changed))
            )
        ).one()
        return count, max_changed

    async def save(self, supplier: Supplier) -> Supplier:
        capabilities = await load_by_ids(
            self._db, FabricationMethodOrmModel, supplier.capability_ids
        )
        article_groups = await load_by_ids(
            self._db, ArticleGroupOrmModel, supplier.article_group_ids
        )
        if supplier.id == 0:
            orm = SupplierOrmModel(**_entity_to_dict(supplier))
            orm.capabilities = capabilities
            orm.article_groups = article_groups
            self._db.add(orm)
            await self._db.flush()
            new_id = orm.id
            return _orm_to_entity(await self._reload(new_id))
        # The collections are reassigned below, which loads the old ones first.
        existing = await self._db.get(
            SupplierOrmModel,
            supplier.id,
            options=[
                selectinload(SupplierOrmModel.capabilities),
                selectinload(SupplierOrmModel.article_groups),
            ],
            populate_existing=True,
        )
        if not existing:
            raise ValueError(f"SupplierOrmModel id={supplier.id} not found.")
        orm = existing
        for key, value in _entity_to_dict(supplier).items():
            setattr(orm, key, value)
        orm.capabilities = capabilities
        orm.article_groups = article_groups
        await self._db.flush()
        return _orm_to_entity(await self._reload(supplier.id))

    async def _reload(self, id: int) -> SupplierOrmModel:
        return (
            await self._db.scalars(by_id(SupplierOrmModel, id, *_load_options(), refresh=True))
        ).one()

    async def delete(self, supplier: Supplier) -> None:
        """Hard delete. Archiving through save() is the usual way to remove a row."""
        # Deleting clears the association rows, which needs both collections loaded.
        orm = await self._db.get(
            SupplierOrmModel,
            supplier.id,
            options=[
                selectinload(SupplierOrmModel.capabilities),
                selectinload(SupplierOrmModel.article_groups),
            ],
            populate_existing=True,
        )
        if orm:
            await self._db.delete(orm)
            await self._db.flush()
