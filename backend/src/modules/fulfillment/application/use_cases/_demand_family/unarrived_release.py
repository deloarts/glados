"""
Releases what a bought or source item demand holds on order lines beyond the
pieces that already reached it, for a demand marked fulfilled by hand. Such a
demand waits for nothing more, so an allocation that kept its full quantity
would hold the line's capacity for pieces nobody needs and block the line
from being shrunk or allocated to another demand.

The pieces that reached the demand on a line are its share of the line's
accepted pieces in the fill order (lifecycle/demand.py). Cutting the
allocation down to that share leaves every other demand on the line with
exactly the pieces it had: a demand whose allocation is not fully covered
has taken every arrived piece left after the demands ahead of it, so the
demands behind it had none. An allocation of which nothing arrived is
deleted, and a stock allocation, which names no line, stays.

The caller locks the lines it got from `line_ids` together with the demand
before it calls `release`, and touches and runs its lifecycle reconciler.
"""

from dataclasses import replace
from typing import Generic

from src.modules.fulfillment.application.services.allocation_fill import LineFillRepos
from src.modules.fulfillment.application.services.allocation_fill import line_fill
from src.modules.fulfillment.application.use_cases._demand_family.allocation_writers import L
from src.modules.fulfillment.application.use_cases._demand_family.allocation_writers import (
    OrderLineAllocationRepo,
)
from src.modules.fulfillment.domain.services.lifecycle.demand import pieces_ahead
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemRepository,
)
from src.modules.platform.domain.services.quantities import is_zero_quantity
from src.modules.platform.domain.services.quantities import quantity_gt


class UnarrivedLineRelease(Generic[L]):
    """The release for one family, whose allocations `allocations` holds."""

    def __init__(
        self,
        allocations: OrderLineAllocationRepo[L],
        fill: LineFillRepos,
        order_items: IOrderItemRepository,
    ) -> None:
        self._allocations = allocations
        self._fill = fill
        self._order_items = order_items

    async def _on_lines(self, demand_id: int) -> list[L]:
        return [
            allocation
            for allocation in await self._allocations.get_by_demand_item_id(demand_id)
            if allocation.order_item_id is not None
        ]

    async def line_ids(self, demand_id: int) -> set[int]:
        """The order lines the demand holds allocations on."""
        return {
            allocation.order_item_id
            for allocation in await self._on_lines(demand_id)
            if allocation.order_item_id is not None
        }

    async def release(self, rank: int, demand_id: int) -> float:
        """Cuts each of the demand's line allocations down to the pieces that
        reached it and returns the quantity released. `rank` is the family's
        place in the fill of a line."""
        held = await self._on_lines(demand_id)
        fills = await line_fill(
            [a.order_item_id for a in held if a.order_item_id is not None],
            bought=self._fill.bought,
            source=self._fill.source,
        )
        released = 0.0
        for allocation in held:
            assert allocation.order_item_id is not None
            line = await self._order_items.get_by_id(allocation.order_item_id)
            arrived = (
                0.0
                if line is None or line.status == OrderItemStatus.CANCELED
                else line.quantity_delivered
            )
            ahead = pieces_ahead(fills.get(allocation.order_item_id, []), rank, demand_id)
            reached = min(max(arrived - ahead, 0.0), allocation.quantity)
            if not quantity_gt(allocation.quantity, reached):
                continue
            released += allocation.quantity - reached
            if is_zero_quantity(reached):
                await self._allocations.delete(allocation)
            else:
                await self._allocations.save(replace(allocation, quantity=reached))
        return released
