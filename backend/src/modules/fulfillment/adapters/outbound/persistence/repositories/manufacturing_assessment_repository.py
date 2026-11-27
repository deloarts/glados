"""
Concrete SQLAlchemy implementation for the ManufacturingAssessment
aggregate. An order has at most one active row; a later assessment after a
reversed completion marks the earlier one superseded instead of changing or
deleting it, so the rows themselves are never edited otherwise.
"""

from datetime import datetime
from functools import lru_cache

from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.interfaces import ORMOption

from src.modules.fulfillment.adapters.outbound.persistence.models.manufacturing_assessment_model import (
    ManufacturingAssessmentOrmModel,
)
from src.modules.fulfillment.domain.entities.manufacturing_assessment import ManufacturingAssessment
from src.modules.fulfillment.domain.errors import ManufacturingAssessmentAlreadyExistsError
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
        superseded_at=orm.superseded_at,
        operator=user_orm_to_entity(orm.operator) if orm.operator else None,
    )


def _is_active_assessment_clash(exc: IntegrityError) -> bool:
    """Whether the error is the one-active-assessment index: Postgres names
    the index, SQLite the column."""
    message = str(exc.orig).lower()
    return (
        "ix_manufacturing_assessment_table_production_order_id" in message
        or "unique constraint failed: manufacturing_assessment_table.production_order_id" in message
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
            .where(
                ManufacturingAssessmentOrmModel.production_order_id == production_order_id,
                ManufacturingAssessmentOrmModel.superseded_at.is_(None),
            )
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
            superseded_at=assessment.superseded_at,
        )
        self._db.add(orm)
        try:
            await self._db.flush()
        except IntegrityError as exc:
            # The partial unique index clashes when a concurrent record of
            # the same order won the race after the caller checked.
            if _is_active_assessment_clash(exc):
                raise ManufacturingAssessmentAlreadyExistsError(
                    f"Production order #{assessment.production_order_id} already has a "
                    "manufacturing assessment."
                ) from exc
            raise
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

    async def mark_superseded(self, assessment_id: int, superseded_at: datetime) -> None:
        # Flushed at once, so the new row the caller adds next does not meet
        # this one in the partial unique index.
        await self._db.execute(
            update(ManufacturingAssessmentOrmModel)
            .where(
                ManufacturingAssessmentOrmModel.id == assessment_id,
                ManufacturingAssessmentOrmModel.superseded_at.is_(None),
            )
            .values(superseded_at=superseded_at)
        )
