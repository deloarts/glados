"""
Concrete implementation of IFabricationMethodRepository, a subclass of the shared
labeled catalogue repository that adds the fabrication method columns, the
lookup of the default for assemblies and the translation of a clash on that
single default into a domain error.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.interfaces import ORMOption

from src.modules.catalogue.adapters.outbound.persistence.mappers.catalogue_mappers import (
    fabrication_method_load_options,
)
from src.modules.catalogue.adapters.outbound.persistence.mappers.catalogue_mappers import (
    fabrication_method_orm_to_entity,
)
from src.modules.catalogue.adapters.outbound.persistence.models.fabrication_method_model import (
    FabricationMethodOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.labeled_catalogue_repository import (
    LabeledCatalogueRepositoryBase,
)
from src.modules.catalogue.domain.entities.fabrication_method import FabricationMethod
from src.modules.catalogue.domain.errors import FabricationMethodAssemblyDefaultConflictError
from src.modules.catalogue.ports.outbound.repositories.fabrication_method_repository import (
    IFabricationMethodRepository,
)


class SqlAlchemyFabricationMethodRepository(
    LabeledCatalogueRepositoryBase[FabricationMethod], IFabricationMethodRepository
):
    """Implements IFabricationMethodRepository."""

    _model = FabricationMethodOrmModel

    def _load_options(self) -> tuple[ORMOption, ...]:
        return fabrication_method_load_options()

    def _orm_to_entity(self, orm: FabricationMethodOrmModel) -> FabricationMethod:
        return fabrication_method_orm_to_entity(orm)

    def _entity_to_dict(self, entity: FabricationMethod) -> dict[str, Any]:
        return {
            "created": entity.created,
            "changed": entity.changed,
            "changes": entity.changes,
            "name": entity.name.as_dict(),
            "label_color": entity.label_color,
            "label_font_color": entity.label_font_color,
            "description": entity.description.as_dict(),
            "creator_id": entity.creator_id,
            "requires_machine": entity.requires_machine,
            "required_external": entity.required_external,
            "default_supplier_id": entity.default_supplier_id,
            "lead_time_days": entity.lead_time_days,
            "wait_after_minutes": entity.wait_after_minutes,
            "default_for_assemblies": entity.default_for_assemblies,
            "archived": entity.archived,
            "sort_order": entity.sort_order,
        }

    async def _flush(self) -> None:
        """Flushes a write, turning a clash on the single default for
        assemblies into a domain error. The use cases clear the previous
        holder first, so only a concurrent write gets here."""
        try:
            await self._db.flush()
        except IntegrityError as exc:
            if "default_for_assemblies" in str(exc.orig).lower():
                raise FabricationMethodAssemblyDefaultConflictError(
                    "Another fabrication method is already the default for assemblies."
                ) from exc
            raise

    async def get_default_for_assemblies(self) -> FabricationMethod | None:
        orm = await self._db.scalar(
            select(FabricationMethodOrmModel)
            .where(FabricationMethodOrmModel.default_for_assemblies.is_(True))
            .options(*fabrication_method_load_options())
            .limit(1)
        )
        return fabrication_method_orm_to_entity(orm) if orm else None
