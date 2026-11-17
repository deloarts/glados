"""
Shared order-item/order lookups and demand-summary assembly for the
order-item-backed allocation families: bought items
(src/modules/fulfillment/application/use_cases/bought_item_demand/get_allocations.py) and source
items (src/modules/fulfillment/application/use_cases/source_item_allocation/get_allocations.py). Both
families allocate demand to order items the same way and differ only in
their entity types, exceptions and how a substitution is described, so
everything here works against a small structural Protocol instead of either
concrete allocation entity, and callers supply their own family-specific
pieces (the demand/allocation repositories, the compute_summary function,
the substitution-building strategy and the result DTO class).
"""

from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Iterable
from collections.abc import Mapping
from collections.abc import Sequence
from typing import Protocol
from typing import TypeVar

from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.services.allocation_coverage import units_differ
from src.modules.fulfillment.domain.services.lifecycle.demand import FillEntry
from src.modules.fulfillment.domain.value_objects.demand_summary import DemandQuantitySummary
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import IOrderRepository


class AllocationRow(Protocol):
    """Structural shape both BoughtItemDemandAllocation and
    SourceItemDemandAllocation satisfy, everything below needs."""

    demand_item_id: int
    order_item_id: int | None


class DemandRow(Protocol):
    """What every demand family's entity has that the summaries read."""

    id: int
    unit: str


class UnitMarkedResult(Protocol):
    """An allocation result the unit comparison fills."""

    demand_item_id: int
    order_item_unit: str | None
    demand_unit: str | None
    unit_mismatch: bool


AllocationT = TypeVar("AllocationT", bound=AllocationRow)
DemandT = TypeVar("DemandT", bound=DemandRow)
AllocationResultT = TypeVar("AllocationResultT", bound=UnitMarkedResult)
SubstitutionT = TypeVar("SubstitutionT")
ResultT = TypeVar("ResultT")


# ── Order item / order lookups ──────────────────────────────────────────


async def order_items_for_allocations(
    allocations: list[AllocationT],
    order_item_repo: IOrderItemRepository,
) -> dict[int, OrderItem]:
    """Fetches the order items referenced by `allocations`, keyed by id.
    Skips stock allocations (order_item_id is None) and orphaned
    references whose order item no longer exists."""
    order_item_ids = {a.order_item_id for a in allocations if a.order_item_id is not None}
    result: dict[int, OrderItem] = {}
    for oid in order_item_ids:
        row = await order_item_repo.get_by_id(oid)
        if row is not None:
            result[oid] = row
    return result


async def order_items_for_allocation_batch(
    allocations: list[AllocationT],
    order_item_repo: IOrderItemRepository,
) -> dict[int, OrderItem]:
    """Batch counterpart to order_items_for_allocations: one get_by_ids
    query for every order item referenced anywhere in `allocations`
    (typically the whole batch's allocations, not one demand's), instead
    of one get_by_id query per referenced id. Same skip/orphan semantics:
    stock allocations and dangling order_item_id references are simply
    absent from the result. Callers that need a per-demand-scoped dict
    (e.g. to feed a compute_summary that derives order_ids from every
    value in the dict it's given) must subscope this batch-wide result
    themselves; this function only changes how the lookup is fetched,
    never what it would contain for a given `allocations` list."""
    order_item_ids = list({a.order_item_id for a in allocations if a.order_item_id is not None})
    if not order_item_ids:
        return {}
    return {item.id: item for item in await order_item_repo.get_by_ids(order_item_ids)}


async def orders_for_order_items(
    order_items: Iterable[OrderItem],
    order_repo: IOrderRepository,
) -> dict[int, Order]:
    """Fetches the orders referenced by `order_items`, keyed by id. One
    get_by_ids query for every order referenced anywhere in `order_items`,
    instead of one get_by_id query per referenced order. Orders that no
    longer exist are simply absent from the result."""
    order_ids = list({oi.order_id for oi in order_items})
    if not order_ids:
        return {}
    return {order.id: order for order in await order_repo.get_by_ids(order_ids)}


async def fetch_order_lookup(
    allocations: list[AllocationT],
    order_item_repo: IOrderItemRepository,
    order_repo: IOrderRepository,
) -> tuple[dict[int, OrderItem], dict[int, Order]]:
    """The order-item and order lookups almost every allocation read use
    case needs, fetched together since the order lookup depends on the
    order-item one."""
    order_items_by_id = await order_items_for_allocation_batch(allocations, order_item_repo)
    orders_by_id = await orders_for_order_items(order_items_by_id.values(), order_repo)
    return order_items_by_id, orders_by_id


async def order_numbers_for(
    order_ids: tuple[int, ...] | list[int],
    order_repo: IOrderRepository,
    cache: dict[int, Order] | None = None,
) -> list[str]:
    """Resolves order ids to order numbers, in the same order, skipping
    any id that no longer resolves to an order. `cache` lets a batch of
    calls (GetDemandSummaryBatch and its source-item counterpart) share
    one growing set of already-fetched orders across demands."""
    cache = cache if cache is not None else {}
    missing_ids = list({oid for oid in order_ids if oid not in cache})
    if missing_ids:
        for order in await order_repo.get_by_ids(missing_ids):
            cache[order.id] = order
    return [cache[oid].order_number for oid in order_ids if oid in cache]


