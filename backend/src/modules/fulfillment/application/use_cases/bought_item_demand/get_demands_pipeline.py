"""
Procurement pipeline view: one row per demand item that is either
still in flight (open/allocated/ordered) or reached a terminal status
(fulfilled/canceled) recently. N+1-free: batch-fetches allocations and the
order items they reference, then computes each row's quantity summary from
the pre-fetched lists via AllocationQuantityService (shared with the rest
of the allocation/demand summary code paths).
"""

from collections.abc import Mapping
from collections.abc import Sequence
from datetime import date

from src.modules.fulfillment.application.dto.bought_item_demand_dto import PipelineResult
from src.modules.fulfillment.application.dto.bought_item_demand_dto import PipelineRowResult
from src.modules.fulfillment.application.services.allocation_fill import line_fill
from src.modules.fulfillment.application.services.allocation_lookup import (
    order_items_for_allocation_batch,
)
from src.modules.fulfillment.application.services.allocation_lookup import orders_for_order_items
from src.modules.fulfillment.domain.entities.bought_item_allocation import (
    BoughtItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.bought_item_demand_item import BoughtItemDemandItem
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.services.allocation_service import AllocationQuantityService
from src.modules.fulfillment.domain.services.lifecycle.demand import FillEntry
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemDemandItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import IOrderRepository


class GetDemandsPipeline:
    def __init__(
        self,
        demand_repo: IBoughtItemDemandItemRepository,
        allocation_repo: IBoughtItemAllocationRepository,
        order_item_repo: IOrderItemRepository,
        order_repo: IOrderRepository,
    ) -> None:
        self._demands = demand_repo
        self._allocations = allocation_repo
        self._order_items = order_item_repo
        self._orders = order_repo

    async def execute(self, terminal_since: date) -> PipelineResult:
        demands = await self._demands.get_pipeline(terminal_since)
        if not demands:
            return PipelineResult(items=[])

        demand_ids = [d.id for d in demands]
        all_allocations = await self._allocations.get_by_demand_item_ids(demand_ids)

        allocations_by_demand: dict[int, list[BoughtItemDemandAllocation]] = {
            d.id: [] for d in demands
        }
        for alloc in all_allocations:
            allocations_by_demand.setdefault(alloc.demand_item_id, []).append(alloc)

        order_items_by_id = await order_items_for_allocation_batch(
            all_allocations, self._order_items
        )

        orders_by_id = await orders_for_order_items(order_items_by_id.values(), self._orders)
        fill = await line_fill(order_items_by_id, bought=self._allocations)

        rows = [
            self._build_row(
                demand,
                allocations_by_demand.get(demand.id, []),
                order_items_by_id,
                orders_by_id,
                fill,
            )
            for demand in demands
        ]
        return PipelineResult(items=rows)

    def _build_row(
        self,
        demand: BoughtItemDemandItem,
        allocations: list[BoughtItemDemandAllocation],
        order_items_by_id: dict[int, OrderItem],
        orders_by_id: dict[int, Order],
        fill: Mapping[int, Sequence[FillEntry]],
    ) -> PipelineRowResult:
        demand_order_items_by_id = {
            oi.id: oi
            for a in allocations
            if a.order_item_id is not None and (oi := order_items_by_id.get(a.order_item_id))
        }
        summary = AllocationQuantityService.compute_summary(
            demand, allocations, demand_order_items_by_id, fill
        )

        supplier_names = sorted(
            {oi.supplier_name for oi in demand_order_items_by_id.values() if oi.supplier_name}
        )
        expected_delivery_dates = sorted(
            {
                oi.expected_delivery_date
                for oi in demand_order_items_by_id.values()
                if oi.expected_delivery_date is not None
            }
        )
        order_numbers = sorted(
            {orders_by_id[oid].order_number for oid in summary.order_ids if oid in orders_by_id}
        )

        return PipelineRowResult(
            demand_item_id=demand.id,
            status=demand.status,
            high_priority=demand.high_priority,
            item_id=demand.item_id,
            item_order_code_1=demand.item_order_code_1,
            item_article_name=demand.item_article_name,
            project_id=demand.project_id,
            project_number=demand.project_number,
            unit=demand.unit,
            total=summary.total,
            allocated=summary.allocated,
            ordered=summary.ordered,
            delivered=summary.delivered,
            fulfilled_from_stock=summary.fulfilled_from_stock,
            remaining=summary.remaining,
            is_fully_allocated=summary.is_fully_allocated,
            is_fully_delivered=summary.is_fully_delivered,
            supplier_names=supplier_names,
            order_numbers=order_numbers,
            expected_delivery_dates=expected_delivery_dates,
        )
