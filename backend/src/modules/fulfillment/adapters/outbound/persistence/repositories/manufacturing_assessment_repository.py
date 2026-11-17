"""
Concrete SQLAlchemy implementation for the ManufacturingAssessment
aggregate. One row per completed production order, create + read
only, no update/delete (immutable, mirrors OrderItemDelivery).
"""

from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.interfaces import ORMOption

from src.modules.fulfillment.adapters.outbound.persistence.models.manufacturing_assessment_model import (
    ManufacturingAssessmentOrmModel,
)
from src.modules.fulfillment.domain.entities.manufacturing_assessment import ManufacturingAssessment
from src.modules.fulfillment.domain.value_objects.production_status import ComplexityClass
from src.modules.platform.adapters.outbound.persistence.statements import by_id
from src.modules.platform.adapters.outbound.persistence.user_loading import load_user
from src.modules.platform.adapters.outbound.persistence.user_loading import user_orm_to_entity

# ── ORM <-> Entity converters ────────────────────────────────────────


@lru_cache(maxsize=1)
def manufacturing_assessment_load_options() -> tuple[ORMOption, ...]:
    """Everything manufacturing_assessment_orm_to_entity() dereferences. Built
    on first call rather than at import, because constructing a loader option
    configures the mapper registry before every model module is registered."""
    return (load_user(ManufacturingAssessmentOrmModel.operator),)


def manufacturing_assessment_orm_to_entity(
    orm: ManufacturingAssessmentOrmModel,
) -> ManufacturingAssessment:
    return ManufacturingAssessment(
        id=orm.id,
        public_id=orm.public_id,
        production_order_id=orm.production_order_id,
        operator_id=orm.operator_id,
        actual_minutes_per_piece=orm.actual_minutes_per_piece,
        actual_setup_minutes=orm.actual_setup_minutes,
        complexity=ComplexityClass(orm.complexity),
        note=orm.note,
        created=orm.created,
        operator=user_orm_to_entity(orm.operator) if orm.operator else None,
    )


# ══════════════════════════════════════════════════════════════════════
# ManufacturingAssessment repository
# ══════════════════════════════════════════════════════════════════════


class SqlAlchemyManufacturingAssessmentRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_production_order_id(
        self, production_order_id: int
    ) -> ManufacturingAssessment | None:
        orm = await self._db.scalar(
            select(ManufacturingAssessmentOrmModel)
            .where(ManufacturingAssessmentOrmModel.production_order_id == production_order_id)
            .options(*manufacturing_assessment_load_options())
            .limit(1)
        )
        return manufacturing_assessment_orm_to_entity(orm) if orm else None

    async def save(self, assessment: ManufacturingAssessment) -> ManufacturingAssessment:
        orm = ManufacturingAssessmentOrmModel(
            production_order_id=assessment.production_order_id,
            operator_id=assessment.operator_id,
            actual_minutes_per_piece=assessment.actual_minutes_per_piece,
            actual_setup_minutes=assessment.actual_setup_minutes,
            complexity=assessment.complexity.value,
            note=assessment.note,
            created=assessment.created,
        )
        self._db.add(orm)
        await self._db.flush()
        new_id = orm.id
        reloaded = (
            await self._db.scalars(
                by_id(
                    ManufacturingAssessmentOrmModel,
                    new_id,
                    *manufacturing_assessment_load_options(),
                    refresh=True,
                )
            )
        ).one()
        return manufacturing_assessment_orm_to_entity(reloaded)
