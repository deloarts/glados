"""
Covers (part of) a made item demand directly from stock instead of via a
lot, through the fulfilment the demand families share
(_demand_family/fulfill_from_stock.py). The lifecycle reconciler counts the
pieces the demand's lots have completed too, so a demand covered partly by a
lot and partly from stock reaches FULFILLED.
"""

from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemAllocationSource
from src.modules.fulfillment.application.dto.made_item_allocation_dto import (
    FulfillMadeItemFromStockCommand,
)
from src.modules.fulfillment.application.dto.made_item_allocation_dto import (
    FulfillMadeItemFromStockResult,
)
from src.modules.fulfillment.application.use_cases._demand_family.fulfill_from_stock import (
    FulfillFromStock,
)
from src.modules.fulfillment.application.use_cases.made_item_demand._spec import SPEC
from src.modules.fulfillment.domain.entities.made_item_allocation import MadeItemDemandAllocation
from src.modules.fulfillment.domain.entities.made_item_demand_item import MadeItemDemandItem
from src.modules.fulfillment.domain.services.made_item_allocation_service import (
    MadeItemAllocationQuantityService,
)


class FulfillDemandFromStock(
    FulfillFromStock[
        MadeItemDemandItem,
        MadeItemDemandAllocation,
        FulfillMadeItemFromStockCommand,
        FulfillMadeItemFromStockResult,
    ]
):
    _spec = SPEC
    _result = FulfillMadeItemFromStockResult

    def _stock_allocation(self, demand_id: int, quantity: float) -> MadeItemDemandAllocation:
        return MadeItemDemandAllocation(
            demand_item_id=demand_id,
            lot_id=None,
            quantity=quantity,
            source=MadeItemAllocationSource.STOCK,
        )

    async def _unallocated(
        self, demand: MadeItemDemandItem, allocations: list[MadeItemDemandAllocation]
    ) -> float:
        # The unallocated quantity reads no delivery, so no fill is needed.
        return MadeItemAllocationQuantityService.compute_summary(
            demand, allocations, fill={}
        ).unallocated