# ── Substitutions ───────────────────────────────────────────────────────


class SubstitutingAllocation(Protocol):
    """The fields a substitution total reads off an allocation."""

    @property
    def quantity(self) -> float: ...

    @property
    def substitute_reason(self) -> str | None: ...


SubstitutingT = TypeVar("SubstitutingT", bound=SubstitutingAllocation)


def group_substitutions(
    allocations: Iterable[SubstitutingT],
    substitute_id: Callable[[SubstitutingT], int | None],
) -> dict[int, tuple[str | None, float]]:
    """Totals the substituting allocations per substitute id, in order of
    first appearance, keeping the first non-null reason. Allocations whose
    `substitute_id` is None are not substitutions and are skipped."""
    groups: dict[int, tuple[str | None, float]] = {}
    for alloc in allocations:
        sid = substitute_id(alloc)
        if sid is None:
            continue
        if sid in groups:
            reason, qty = groups[sid]
            groups[sid] = (reason or alloc.substitute_reason, qty + alloc.quantity)
        else:
            groups[sid] = (alloc.substitute_reason, alloc.quantity)
    return groups


# ── Enriched allocation results ─────────────────────────────────────────


def to_allocation_result(
    allocation: AllocationT,
    order_items_by_id: dict[int, OrderItem] | None,
    orders_by_id: dict[int, Order] | None,
    build: Callable[[AllocationT, OrderItem | None, Order | None], ResultT],
) -> ResultT:
    """Resolves the order item (and its order) an allocation references,
    if any, then hands them to `build` to construct the family's
    AllocationResult DTO. Both families enrich an allocation the same
    way; they differ only in which DTO fields they copy off the order
    item and the allocation itself, which `build` encapsulates."""
    order_item = (
        order_items_by_id.get(allocation.order_item_id)
        if order_items_by_id and allocation.order_item_id is not None
        else None
    )
    order = orders_by_id.get(order_item.order_id) if order_item and orders_by_id else None
    return build(allocation, order_item, order)


async def get_enriched_allocations(
    allocations: list[AllocationT],
    order_item_repo: IOrderItemRepository,
    order_repo: IOrderRepository,
    build: Callable[[AllocationT, OrderItem | None, Order | None], ResultT],
) -> list[ResultT]:
    """Shared GetAllocationsFor*/GetAllocationsForOrderItem body: fetch the
    order-item/order lookup for `allocations`, then enrich each one via
    `build`."""
    order_items_by_id, orders_by_id = await fetch_order_lookup(
        allocations, order_item_repo, order_repo
    )
    return [to_allocation_result(a, order_items_by_id, orders_by_id, build) for a in allocations]


# ── Demand summary assembly ──────────────────────────────────────────────


def _lines_differ_in_unit(demand_unit: str, lines: Iterable[OrderItem]) -> bool:
    return any(units_differ(demand_unit, line.unit) for line in lines)


async def mark_unit_mismatches(
    results: list[AllocationResultT],
    get_demands: Callable[[list[int]], Awaitable[Sequence[DemandRow]]],
) -> list[AllocationResultT]:
    """Fills each allocation result's demand unit and whether its line names
    another one, from the demands read in one batch."""
    units = {d.id: d.unit for d in await get_demands(sorted({r.demand_item_id for r in results}))}
    for result in results:
        result.demand_unit = units.get(result.demand_item_id)
        result.unit_mismatch = (
            result.demand_unit is not None
            and result.order_item_unit is not None
            and units_differ(result.demand_unit, result.order_item_unit)
        )
    return results


def build_demand_summary_result(
    result_cls: Callable[..., ResultT],
    summary: DemandQuantitySummary,
    order_numbers: list[str],
    substitutions: list[SubstitutionT],
    *,
    unit_mismatch: bool = False,
) -> ResultT:
    """Builds a DemandSummaryResult (or its source-item counterpart) from
    a DemandQuantitySummary; both families' result DTOs share every field
    except `substitutions`, whose entries are a family-specific DTO."""
    return result_cls(
        unit_mismatch=unit_mismatch,
        demand_item_id=summary.demand_item_id,
        unit=summary.unit,
        total=summary.total,
        allocated=summary.allocated,
        fulfilled_from_stock=summary.fulfilled_from_stock,
        ordered=summary.ordered,
        delivered=summary.delivered,
        remaining=summary.remaining,
        unallocated=summary.unallocated,
        pending=summary.pending,
        in_transit=summary.in_transit,
        is_fully_allocated=summary.is_fully_allocated,
        is_fully_delivered=summary.is_fully_delivered,
        order_ids=list(summary.order_ids),
        order_numbers=order_numbers,
        substitutions=substitutions,
    )


