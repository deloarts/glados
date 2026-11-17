"""
Concrete implementation of IContactRepository using SQLAlchemy.
"""

from functools import lru_cache
from typing import Any

from sqlalchemy import case
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.interfaces import ORMOption

from src.modules.catalogue.adapters.outbound.persistence.mappers.contact_mappers import (
    contact_orm_to_entity,
)
from src.modules.catalogue.adapters.outbound.persistence.models.contact_model import ContactOrmModel
from src.modules.catalogue.adapters.outbound.persistence.models.customer_model import (
    CustomerOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.supplier_model import (
    SupplierOrmModel,
)
from src.modules.catalogue.domain.entities.contact import Contact
from src.modules.catalogue.ports.outbound.repositories.contact_repository import ContactFilterDto
from src.modules.catalogue.ports.outbound.repositories.contact_repository import IContactRepository
from src.modules.platform.adapters.outbound.persistence.like_escape import contains_ci
from src.modules.platform.adapters.outbound.persistence.statements import by_id
from src.modules.platform.adapters.outbound.persistence.statements import fetch_page
from src.modules.platform.adapters.outbound.persistence.statements import lock_row
from src.modules.platform.adapters.outbound.persistence.statements import order_term
from src.modules.platform.adapters.outbound.persistence.user_loading import load_user


@lru_cache(maxsize=1)
def contact_load_options() -> tuple[ORMOption, ...]:
    """Everything contact_orm_to_entity() dereferences. Built on first call
    rather than at import, because constructing a loader option configures
    the mapper registry before every model module is registered."""
    return (
        load_user(ContactOrmModel.creator),
        load_user(ContactOrmModel.changed_by),
        selectinload(ContactOrmModel.customer),
        selectinload(ContactOrmModel.supplier),
    )


def _entity_to_dict(contact: Contact) -> dict[str, Any]:
    return {
        "created": contact.created,
        "changed": contact.changed,
        "archived": contact.archived,
        "anonymised_at": contact.anonymised_at,
        "name": contact.name,
        "role": contact.role,
        "email": contact.email,
        "phone": contact.phone,
        "mobile": contact.mobile,
        "note": contact.note,
        "customer_id": contact.customer_id,
        "supplier_id": contact.supplier_id,
        "receives_request_mails": contact.receives_request_mails,
        "receives_order_mails": contact.receives_order_mails,
        "creator_id": contact.creator_id,
    }


class SqlAlchemyContactRepository(IContactRepository):
    """Implements IContactRepository."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Queries ───────────────────────────────────────────────────────

    async def get_by_id(self, id: int) -> Contact | None:
        orm = await self._db.scalar(by_id(ContactOrmModel, id, *contact_load_options()).limit(1))
        return contact_orm_to_entity(orm) if orm else None

    async def get_by_ids(self, ids: list[int]) -> list[Contact]:
        if not ids:
            return []
        rows = await self._db.scalars(
            select(ContactOrmModel)
            .where(ContactOrmModel.id.in_(set(ids)))
            .options(*contact_load_options())
        )
        return [contact_orm_to_entity(orm) for orm in rows]

    async def lock_for_update(self, id: int) -> None:
        await lock_row(self._db, ContactOrmModel, id)

    async def get_multi(self, filters: ContactFilterDto) -> tuple[int, list[Contact]]:
        customer = aliased(CustomerOrmModel)
        supplier = aliased(SupplierOrmModel)
        organisation_name = func.coalesce(customer.name, supplier.name)
        q = (
            select(ContactOrmModel)
            .outerjoin(customer, ContactOrmModel.customer_id == customer.id)
            .outerjoin(supplier, ContactOrmModel.supplier_id == supplier.id)
        )
        if not filters.include_archived:
            q = q.where(ContactOrmModel.archived.is_(False))
        if filters.customer_id is not None:
            q = q.where(ContactOrmModel.customer_id == filters.customer_id)
        if filters.supplier_id is not None:
            q = q.where(ContactOrmModel.supplier_id == filters.supplier_id)
        if filters.organisation_kind == "customer":
            q = q.where(ContactOrmModel.customer_id.is_not(None))
        elif filters.organisation_kind == "supplier":
            q = q.where(ContactOrmModel.supplier_id.is_not(None))
        elif filters.organisation_kind == "none":
            q = q.where(
                ContactOrmModel.customer_id.is_(None), ContactOrmModel.supplier_id.is_(None)
            )
        if filters.name:
            q = q.where(
                contains_ci(ContactOrmModel.name, filters.name)
                | contains_ci(ContactOrmModel.role, filters.name)
            )
        if filters.email:
            q = q.where(contains_ci(ContactOrmModel.email, filters.email))
        if filters.phone:
            q = q.where(
                contains_ci(ContactOrmModel.phone, filters.phone)
                | contains_ci(ContactOrmModel.mobile, filters.phone)
            )
        if filters.search:
            term = filters.search
            q = q.where(
                or_(
                    contains_ci(ContactOrmModel.name, term),
                    contains_ci(ContactOrmModel.role, term),
                    contains_ci(ContactOrmModel.email, term),
                    contains_ci(ContactOrmModel.phone, term),
                    contains_ci(ContactOrmModel.mobile, term),
                    contains_ci(customer.name, term),
                    contains_ci(supplier.name, term),
                )
            )

        if filters.order_by == "organisation":
            # Contacts without an organisation come last in either direction,
            # so the groups of an organisation stay together across pages.
            order: tuple[Any, ...] = (
                case((organisation_name.is_(None), 1), else_=0),
                order_term(organisation_name, filters.order_dir, default="asc"),
                ContactOrmModel.name.asc(),
            )
        else:
            sort_columns = {
                "name": ContactOrmModel.name,
                "created": ContactOrmModel.created,
                "changed": ContactOrmModel.changed,
            }
            column = sort_columns.get(filters.order_by or "name", ContactOrmModel.name)
            order = (order_term(column, filters.order_dir, default="asc"),)
        total, rows = await fetch_page(
            self._db,
            q,
            filters.skip,
            filters.limit,
            *order,
            ContactOrmModel.id.asc(),
            options=contact_load_options(),
        )
        return total, [contact_orm_to_entity(r) for r in rows]

    async def get_mail_recipients(self, supplier_id: int) -> list[Contact]:
        rows = await self._db.scalars(
            select(ContactOrmModel)
            .where(
                ContactOrmModel.supplier_id == supplier_id,
                ContactOrmModel.archived.is_(False),
                ContactOrmModel.email.is_not(None),
                ContactOrmModel.email != "",
                ContactOrmModel.receives_request_mails.is_(True)
                | ContactOrmModel.receives_order_mails.is_(True),
            )
            .order_by(ContactOrmModel.name.asc(), ContactOrmModel.id.asc())
            .options(*contact_load_options())
        )
        return [contact_orm_to_entity(orm) for orm in rows]

    async def get_mail_contacts_of_customer(self, customer_id: int) -> list[Contact]:
        rows = await self._db.scalars(
            select(ContactOrmModel)
            .where(
                ContactOrmModel.customer_id == customer_id,
                ContactOrmModel.archived.is_(False),
                ContactOrmModel.email.is_not(None),
                ContactOrmModel.email != "",
            )
            .order_by(ContactOrmModel.name.asc(), ContactOrmModel.id.asc())
            .options(*contact_load_options())
        )
        return [contact_orm_to_entity(orm) for orm in rows]

    # ── Mutations ─────────────────────────────────────────────────────

    async def save(self, contact: Contact) -> Contact:
        if contact.id == 0:
            orm = ContactOrmModel(**_entity_to_dict(contact))
            self._db.add(orm)
            await self._db.flush()
            return contact_orm_to_entity(await self._reload(orm.id))
        existing = await self._db.get(ContactOrmModel, contact.id)
        if not existing:
            raise ValueError(f"ContactOrmModel id={contact.id} not found for update.")
        for key, value in _entity_to_dict(contact).items():
            setattr(existing, key, value)
        await self._db.flush()
        return contact_orm_to_entity(await self._reload(contact.id))

    async def _reload(self, id: int) -> ContactOrmModel:
        return (
            await self._db.scalars(
                by_id(ContactOrmModel, id, *contact_load_options(), refresh=True)
            )
        ).one()
