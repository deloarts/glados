"""Helpers the order use cases share."""

from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Iterable
from datetime import datetime

from src.modules.fulfillment.application.services.lifecycle_loader import AggregateIds
from src.modules.fulfillment.domain.entities.bought_item_allocation import (
    BoughtItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.source_item_allocation import (
    SourceItemDemandAllocation,
)
from src.modules.fulfillment.domain.errors import OrderItemNotFoundError
from src.modules.fulfillment.domain.errors import OrderNotFoundError
from src.modules.fulfillment.domain.services.lifecycle.demand import fit_in_fill_order
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import IOrderRepository
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemAllocationRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.edit_version import bump_edit_version
from src.modules.platform.domain.services.quantities import is_zero_quantity
from src.modules.platform.domain.services.quantities import quantity_eq
from src.shared_kernel.domain.services.changelog_service import append_changelog


def lots_of_made_lines(lines: Iterable[OrderItem]) -> AggregateIds:
    """The lots that the MADE lines among `lines` supply. A use case that
    writes the position or the lot of such a line locks these together with
    the line, because the one lock order puts a lot before its orders and
    lines."""
    lot_ids = {
        line.lot_id
        for line in lines
        if line.line_type == OrderLineType.MADE and line.lot_id is not None
    }
    return AggregateIds.of({LifecycleAggregate.LOTS: lot_ids})


async def read_order_line(
    orders: IOrderRepository, order_items: IOrderItemRepository, order_id: int, order_item_id: int
) -> tuple[Order, OrderItem]:
    """The order and one of its lines. Raises the not-found error of the
    order, or of the line when it is missing or belongs to another order. A
    use case reads both once to know what to lock and again under the
    locks."""
    order = found_or_raise(
        await orders.get_by_id(order_id), OrderNotFoundError, f"Order #{order_id} not found."
    )
    item = await order_items.get_by_id(order_item_id)
    if not item or item.order_id != order_id:
        raise OrderItemNotFoundError(f"Order item #{order_item_id} not found in order #{order_id}.")
    return order, item


async def release_line_allocations(
    line: OrderItem,
    bought_allocations: IBoughtItemAllocationRepository,
    source_allocations: ISourceItemAllocationRepository | None,
) -> tuple[set[int], set[int]]:
    """Deletes every allocation of both families on the line, whatever the
    demand's status, and returns the ids of the bought and the source
    demands that lost one, for the caller to touch with its reconciler."""
    bought_ids: set[int] = set()
    for allocation in await bought_allocations.get_by_order_item_id(line.id):
        bought_ids.add(allocation.demand_item_id)
        await bought_allocations.delete(allocation)
    source_ids: set[int] = set()
    if source_allocations is not None:
        for source_allocation in await source_allocations.get_by_order_item_id(line.id):
            source_ids.add(source_allocation.demand_item_id)
            await source_allocations.delete(source_allocation)
    return bought_ids, source_ids


async def fit_line_allocations(
    line: OrderItem,
    limit: float,
    *,
    bought_allocations: IBoughtItemAllocationRepository,
    source_allocations: ISourceItemAllocationRepository | None,
) -> tuple[set[int], set[int]]:
    """Fits the allocations of both families on the line into `limit` when
    they exceed it, cutting from the end of the line's fill order, the bought
    demands before the source demands and each family by demand id
    (lifecycle/demand.py fit_in_fill_order), so no demand loses pieces that
    already reached it; an allocation that comes out as nothing is deleted.
    Returns the ids of the bought and the source demands allocated to the
    line, for the caller to touch with its reconciler: a deleted allocation
    no longer leads from the line to its demand."""
    bought = sorted(
        await bought_allocations.get_by_order_item_id(line.id), key=lambda a: a.demand_item_id
    )
    source = (
        sorted(
            await source_allocations.get_by_order_item_id(line.id),
            key=lambda a: a.demand_item_id,
        )
        if source_allocations is not None
        else []
    )
    scaled = fit_in_fill_order(
        [*(a.quantity for a in bought), *(a.quantity for a in source)], limit
    )
    await _resize(bought, scaled[: len(bought)], bought_allocations.save, bought_allocations.delete)
    if source_allocations is not None:
        await _resize(
            source, scaled[len(bought) :], source_allocations.save, source_allocations.delete
        )
    return {a.demand_item_id for a in bought}, {a.demand_item_id for a in source}


async def close_line_short(
    line: OrderItem,
    actor: User,
    now: datetime,
    *,
    cause: str | None = None,
    order_items: IOrderItemRepository,
    bought_allocations: IBoughtItemAllocationRepository,
    source_allocations: ISourceItemAllocationRepository | None,
) -> tuple[set[int], set[int]]:
    """Closes the line short: its quantity becomes the pieces delivered or
    lost on it, the close and the quantity before it are recorded, and the
    allocations of both families on it are fitted into
    the pieces it delivered (fit_line_allocations), since lost pieces never
    arrived and the demands' rest opens again. Saves the line with a
    changelog note that ends with `cause` when given. Returns the ids of the
    bought and the source demands allocated to the line, for the caller to
    touch with its reconciler."""
    old_quantity = line.quantity
    new_quantity = line.quantity_settled
    touched = await fit_line_allocations(
        line,
        line.quantity_delivered,
        bought_allocations=bought_allocations,
        source_allocations=source_allocations,
    )
    line.quantity = new_quantity
    bump_edit_version(line)
    line.closed_short_at = now
    line.closed_short_from = old_quantity
    line.changed = now
    note = f"Closed short at {new_quantity:.3f} of {old_quantity:.3f} {line.unit}"
    line.changes = append_changelog(
        line.changes, actor.full_name, f"{note}: {cause}." if cause else f"{note}."
    )
    await order_items.save(line)
    return touched


async def _resize[A: (BoughtItemDemandAllocation, SourceItemDemandAllocation)](
    allocations: list[A],
    quantities: list[float],
    save: Callable[[A], Awaitable[object]],
    delete: Callable[[A], Awaitable[None]],
) -> None:
    """Writes the new allocation quantities, deleting an allocation that
    comes out as nothing."""
    for allocation, quantity in zip(allocations, quantities, strict=True):
        if quantity_eq(quantity, allocation.quantity):
            continue
        if is_zero_quantity(quantity):
            await delete(allocation)
        else:
            allocation.quantity = quantity
            await save(allocation)
