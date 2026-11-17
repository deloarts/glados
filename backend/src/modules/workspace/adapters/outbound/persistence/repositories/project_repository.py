"""
Concrete implementation of IProjectRepository using SQLAlchemy + Postgres.
All ORM ↔ entity mapping is private to this module.
"""

from functools import lru_cache
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
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
from src.modules.platform.adapters.outbound.persistence.mapping_common import changed_by_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import soft_delete_kwargs
from src.modules.platform.adapters.outbound.persistence.statements import by_id
from src.modules.platform.adapters.outbound.persistence.statements import fetch_page
from src.modules.platform.adapters.outbound.persistence.statements import order_term
from src.modules.platform.adapters.outbound.persistence.tenant_zone import date_filter_zone
from src.modules.platform.adapters.outbound.persistence.user_loading import load_user
from src.modules.platform.adapters.outbound.persistence.user_loading import user_orm_to_entity
from src.modules.workspace.adapters.outbound.persistence.models.product_model import ProductOrmModel
from src.modules.workspace.adapters.outbound.persistence.models.project_model import ProjectOrmModel
from src.modules.workspace.adapters.outbound.persistence.repositories.product_repository import (
    product_orm_to_entity,
)
from src.modules.workspace.domain.entities.project import Project
from src.modules.workspace.domain.value_objects.project_status import ProjectStatus
from src.modules.workspace.ports.outbound.repositories.project_repository import IProjectRepository
from src.modules.workspace.ports.outbound.workspace_queries import ProjectFilterDto

# ── Mapping helpers ───────────────────────────────────────────────────


@lru_cache(maxsize=1)
def project_load_options() -> tuple[ORMOption, ...]:
    """Everything _orm_to_entity() dereferences, including the nested
    customer and product mappers. Built on first call rather than at import,
    because constructing a loader option configures the mapper registry before
    every model module is registered."""
    return (
        load_user(ProjectOrmModel.customer, CustomerOrmModel.creator),
        load_user(ProjectOrmModel.product, ProductOrmModel.customer, CustomerOrmModel.creator),
        load_user(ProjectOrmModel.product, ProductOrmModel.creator),
        load_user(ProjectOrmModel.creator),
        load_user(ProjectOrmModel.changed_by),
    )


def _orm_to_entity(orm: ProjectOrmModel) -> Project:
    return Project(
        id=orm.id,
        public_id=orm.public_id,
        project_number=orm.project_number,
        customer_id=orm.customer_id,
        customer=customer_orm_to_entity(orm.customer) if orm.customer else None,
        product_id=orm.product_id,
        product=product_orm_to_entity(orm.product) if orm.product else None,
        description=orm.description,
        status=ProjectStatus(orm.status),
        designated_user_id=orm.designated_user_id,
        created=orm.created,
        creator_id=orm.creator_id or 0,
        creator=user_orm_to_entity(orm.creator) if orm.creator else None,
        **changed_by_kwargs(orm.changed_by_id, orm.changed_by),
        production_time_budget=orm.production_time_budget,
        required_delivery_date_made=orm.required_delivery_date_made,
        required_delivery_date_bought=orm.required_delivery_date_bought,
        edit_version=orm.edit_version,
        **soft_delete_kwargs(orm.changed, orm.changes, orm.deleted),
    )


def _entity_to_dict(project: Project) -> dict[str, Any]:
    return {
        "project_number": project.project_number,
        "customer_id": project.customer_id,
        "product_id": project.product_id,
        "description": project.description,
        "status": project.status.value,
        "designated_user_id": project.designated_user_id,
        "created": project.created,
        "creator_id": project.creator_id or None,
        "production_time_budget": project.production_time_budget,
        "required_delivery_date_made": project.required_delivery_date_made,
        "required_delivery_date_bought": project.required_delivery_date_bought,
        "edit_version": project.edit_version,
        **soft_delete_kwargs(project.changed, project.changes, project.deleted),
    }


# ── Repository ────────────────────────────────────────────────────────


