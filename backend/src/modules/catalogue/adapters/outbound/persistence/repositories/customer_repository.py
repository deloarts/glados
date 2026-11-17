"""
Concrete implementation of ICustomerRepository using SQLAlchemy + Postgres.
"""

from datetime import datetime
from functools import lru_cache
from typing import Any

import sqlalchemy as sa
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.interfaces import ORMOption

from src.modules.catalogue.adapters.outbound.persistence.mappers.customer_mappers import (
    customer_orm_to_entity,
)
from src.modules.catalogue.adapters.outbound.persistence.models.customer_model import (
    CustomerOrmModel,
)
from src.modules.catalogue.domain.entities.customer import Customer
from src.modules.catalogue.ports.outbound.repositories.customer_repository import CustomerFilterDto
from src.modules.catalogue.ports.outbound.repositories.customer_repository import (
    ICustomerRepository,
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

# ── Mapping helpers ───────────────────────────────────────────────────


@lru_cache(maxsize=1)
def customer_load_options() -> tuple[ORMOption, ...]:
    """Everything customer_orm_to_entity() dereferences. Built on first call rather
    than at import, because constructing a loader option configures the
    mapper registry before every model module is registered."""
    return (load_user(CustomerOrmModel.creator), load_user(CustomerOrmModel.changed_by))


def _entity_to_dict(customer: Customer) -> dict[str, Any]:
    return {
        "created": customer.created,
        "name": customer.name,
        "legal_name": customer.legal_name,
        "vat_id": customer.vat_id,
        "level": customer.level.value,
        "street": customer.street,
        "city": customer.city,
        "country": customer.country,
        "postal_code": customer.postal_code,
        "email": customer.email,
        "phone": customer.phone,
        "weblink": customer.weblink,
        "creator_id": customer.creator_id,
        "changed": customer.changed,
        "changes": customer.changes,
        "archived": customer.archived,
    }


# ── Repository ────────────────────────────────────────────────────────

# Workspace's tables that name a customer, named rather than imported, since
# Catalogue sits below Workspace.
_product_table = sa.table("product_table", sa.column("customer_id", sa.Integer))
_project_table = sa.table("project_table", sa.column("customer_id", sa.Integer))


class SqlAlchemyCustomerRepository(ICustomerRepository):
    """Implements ICustomerRepository."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Queries ───────────────────────────────────────────────────────

    async def get_by_id(self, id: int) -> Customer | None:
        orm = await self._db.scalar(by_id(CustomerOrmModel, id, *customer_load_options()).limit(1))
        return customer_orm_to_entity(orm) if orm else None

    async def lock_for_update(self, id: int) -> None:
        await lock_row(self._db, CustomerOrmModel, id)

    async def get_by_vat_id(self, vat_id: str) -> Customer | None:
        """Filters archived rows, matching get_multi. Safe because
        `vat_id`'s uniqueness is enforced by a partial index
        (`uq_customer_vat_id_active`, WHERE archived IS false), so an
        archived row no longer reserves its VAT id and the uniqueness
        pre-check this backs must not see one."""
        orm = await self._db.scalar(
            select(CustomerOrmModel)
            .where(CustomerOrmModel.vat_id == vat_id, CustomerOrmModel.archived.is_(False))
            .options(*customer_load_options())
            .limit(1)
        )
        return customer_orm_to_entity(orm) if orm else None

    async def get_multi(self, filters: CustomerFilterDto) -> tuple[int, list[Customer]]:
        zone = await date_filter_zone(
            self._db,
            filters.created_from,
            filters.created_to,
            filters.changed_from,
            filters.changed_to,
        )
        q = select(CustomerOrmModel)
        if not filters.include_archived:
            q = q.where(CustomerOrmModel.archived.is_(False))

        if filters.id is not None:
            q = q.where(CustomerOrmModel.id == filters.id)
        if filters.name:
            q = q.where(contains_ci(CustomerOrmModel.name, filters.name))
        if filters.vat_id:
            q = q.where(CustomerOrmModel.vat_id == filters.vat_id)
        if filters.legal_name:
            q = q.where(contains_ci(CustomerOrmModel.legal_name, filters.legal_name))
        if filters.level:
            q = q.where(CustomerOrmModel.level == filters.level)
        if filters.address:
            q = q.where(
                contains_ci(CustomerOrmModel.street, filters.address)
                | contains_ci(CustomerOrmModel.postal_code, filters.address)
                | contains_ci(CustomerOrmModel.city, filters.address)
            )
        if filters.country:
            q = q.where(contains_ci(CustomerOrmModel.country, filters.country))
        if filters.email:
            q = q.where(contains_ci(CustomerOrmModel.email, filters.email))
        if filters.creator_id is not None:
            q = q.where(CustomerOrmModel.creator_id == filters.creator_id)
        if filters.changed_by_id is not None:
            q = q.where(CustomerOrmModel.changed_by_id == filters.changed_by_id)
        if filters.created_from:
            q = q.where(CustomerOrmModel.created >= day_start_utc(filters.created_from, zone))
        if filters.created_to:
            q = q.where(CustomerOrmModel.created < day_after_utc(filters.created_to, zone))
        if filters.changed_from:
            q = q.where(CustomerOrmModel.changed >= day_start_utc(filters.changed_from, zone))
        if filters.changed_to:
            q = q.where(CustomerOrmModel.changed < day_after_utc(filters.changed_to, zone))
        if filters.search:
            term = filters.search
            q = q.where(
                (contains_ci(CustomerOrmModel.name, term))
                | (contains_ci(CustomerOrmModel.legal_name, term))
                | (contains_ci(CustomerOrmModel.vat_id, term))
            )

        _sort_column_map = {
            "id": CustomerOrmModel.id,
            "name": CustomerOrmModel.name,
            "created": CustomerOrmModel.created,
            "changed": CustomerOrmModel.changed,
        }
        sort_col = _sort_column_map.get(filters.order_by or "name", CustomerOrmModel.name)
        total, rows = await fetch_page(
            self._db,
            q,
            filters.skip,
            filters.limit,
            order_term(sort_col, filters.order_dir, default="desc"),
            options=customer_load_options(),
        )
        return total, [customer_orm_to_entity(r) for r in rows]

    async def get_aggregate(self) -> tuple[int, datetime | None]:
        count, max_changed = (
            await self._db.execute(
                select(func.count(CustomerOrmModel.id), func.max(CustomerOrmModel.changed))
            )
        ).one()
        return count, max_changed

    # ── Mutations ─────────────────────────────────────────────────────

    async def save(self, customer: Customer) -> Customer:
        if customer.id == 0:
            orm = CustomerOrmModel(**_entity_to_dict(customer))
            self._db.add(orm)
            await self._db.flush()
            new_id = orm.id
            return customer_orm_to_entity(await self._reload(new_id))
        existing = await self._db.get(CustomerOrmModel, customer.id)
        if not existing:
            raise ValueError(f"CustomerOrmModel id={customer.id} not found for update.")
        orm = existing
        for key, value in _entity_to_dict(customer).items():
            setattr(orm, key, value)
        await self._db.flush()
        return customer_orm_to_entity(await self._reload(customer.id))

    async def _reload(self, id: int) -> CustomerOrmModel:
        return (
            await self._db.scalars(
                by_id(CustomerOrmModel, id, *customer_load_options(), refresh=True)
            )
        ).one()

    async def delete(self, customer: Customer) -> None:
        """Hard delete. Archiving through save() is the usual way to remove a row."""
        orm = await self._db.get(CustomerOrmModel, customer.id, populate_existing=True)
        if orm:
            # The products and projects of Workspace that name the customer
            # let go of it first, since no ORM relationship reaches them.
            for linked in (_product_table, _project_table):
                await self._db.execute(
                    sa.update(linked)
                    .where(linked.c.customer_id == customer.id)
                    .values(customer_id=None)
                    .execution_options(synchronize_session=False)
                )
            await self._db.delete(orm)
            await self._db.flush()
