"""
Concrete implementation of IProductRepository using SQLAlchemy + Postgres.
"""

from functools import lru_cache
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.interfaces import ORMOption

from src.modules.catalogue.adapters.outbound.persistence.mappers.customer_mappers import (
    customer_orm_to_entity,
)
from src.modules.catalogue.adapters.outbound.persistence.models.customer_model import (
    CustomerOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.date_range import day_after_utc
from src.modules.platform.adapters.outbound.persistence.date_range import day_start_utc
from src.modules.platform.adapters.outbound.persistence.like_escape import contains_ci
from src.modules.platform.adapters.outbound.persistence.statements import by_id
from src.modules.platform.adapters.outbound.persistence.statements import fetch_page
from src.modules.platform.adapters.outbound.persistence.statements import lock_row
from src.modules.platform.adapters.outbound.persistence.statements import order_term
from src.modules.platform.adapters.outbound.persistence.tenant_zone import date_filter_zone
from src.modules.platform.adapters.outbound.persistence.user_loading import load_user
from src.modules.platform.adapters.outbound.persistence.user_loading import user_orm_to_entity
from src.modules.workspace.adapters.outbound.persistence.models.product_model import ProductOrmModel
from src.modules.workspace.domain.entities.product import Product
from src.modules.workspace.ports.outbound.repositories.product_repository import IProductRepository
from src.modules.workspace.ports.outbound.repositories.product_repository import ProductFilterDto

# ── Mapping helpers ───────────────────────────────────────────────────


@lru_cache(maxsize=1)
def product_load_options() -> tuple[ORMOption, ...]:
    """Everything product_orm_to_entity() dereferences, including the nested
    customer mapper. Built on first call rather than at import, because
    constructing a loader option configures the mapper registry before every
    model module is registered."""
    return (
        load_user(ProductOrmModel.customer, CustomerOrmModel.creator),
        load_user(ProductOrmModel.creator),
    )


def product_orm_to_entity(orm: ProductOrmModel) -> Product:
    return Product(
        id=orm.id,
        public_id=orm.public_id,
        product_number=orm.product_number,
        customer_id=orm.customer_id,
        customer=customer_orm_to_entity(orm.customer) if orm.customer else None,
        description=orm.description,
        designation=orm.designation,
        machine_type=orm.machine_type,
        installation_site=orm.installation_site,
        installation_location=orm.installation_location,
        planned_placing_on_market=orm.planned_placing_on_market,
        legal_basis=orm.legal_basis,
        plc_environment_id=orm.plc_environment_id,
        contains_pneumatics=orm.contains_pneumatics,
        contains_hydraulics=orm.contains_hydraulics,
        contains_electrics=orm.contains_electrics,
        contains_robotics=orm.contains_robotics,
        is_active=orm.is_active,
        designated_user_id=orm.designated_user_id,
        created=orm.created,
        archived=orm.archived,
        creator_id=orm.creator_id or 0,
        creator=user_orm_to_entity(orm.creator) if orm.creator else None,
        edit_version=orm.edit_version,
    )


def _entity_to_dict(product: Product) -> dict[str, Any]:
    return {
        "product_number": product.product_number,
        "customer_id": product.customer_id,
        "description": product.description,
        "designation": product.designation,
        "machine_type": product.machine_type,
        "installation_site": product.installation_site,
        "installation_location": product.installation_location,
        "planned_placing_on_market": product.planned_placing_on_market,
        "legal_basis": product.legal_basis,
        "plc_environment_id": product.plc_environment_id,
        "contains_pneumatics": product.contains_pneumatics,
        "contains_hydraulics": product.contains_hydraulics,
        "contains_electrics": product.contains_electrics,
        "contains_robotics": product.contains_robotics,
        "is_active": product.is_active,
        "designated_user_id": product.designated_user_id,
        "created": product.created,
        "archived": product.archived,
        "creator_id": product.creator_id or None,
    }


# ── Repository ────────────────────────────────────────────────────────


class SqlAlchemyProductRepository(IProductRepository):
    """Implements IProductRepository."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Queries ───────────────────────────────────────────────────────

    async def get_by_id(self, id: int) -> Product | None:
        orm = await self._db.scalar(by_id(ProductOrmModel, id, *product_load_options()).limit(1))
        return product_orm_to_entity(orm) if orm else None

    async def lock_for_update(self, id: int) -> None:
        await lock_row(self._db, ProductOrmModel, id)

    async def get_by_product_number(self, product_number: str) -> Product | None:
        """Filters archived rows, matching get_multi. Safe because
        `product_number`'s uniqueness is enforced by a partial index
        (`uq_product_product_number_active`, WHERE archived IS false), so
        an archived row no longer reserves its number and the uniqueness
        pre-check this backs must not see one."""
        orm = await self._db.scalar(
            select(ProductOrmModel)
            .where(
                ProductOrmModel.product_number == product_number,
                ProductOrmModel.archived.is_(False),
            )
            .options(*product_load_options())
            .limit(1)
        )
        return product_orm_to_entity(orm) if orm else None

    async def get_by_designated_user_id(self, user_id: int) -> list[Product]:
        rows = (
            await self._db.scalars(
                select(ProductOrmModel)
                .where(
                    ProductOrmModel.designated_user_id == user_id,
                    ProductOrmModel.archived.is_(False),
                )
                .options(*product_load_options())
            )
        ).all()
        return [product_orm_to_entity(r) for r in rows]

    async def get_multi(self, filters: ProductFilterDto) -> tuple[int, list[Product]]:
        zone = await date_filter_zone(self._db, filters.created_from, filters.created_to)
        q = select(ProductOrmModel)
        if not filters.include_archived:
            q = q.where(ProductOrmModel.archived.is_(False))

        if filters.id is not None:
            q = q.where(ProductOrmModel.id == filters.id)
        if filters.is_active is not None:
            q = q.where(ProductOrmModel.is_active.is_(filters.is_active))
        if filters.designated_user_id is not None:
            q = q.where(ProductOrmModel.designated_user_id == filters.designated_user_id)
        if filters.product_number:
            q = q.where(contains_ci(ProductOrmModel.product_number, filters.product_number))
        if filters.customer_id is not None:
            q = q.where(ProductOrmModel.customer_id == filters.customer_id)
        if filters.description:
            q = q.where(contains_ci(ProductOrmModel.description, filters.description))
        if filters.creator_id is not None:
            q = q.where(ProductOrmModel.creator_id == filters.creator_id)
        if filters.created_from:
            q = q.where(ProductOrmModel.created >= day_start_utc(filters.created_from, zone))
        if filters.created_to:
            q = q.where(ProductOrmModel.created < day_after_utc(filters.created_to, zone))
        if filters.search:
            term = filters.search
            q = q.where(
                (contains_ci(ProductOrmModel.product_number, term))
                | (contains_ci(ProductOrmModel.description, term))
            )

        _sort_column_map = {
            "id": ProductOrmModel.id,
            "product_number": ProductOrmModel.product_number,
            "created": ProductOrmModel.created,
        }
        sort_col = _sort_column_map.get(
            filters.order_by or "product_number", ProductOrmModel.product_number
        )
        total, rows = await fetch_page(
            self._db,
            q,
            filters.skip,
            filters.limit,
            order_term(sort_col, filters.order_dir, default="desc"),
            options=product_load_options(),
        )
        return total, [product_orm_to_entity(r) for r in rows]

    async def get_active(self, limit: int) -> list[Product]:
        _, products = await self.get_multi(
            ProductFilterDto(
                is_active=True, limit=limit, order_by="product_number", order_dir="asc"
            )
        )
        return products

    # ── Mutations ─────────────────────────────────────────────────────

    async def save(self, product: Product) -> Product:
        if product.id == 0:
            orm = ProductOrmModel(**_entity_to_dict(product))
            self._db.add(orm)
            await self._db.flush()
            new_id = orm.id
            return product_orm_to_entity(await self._reload(new_id))
        existing = await self._db.get(ProductOrmModel, product.id)
        if not existing:
            raise ValueError(f"ProductOrmModel id={product.id} not found for update.")
        orm = existing
        for key, value in _entity_to_dict(product).items():
            setattr(orm, key, value)
        await self._db.flush()
        return product_orm_to_entity(await self._reload(product.id))

    async def _reload(self, id: int) -> ProductOrmModel:
        return (
            await self._db.scalars(
                by_id(ProductOrmModel, id, *product_load_options(), refresh=True)
            )
        ).one()

    async def delete(self, product: Product) -> None:
        """Hard delete. Archiving through save() is the usual way to remove a row."""
        orm = await self._db.get(
            ProductOrmModel,
            product.id,
            options=[
                selectinload(ProductOrmModel.projects),
                selectinload(ProductOrmModel.files),
            ],
            populate_existing=True,
        )
        if orm:
            await self._db.delete(orm)
            await self._db.flush()
