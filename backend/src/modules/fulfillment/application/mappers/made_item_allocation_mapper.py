"""Converts a MadeItemDemandAllocation domain entity to its result DTO."""

from src.modules.fulfillment.application.dto.made_item_allocation_dto import (
    MadeItemAllocationResult,
)
from src.modules.fulfillment.domain.entities.made_item_allocation import MadeItemDemandAllocation


class MadeItemAllocationMapper:
    @staticmethod
    def to_result(allocation: MadeItemDemandAllocation) -> MadeItemAllocationResult:
        return MadeItemAllocationResult(
            demand_item_id=allocation.demand_item_id,
            lot_id=allocation.lot_id,
            source=allocation.source,
            quantity=allocation.quantity,
        )