class SqlAlchemyProjectRepository(IProjectRepository):
    """Implements IProjectRepository."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Queries ───────────────────────────────────────────────────────

    async def get_by_id(self, id: int) -> Project | None:
        orm = await self._db.scalar(
            select(ProjectOrmModel)
            .where(ProjectOrmModel.id == id, ProjectOrmModel.deleted.is_(False))
            .options(*project_load_options())
            .limit(1)
        )
        return _orm_to_entity(orm) if orm else None

    async def lock_for_update(self, id: int) -> None:
        (
            await self._db.scalars(
                select(ProjectOrmModel.id)
                .where(ProjectOrmModel.id == id)
                .with_for_update(key_share=True)
            )
        ).all()

    async def lock_for_share(self, ids: list[int]) -> None:
        if not ids:
            return
        (
            await self._db.scalars(
                select(ProjectOrmModel.id)
                .where(ProjectOrmModel.id.in_(sorted(set(ids))))
                .order_by(ProjectOrmModel.id)
                .with_for_update(read=True)
            )
        ).all()

    async def get_by_project_number(self, project_number: str) -> Project | None:
        """Filters soft-deleted rows, matching get_by_id/get_multi. Safe
        because `project_number`'s uniqueness is enforced by a partial
        index (`uq_project_project_number_active`, WHERE deleted IS false),
        so a soft-deleted row no longer reserves its number and the
        uniqueness pre-check this backs must not see one."""
        orm = await self._db.scalar(
            select(ProjectOrmModel)
            .where(
                ProjectOrmModel.project_number == project_number,
                ProjectOrmModel.deleted.is_(False),
            )
            .options(*project_load_options())
            .limit(1)
        )
        return _orm_to_entity(orm) if orm else None

    async def get_by_product_id(self, product_id: int) -> list[Project]:
        rows = (
            await self._db.scalars(
                select(ProjectOrmModel)
                .where(ProjectOrmModel.product_id == product_id, ProjectOrmModel.deleted.is_(False))
                .options(*project_load_options())
            )
        ).all()
        return [_orm_to_entity(r) for r in rows]

    async def get_by_designated_user_id(self, user_id: int) -> list[Project]:
        rows = (
            await self._db.scalars(
                select(ProjectOrmModel)
                .where(
                    ProjectOrmModel.designated_user_id == user_id,
                    ProjectOrmModel.deleted.is_(False),
                )
                .options(*project_load_options())
            )
        ).all()
        return [_orm_to_entity(r) for r in rows]

    async def get_multi(self, filters: ProjectFilterDto) -> tuple[int, list[Project]]:
        zone = await date_filter_zone(self._db, filters.created_from, filters.created_to)
        q = select(ProjectOrmModel).where(ProjectOrmModel.deleted.is_(False))

        if filters.id is not None:
            q = q.where(ProjectOrmModel.id == filters.id)
        if filters.ids:
            q = q.where(ProjectOrmModel.id.in_(filters.ids))
        if filters.status is not None:
            q = q.where(ProjectOrmModel.status == filters.status)
        if filters.designated_user_id is not None:
            q = q.where(ProjectOrmModel.designated_user_id == filters.designated_user_id)
        if filters.product_id is not None:
            q = q.where(ProjectOrmModel.product_id == filters.product_id)
        if filters.project_number:
            q = q.where(contains_ci(ProjectOrmModel.project_number, filters.project_number))
        if filters.customer_id is not None:
            q = q.where(ProjectOrmModel.customer_id == filters.customer_id)
        if filters.description:
            q = q.where(contains_ci(ProjectOrmModel.description, filters.description))
        if filters.creator_id is not None:
            q = q.where(ProjectOrmModel.creator_id == filters.creator_id)
        if filters.changed_by_id is not None:
            q = q.where(ProjectOrmModel.changed_by_id == filters.changed_by_id)
        if filters.created_from:
            q = q.where(ProjectOrmModel.created >= day_start_utc(filters.created_from, zone))
        if filters.created_to:
            q = q.where(ProjectOrmModel.created < day_after_utc(filters.created_to, zone))
        if filters.required_delivery_date_made_from:
            q = q.where(
                ProjectOrmModel.required_delivery_date_made
                >= filters.required_delivery_date_made_from
            )
        if filters.required_delivery_date_made_to:
            q = q.where(
                ProjectOrmModel.required_delivery_date_made
                <= filters.required_delivery_date_made_to
            )
        if filters.required_delivery_date_bought_from:
            q = q.where(
                ProjectOrmModel.required_delivery_date_bought
                >= filters.required_delivery_date_bought_from
            )
        if filters.required_delivery_date_bought_to:
            q = q.where(
                ProjectOrmModel.required_delivery_date_bought
                <= filters.required_delivery_date_bought_to
            )
        if filters.search:
            term = filters.search
            q = q.where(
                (contains_ci(ProjectOrmModel.project_number, term))
                | (contains_ci(ProjectOrmModel.description, term))
            )

        _sort_column_map = {
            "id": ProjectOrmModel.id,
            "project_number": ProjectOrmModel.project_number,
            "created": ProjectOrmModel.created,
        }
        sort_col = _sort_column_map.get(
            filters.order_by or "project_number", ProjectOrmModel.project_number
        )
        total, rows = await fetch_page(
            self._db,
            q,
            filters.skip,
            filters.limit,
            order_term(sort_col, filters.order_dir, default="desc"),
            options=project_load_options(),
        )
        return total, [_orm_to_entity(r) for r in rows]

    # ── Mutations ─────────────────────────────────────────────────────

    async def save(self, project: Project) -> Project:
        """Inserts (id 0) or updates the project. Flushes without committing;
        the caller's unit of work commits."""
        if project.id == 0:
            orm = ProjectOrmModel(**_entity_to_dict(project))
            self._db.add(orm)
            await self._db.flush()
            return _orm_to_entity(await self._reload(orm.id))
        existing = await self._db.get(ProjectOrmModel, project.id)
        if not existing:
            raise ValueError(f"ProjectOrmModel id={project.id} not found for update.")
        orm = existing
        for key, value in _entity_to_dict(project).items():
            setattr(orm, key, value)
        await self._db.flush()
        return _orm_to_entity(await self._reload(project.id))

    async def _reload(self, id: int) -> ProjectOrmModel:
        return (
            await self._db.scalars(
                by_id(ProjectOrmModel, id, *project_load_options(), refresh=True)
            )
        ).one()

    async def delete(self, project: Project) -> None:
        """Hard delete. Marking the project deleted through save() is the usual way."""
        orm = await self._db.get(ProjectOrmModel, project.id)
        if orm:
            await self._db.delete(orm)
            await self._db.flush()
