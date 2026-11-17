"""
Covers (part of) a source item demand directly from stock, no order
involved, through the fulfilment the demand families share
(_demand_family/fulfill_from_stock.py). The open quantity it reports counts
the order lines the demand is allocated on, and the machine schedules are
recomputed once the fulfilment is committed.

This is also the mechanism for "book-keeping only" fulfillment: a lot
whose step 1 was already in progress/done before its source material was
ever assigned can have that already-used material declared fulfilled from
stock here, which counts as "arrived" for the raw-material gating
mechanism (see _raw_material_coverage.py) without needing a real order.
"""

from src.modules.fulfillment.application.dto.source_item_allocation_dto import (
    FulfillSourceItemDemandFromStockCommand,
)
from src.modules.fulfillment.application.dto.source_item_allocation_dto import (
    FulfillSourceItemDemandFromStockResult,
)
from src.modules.fulfillment.application.services.allocation_lookup import (
    order_items_for_allocations,
)
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.use_cases._demand_family.fulfill_from_stock import (
    FulfillFromStock,
)
from src.modules.fulfillment.application.use_cases.production_schedule.recompute_machine_schedule import (
    RecomputeMachineSchedule,
)
from src.modules.fulfillment.application.use_cases.source_item_demand._spec import SPEC
from src.modules.fulfillment.domain.entities.source_item_allocation import (
    SourceItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.source_item_demand_item import SourceItemDemandItem
from src.modules.fulfillment.domain.services.source_item_allocation_service import (
    SourceItemAllocationQuantityService,
)
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemAllocationSource,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemDemandRepository,
)
from src.modules.platform.application.services.schedule_recompute_port import (
    recompute_schedule_after_commit,
)
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class FulfillSourceItemDemandFromStock(
    FulfillFromStock[
        SourceItemDemandItem,
        SourceItemDemandAllocation,
        FulfillSourceItemDemandFromStockCommand,
        FulfillSourceItemDemandFromStockResult,
    ]
):
    _spec = SPEC
    _result = FulfillSourceItemDemandFromStockResult

    def __init__(
        self,
        demand_repo: ISourceItemDemandRepository,
        allocation_repo: ISourceItemAllocationRepository,
        order_item_repo: IOrderItemRepository,
        recompute_schedule: RecomputeMachineSchedule | None = None,
        *,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
    ) -> None:
        super().__init__(demand_repo, allocation_repo, uow=uow, reconciler=reconciler)
        self._order_items = order_item_repo
        self._recompute = recompute_schedule

    def _stock_allocation(self, demand_id: int, quantity: float) -> SourceItemDemandAllocation:
        return SourceItemDemandAllocation(
            demand_item_id=demand_id,
            order_item_id=None,
            quantity=quantity,
            source=SourceItemAllocationSource.STOCK,
        )

    async def _unallocated(
        self, demand: SourceItemDemandItem, allocations: list[SourceItemDemandAllocation]
    ) -> float:
        order_items_by_id = await order_items_for_allocations(allocations, self._order_items)
        # The unallocated quantity reads no delivery, so no fill is needed.
        return SourceItemAllocationQuantityService.compute_summary(
            demand, allocations, order_items_by_id, {}
        ).unallocated

    async def _after_commit(self, demand: SourceItemDemandItem) -> None:
        await recompute_schedule_after_commit(
            self._recompute,
            after=(
                f"fulfilling source item demand "
                f"#{demand.id} from stock; the fulfillment itself is committed."
            ),
        )

    def _log_fulfilled(
        self,
        cmd: FulfillSourceItemDemandFromStockCommand,
        demand: SourceItemDemandItem,
        total_from_stock: float,
    ) -> None:
        log.info("Fulfilled %.3f of source item demand #%s from stock.", cmd.quantity, demand.id)
