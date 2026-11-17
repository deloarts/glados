"""
Covers (part of) a bought item demand directly from stock instead of via an
order, through the fulfilment the demand families share
(_demand_family/fulfill_from_stock.py). The open quantity it reports counts
the order lines the demand is allocated on.
"""

from src.modules.catalogue.domain.value_objects.bought_item_status import AllocationSource
from src.modules.fulfillment.application.dto.allocation_dto import FulfillFromStockCommand
from src.modules.fulfillment.application.dto.allocation_dto import FulfillFromStockResult
from src.modules.fulfillment.application.services.allocation_lookup import (
    order_items_for_allocations,
)
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.use_cases._demand_family.fulfill_from_stock import (
    FulfillFromStock,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand._demand_spec import SPEC
from src.modules.fulfillment.domain.entities.bought_item_allocation import (
    BoughtItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.bought_item_demand_item import BoughtItemDemandItem
from src.modules.fulfillment.domain.services.allocation_service import AllocationQuantityService
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemDemandItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class FulfillDemandFromStock(
    FulfillFromStock[
        BoughtItemDemandItem,
        BoughtItemDemandAllocation,
        FulfillFromStockCommand,
        FulfillFromStockResult,
    ]
):
    _spec = SPEC
    _result = FulfillFromStockResult

    def __init__(
        self,
        demand_repo: IBoughtItemDemandItemRepository,
        allocation_repo: IBoughtItemAllocationRepository,
        order_item_repo: IOrderItemRepository,
        *,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
    ) -> None:
        super().__init__(demand_repo, allocation_repo, uow=uow, reconciler=reconciler)
        self._order_items = order_item_repo

    def _stock_allocation(self, demand_id: int, quantity: float) -> BoughtItemDemandAllocation:
        return BoughtItemDemandAllocation(
            demand_item_id=demand_id,
            order_item_id=None,
            quantity=quantity,
            source=AllocationSource.STOCK,
        )

    async def _unallocated(
        self, demand: BoughtItemDemandItem, allocations: list[BoughtItemDemandAllocation]
    ) -> float:
        order_items_by_id = await order_items_for_allocations(allocations, self._order_items)
        # The unallocated quantity reads no delivery, so no fill is needed.
        return AllocationQuantityService.compute_summary(
            demand, allocations, order_items_by_id, {}
        ).unallocated
