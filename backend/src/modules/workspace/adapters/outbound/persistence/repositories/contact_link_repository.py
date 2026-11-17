"""
Concrete implementation of IContactLinkRepository using SQLAlchemy. The
product and project links live in two tables of the same shape, so every
method picks the table by the link's owner.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.workspace.adapters.outbound.persistence.models.contact_link_model import (
    ProductContactOrmModel,
)
from src.modules.workspace.adapters.outbound.persistence.models.contact_link_model import (
    ProjectContactOrmModel,
)
from src.modules.workspace.adapters.outbound.persistence.models.product_model import ProductOrmModel
from src.modules.workspace.adapters.outbound.persistence.models.project_model import ProjectOrmModel
from src.modules.workspace.domain.entities.contact_link import ContactLink
from src.modules.workspace.domain.value_objects.contact_link_owner import ContactLinkOwner
from src.modules.workspace.ports.outbound.repositories.contact_link_repository import (
    ContactUsageRow,
)
from src.modules.workspace.ports.outbound.repositories.contact_link_repository import (
    IContactLinkRepository,
)

_LinkModel = type[ProductContactOrmModel] | type[ProjectContactOrmModel]


def _model(owner: ContactLinkOwner) -> _LinkModel:
    return ProductContactOrmModel if owner == ContactLinkOwner.PRODUCT else ProjectContactOrmModel


def _owner_column(owner: ContactLinkOwner) -> Any:
    if owner == ContactLinkOwner.PRODUCT:
        return ProductContactOrmModel.product_id
    return ProjectContactOrmModel.project_id


def _to_entity(owner: ContactLinkOwner, orm: Any) -> ContactLink:
    return ContactLink(
        id=orm.id,
        public_id=orm.public_id,
        owner=owner,
        owner_id=orm.product_id if owner == ContactLinkOwner.PRODUCT else orm.project_id,
        contact_id=orm.contact_id,
        receives_meeting_notes=orm.receives_meeting_notes,
        created=utc_aware(orm.created),
        creator_id=orm.creator_id,
    )


class SqlAlchemyContactLinkRepository(IContactLinkRepository):
    """Implements IContactLinkRepository."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_links(self, owner: ContactLinkOwner, owner_id: int) -> list[ContactLink]:
        model = _model(owner)
        rows = await self._db.scalars(
            select(model).where(_owner_column(owner) == owner_id).order_by(model.id.asc())
        )
        return [_to_entity(owner, orm) for orm in rows]

    async def get_link(
        self, owner: ContactLinkOwner, owner_id: int, contact_id: int
    ) -> ContactLink | None:
        model = _model(owner)
        orm = await self._db.scalar(
            select(model).where(_owner_column(owner) == owner_id, model.contact_id == contact_id)
        )
        return _to_entity(owner, orm) if orm is not None else None

    async def save(self, link: ContactLink) -> ContactLink:
        model = _model(link.owner)
        if link.id == 0:
            owner_key = "product_id" if link.owner == ContactLinkOwner.PRODUCT else "project_id"
            orm: Any = model(
                **{owner_key: link.owner_id},
                contact_id=link.contact_id,
                receives_meeting_notes=link.receives_meeting_notes,
                created=link.created,
                creator_id=link.creator_id,
            )
            self._db.add(orm)
        else:
            orm = await self._db.get(model, link.id)
            if orm is None:
                raise ValueError(f"{model.__name__} id={link.id} not found for update.")
            orm.receives_meeting_notes = link.receives_meeting_notes
        await self._db.flush()
        return _to_entity(link.owner, orm)

    async def delete(self, link: ContactLink) -> None:
        orm = await self._db.get(_model(link.owner), link.id)
        if orm is not None:
            await self._db.delete(orm)
            await self._db.flush()

    async def get_usage(self, contact_ids: list[int]) -> list[ContactUsageRow]:
        if not contact_ids:
            return []
        ids = set(contact_ids)
        products = await self._db.execute(
            select(
                ProductContactOrmModel.contact_id,
                ProductOrmModel.id,
                ProductOrmModel.product_number,
                ProductContactOrmModel.receives_meeting_notes,
            )
            .join(ProductOrmModel, ProductContactOrmModel.product_id == ProductOrmModel.id)
            .where(ProductContactOrmModel.contact_id.in_(ids), ProductOrmModel.archived.is_(False))
            .order_by(ProductOrmModel.product_number.asc())
        )
        projects = await self._db.execute(
            select(
                ProjectContactOrmModel.contact_id,
                ProjectOrmModel.id,
                ProjectOrmModel.project_number,
                ProjectContactOrmModel.receives_meeting_notes,
            )
            .join(ProjectOrmModel, ProjectContactOrmModel.project_id == ProjectOrmModel.id)
            .where(ProjectContactOrmModel.contact_id.in_(ids), ProjectOrmModel.deleted.is_(False))
            .order_by(ProjectOrmModel.project_number.asc())
        )
        return [
            ContactUsageRow(
                contact_id=contact_id,
                owner=ContactLinkOwner.PRODUCT,
                owner_id=owner_id,
                number=number,
                receives_meeting_notes=receives,
            )
            for contact_id, owner_id, number, receives in products.all()
        ] + [
            ContactUsageRow(
                contact_id=contact_id,
                owner=ContactLinkOwner.PROJECT,
                owner_id=owner_id,
                number=number,
                receives_meeting_notes=receives,
            )
            for contact_id, owner_id, number, receives in projects.all()
        ]
