"""
Repository interface for the ManufacturingAssessment aggregate.
Kept separate from IProductionOrderRepository (unlike
ProductionOrderCompletion), an assessment is a one-off, post-hoc capture
rather than an owned child fetched alongside every order read.
"""

from typing import Protocol
from typing import runtime_checkable

from src.modules.fulfillment.domain.entities.manufacturing_assessment import ManufacturingAssessment


@runtime_checkable
class IManufacturingAssessmentRepository(Protocol):
    async def get_by_production_order_id(
        self, production_order_id: int
    ) -> ManufacturingAssessment | None: ...
    async def save(self, assessment: ManufacturingAssessment) -> ManufacturingAssessment: ...
