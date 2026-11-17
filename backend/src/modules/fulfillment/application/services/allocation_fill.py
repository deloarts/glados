"""
The fill of the order lines and lots a demand summary reads: every allocation
on them, of other demands too, as fill entries (allocation_coverage.
fill_by_reference), so the summary counts the pieces that reach a demand in
the same fill order the demand derivation does (lifecycle/demand.py). A
bought item demand comes before every source item demand on a line, so a
bought summary needs the bought allocations only; a source summary needs
both families.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from src.modules.catalogue.domain.value_objects.bought_item_status import AllocationSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemAllocationSource
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.errors import AllocationTakesArrivedPiecesError
from src.modules.fulfillment.domain.services.allocation_coverage import fill_by_reference
from src.modules.fulfillment.domain.services.lifecycle.demand import BOUGHT_FILL_RANK
from src.modules.fulfillment.domain.services.lifecycle.demand import MADE_FILL_RANK
from src.modules.fulfillment.domain.services.lifecycle.demand import SOURCE_FILL_RANK
from src.modules.fulfillment.domain.services.lifecycle.demand import FillEntry
from src.modules.fulfillment.domain.services.lifecycle.demand import displaced_demand_ids
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemAllocationSource,
)
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    IMadeItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemAllocationRepository,
)


async def line_fill(
    order_item_ids: Iterable[int],
    *,
    bought: IBoughtItemAllocationRepository | None = None,
    source: ISourceItemAllocationRepository | None = None,
) -> dict[int, list[FillEntry]]:
    """The fill entries of the order lines, from the allocations of each
    family whose repository is given."""
    ids = sorted(set(order_item_ids))
    if not ids:
        return {}
    bought_entries = (
        BOUGHT_FILL_RANK,
        await bought.get_by_order_item_ids(ids) if bought is not None else [],
        AllocationSource.STOCK,
    )
    source_entries = (
        SOURCE_FILL_RANK,
        await source.get_by_order_item_ids(ids) if source is not None else [],
        SourceItemAllocationSource.STOCK,
    )
    return fill_by_reference(bought_entries, source_entries)


async def lot_fill(
    lot_ids: Iterable[int], made_allocations: IMadeItemAllocationRepository
) -> dict[int, list[FillEntry]]:
    """The fill entries of the lots, from their made allocations."""
    ids = sorted(set(lot_ids))
    if not ids:
        return {}
    return fill_by_reference(
        (
            MADE_FILL_RANK,
            await made_allocations.get_by_lot_ids(ids),
            MadeItemAllocationSource.STOCK,
        )
    )


@dataclass(frozen=True)
class LineFillRepos:
    """The allocation repositories of both families an order line carries,
    which an allocation writer reads the line's whole fill from."""

    bought: IBoughtItemAllocationRepository
    source: ISourceItemAllocationRepository


async def displaced_on_line(
    repos: LineFillRepos, line: OrderItem, rank: int, demand_item_id: int, quantity: float
) -> list[int]:
    """The demands whose arrived pieces on `line` the allocation of
    `demand_item_id` of the family `rank` would take if it held `quantity`."""
    fill = (await line_fill([line.id], bought=repos.bought, source=repos.source)).get(line.id, [])
    arrived = 0.0 if line.status == OrderItemStatus.CANCELED else line.quantity_delivered
    return displaced_demand_ids(fill, arrived, rank, demand_item_id, quantity)


async def assert_takes_no_arrived_pieces(
    repos: LineFillRepos, line: OrderItem, rank: int, demand_item_id: int, quantity: float
) -> None:
    """Refuses an allocation that would take pieces already arrived for
    another demand on the line (displaced_on_line)."""
    displaced = await displaced_on_line(repos, line, rank, demand_item_id, quantity)
    if displaced:
        names = ", ".join(f"#{d}" for d in displaced)
        raise AllocationTakesArrivedPiecesError(
            f"Order item #{line.id} already delivered the pieces this allocation would take "
            f"from demand(s) {names}; allocate on another line or after more pieces arrive."
        )