async def build_demand_summary(
    *,
    demand_item_id: int,
    get_demand: Callable[[int], Awaitable[DemandT | None]],
    not_found: Callable[[int], Exception],
    get_allocations: Callable[[int], Awaitable[list[AllocationT]]],
    order_item_repo: IOrderItemRepository,
    order_repo: IOrderRepository,
    compute_summary: Callable[
        [DemandT, list[AllocationT], dict[int, OrderItem], Mapping[int, Sequence[FillEntry]]],
        DemandQuantitySummary,
    ],
    get_fill: Callable[[list[int]], Awaitable[Mapping[int, Sequence[FillEntry]]]],
    build_substitutions: Callable[
        [list[AllocationT], dict[int, OrderItem]], Awaitable[list[SubstitutionT]]
    ],
    result_cls: Callable[..., ResultT],
) -> ResultT:
    """Shared GetDemandSummary flow for order-item-backed demand
    allocations: look up the demand (raising `not_found(demand_item_id)`
    if it does not exist), fetch its allocations and the order items they
    reference with their fill (`get_fill`, every allocation on those lines),
    compute the quantity summary, resolve substitutions through
    the caller's family-specific strategy, and assemble the result DTO."""
    demand = await get_demand(demand_item_id)
    if demand is None:
        raise not_found(demand_item_id)

    allocations = await get_allocations(demand_item_id)
    order_items_by_id = await order_items_for_allocation_batch(allocations, order_item_repo)
    fill = await get_fill(sorted(order_items_by_id))

    summary = compute_summary(demand, allocations, order_items_by_id, fill)
    substitutions = await build_substitutions(allocations, order_items_by_id)
    order_numbers = await order_numbers_for(summary.order_ids, order_repo)

    return build_demand_summary_result(
        result_cls,
        summary,
        order_numbers,
        substitutions,
        unit_mismatch=_lines_differ_in_unit(demand.unit, order_items_by_id.values()),
    )


async def build_demand_summary_batch(
    *,
    demand_item_ids: list[int],
    get_demands: Callable[[list[int]], Awaitable[list[DemandT]]],
    get_allocations: Callable[[list[int]], Awaitable[list[AllocationT]]],
    order_item_repo: IOrderItemRepository,
    order_repo: IOrderRepository,
    compute_summary: Callable[
        [DemandT, list[AllocationT], dict[int, OrderItem], Mapping[int, Sequence[FillEntry]]],
        DemandQuantitySummary,
    ],
    get_fill: Callable[[list[int]], Awaitable[Mapping[int, Sequence[FillEntry]]]],
    build_substitutions: Callable[
        [list[AllocationT], dict[int, OrderItem]], Awaitable[list[SubstitutionT]]
    ],
    result_cls: Callable[..., ResultT],
) -> dict[int, ResultT]:
    """Shared GetDemandSummaryBatch flow: one get_by_ids for demands, one
    get_by_demand_item_ids for every allocation in the batch, one
    order-item batch fetch for the whole set of referenced order items,
    instead of one query per demand for each of those three. Missing
    demands are skipped, not errored, and iteration stays over
    `demand_item_ids` so duplicate ids still collapse to one dict entry.
    Order numbers are cached across the whole batch via `order_numbers_for`;
    the per-demand order-items dict passed to compute_summary/
    build_substitutions is always rescoped to that demand's own
    allocations, never the batch-wide dict, since compute_summary derives
    order_ids from every value it is given."""
    results: dict[int, ResultT] = {}
    orders_cache: dict[int, Order] = {}

    demands_by_id = {demand.id: demand for demand in await get_demands(demand_item_ids)}
    all_allocations = await get_allocations(demand_item_ids)
    allocations_by_demand: dict[int, list[AllocationT]] = {}
    for allocation in all_allocations:
        allocations_by_demand.setdefault(allocation.demand_item_id, []).append(allocation)
    order_items_by_id = await order_items_for_allocation_batch(all_allocations, order_item_repo)
    fill = await get_fill(sorted(order_items_by_id))

    for demand_id in demand_item_ids:
        demand = demands_by_id.get(demand_id)
        if demand is None:
            continue

        allocations = allocations_by_demand.get(demand_id, [])
        demand_order_item_ids = {
            a.order_item_id for a in allocations if a.order_item_id is not None
        }
        demand_order_items_by_id = {
            oid: order_items_by_id[oid] for oid in demand_order_item_ids if oid in order_items_by_id
        }

        summary = compute_summary(demand, allocations, demand_order_items_by_id, fill)
        substitutions = await build_substitutions(allocations, demand_order_items_by_id)
        order_numbers = await order_numbers_for(summary.order_ids, order_repo, orders_cache)

        results[demand_id] = build_demand_summary_result(
            result_cls,
            summary,
            order_numbers,
            substitutions,
            unit_mismatch=_lines_differ_in_unit(demand.unit, demand_order_items_by_id.values()),
        )

    return results
