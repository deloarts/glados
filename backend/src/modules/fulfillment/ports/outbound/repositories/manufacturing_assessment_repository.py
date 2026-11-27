"""
Repository interface for the ManufacturingAssessment aggregate.
Kept separate from IProductionOrderRepository (unlike
ProductionOrderCompletion), an assessment is a one-off, post-hoc capture
rather than an owned child fetched alongside every order read.
"""

from datetime import datetime
from typing import Protocol
from typing import runtime_checkable

from src.modules.fulfillment.domain.entities.manufacturing_assessment import ManufacturingAssessment


@runtime_checkable
class IManufacturingAssessmentRepository(Protocol):
    async def get_by_production_order_id(
        self, production_order_id: int
    ) -> ManufacturingAssessment | None:
        """The order's active assessment; a superseded one is never returned."""
        ...

    async def save(self, assessment: ManufacturingAssessment) -> ManufacturingAssessment:
        """Records a new assessment. Raises
        ManufacturingAssessmentAlreadyExistsError when the order already has
        an active one, which a concurrent record can still hit after the
        caller checked."""
        ...

    async def mark_superseded(self, assessment_id: int, superseded_at: datetime) -> None:
        """Marks an active assessment as replaced, so the order's next one
        can be recorded; the row stays as history."""
        ...
