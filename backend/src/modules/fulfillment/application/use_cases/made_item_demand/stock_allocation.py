"""
Sets and removes the stock allocation of a made item demand by hand,
through the writers the demand families share
(_demand_family/allocation_writers.py). Lot allocations follow their lot
instead: CreateLot writes them when it links demands, and the lot's cancel
and short-close disposition move or remove them.
"""

from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemAllocationSource
from src.modules.fulfillment.application.dto.made_item_allocation_dto import (
    MadeItemAllocationResult,
)
from src.modules.fulfillment.application.mappers.made_item_allocation_mapper import (
    MadeItemAllocationMapper,
)
from src.modules.fulfillment.application.use_cases._demand_family import (
    allocation_writers as shared,
)
from src.modules.fulfillment.application.use_cases.made_item_demand._spec import SPEC
from src.modules.fulfillment.domain.entities.made_item_allocation import MadeItemDemandAllocation
from src.modules.fulfillment.domain.entities.made_item_demand_item import MadeItemDemandItem


class UpdateStockAllocation(
    shared.UpdateStockAllocation[
        MadeItemDemandItem, MadeItemDemandAllocation, MadeItemAllocationResult
    ]
):
    """Manually overrides the stock allocation quantity of a demand."""

    _spec = SPEC

    def _result(self, allocation: MadeItemDemandAllocation) -> MadeItemAllocationResult:
        return MadeItemAllocationMapper.to_result(allocation)

    def _stock_allocation(self, demand_id: int, quantity: float) -> MadeItemDemandAllocation:
        return MadeItemDemandAllocation(
            demand_item_id=demand_id,
            lot_id=None,
            quantity=quantity,
            source=MadeItemAllocationSource.STOCK,
        )


class DeleteStockAllocation(
    shared.DeleteStockAllocation[MadeItemDemandItem, MadeItemDemandAllocation]
):
    """Removes the stock allocation row of a demand."""

    _spec = SPEC
