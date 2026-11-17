"""Status of a demand of the bought, made or source family, derived from its
quantity, its allocations and its two intents. The three families share one
table, instantiated once per family enum.

The pieces that arrived on a line, its accepted pieces, and the completed
pieces of a lot fill the allocations on it in one fill order: bought item
demands before source item demands and, within a family, the older demand,
the lower id, first. An allocation covers what reaches it in that order, at
most its own quantity, so a demand is fulfilled as soon as its own pieces
arrived and a line or lot ordered bigger than its demands keeps the surplus
last. Pieces rejected at receipt and written off as lost never count as
arrived; the delivery fits the line's allocations into what is left to come,
and the demand's rest opens again. A canceled line or lot covers nothing.

An allocation is placed once its line is ORDERED or later, or once its lot
has left DRAFT and is neither canceled nor scrapped, so a held lot counts as
placed. FULFILLED needs the covered pieces plus stock to reach the quantity,
which lets stock alone fulfil an OPEN demand in one step. ORDERED needs the
allocations plus stock to reach the quantity and every order or lot
allocation to be placed, so a partly covered demand stays ALLOCATED and its
uncovered rest stays visible. An allocation of zero quantity covers nothing
and is left out of that check, so the rows a full scrap leaves behind never
hold a demand back from ORDERED.
"""

from collections.abc import Iterable
from collections.abc import Sequence
from dataclasses import dataclass

from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.domain.services.lifecycle.facts import AllocationFacts
from src.modules.fulfillment.domain.services.lifecycle.facts import DemandFacts
from src.modules.fulfillment.domain.services.lifecycle.rules import DerivationTable
from src.modules.fulfillment.domain.services.lifecycle.rules import otherwise
from src.modules.fulfillment.domain.services.lifecycle.rules import rule
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.platform.domain.services.quantities import is_zero_quantity
from src.modules.platform.domain.services.quantities import quantity_ge
from src.modules.platform.domain.services.quantities import quantity_gt

_PLACED_LINE = (
    OrderItemStatus.ORDERED,
    OrderItemStatus.PARTIALLY_DELIVERED,
    OrderItemStatus.DELIVERED,
)
_UNPLACED_LOT = (LotStatus.DRAFT, LotStatus.CANCELED, LotStatus.SCRAPPED)


# The fill rank of a family's allocations on a line or lot: bought item
# demands before source item demands; a lot carries made item demands only.
BOUGHT_FILL_RANK = 0
SOURCE_FILL_RANK = 1
MADE_FILL_RANK = 0

# An allocation's place in the fill of its line or lot: its family's rank,
# its demand's id and its quantity.
type FillEntry = tuple[int, int, float]


def pieces_ahead(fill: Iterable[FillEntry], rank: int, demand_item_id: int) -> float:
    """The pieces allocated on a line or lot before the allocation of
    `demand_item_id` of the family `rank`, in the fill order."""
    return sum((quantity for r, d, quantity in fill if (r, d) < (rank, demand_item_id)), 0.0)


def displaced_demand_ids(
    fill: Sequence[FillEntry], arrived: float, rank: int, demand_item_id: int, quantity: float
) -> list[int]:
    """The demands on a line or lot whose arrived pieces would go to the
    allocation of `demand_item_id` of the family `rank` if it held
    `quantity`: the fill hands arrived pieces out by family and demand age,
    so a new or larger allocation of an older demand would otherwise take
    pieces that already reached a younger one."""
    key = (rank, demand_item_id)
    before = list(fill)
    after = [entry for entry in fill if (entry[0], entry[1]) != key] + [(*key, quantity)]
    covered_before = _covered_by_entry(before, arrived)
    covered_after = _covered_by_entry(after, arrived)
    return sorted(
        {
            entry_key[1]
            for entry_key, covered in covered_before.items()
            if entry_key != key and quantity_gt(covered, covered_after.get(entry_key, 0.0))
        }
    )


def _covered_by_entry(fill: Sequence[FillEntry], arrived: float) -> dict[tuple[int, int], float]:
    covered: dict[tuple[int, int], float] = {}
    ahead = 0.0
    for rank, demand_item_id, quantity in sorted(fill, key=lambda e: (e[0], e[1])):
        covered[(rank, demand_item_id)] = min(max(arrived - ahead, 0.0), quantity)
        ahead += quantity
    return covered


def fit_in_fill_order(
    quantities: Sequence[float], limit: float, finished: Sequence[bool] | None = None
) -> list[float]:
    """The allocations of a line or lot, given in fill order, fitted into
    `limit`: unchanged when they fit, else cut from the end of the fill, the
    newest demand first, so a demand never loses pieces that already reached
    it while a later one keeps an allocation. Allocations marked `finished`,
    of demands that are fulfilled or canceled, are cut only after every live
    one. No allocation grows or goes below zero."""
    fitted = list(quantities)
    excess = sum(fitted) - limit
    if not quantity_gt(excess, 0.0):
        return fitted
    done = list(finished) if finished is not None else [False] * len(fitted)
    order = [i for i in reversed(range(len(fitted))) if not done[i]] + [
        i for i in reversed(range(len(fitted))) if done[i]
    ]
    for index in order:
        cut = min(fitted[index], excess)
        fitted[index] -= cut
        excess -= cut
        if not quantity_gt(excess, 0.0):
            break
    return fitted


def arrived_pieces(allocation: AllocationFacts) -> float:
    """The pieces that arrived on the allocation's line, its accepted ones,
    or the completed pieces of its lot; 0 for a stock allocation, a missing
    or canceled reference."""
    if allocation.from_stock:
        return 0.0
    line = allocation.line
    if line is not None:
        return 0.0 if line.status == OrderItemStatus.CANCELED else line.delivered
    lot = allocation.lot
    if lot is not None:
        return 0.0 if lot.status == LotStatus.CANCELED else lot.quantity_completed
    return 0.0


def covered_pieces(allocation: AllocationFacts) -> float:
    """The arrived pieces that reach the allocation in the fill order, from 0
    to its quantity."""
    return min(max(arrived_pieces(allocation) - allocation.ahead, 0.0), allocation.quantity)


def is_placed(allocation: AllocationFacts) -> bool:
    """Whether an order or lot allocation is placed: its line is ORDERED or
    later, or its lot is past DRAFT and neither CANCELED nor SCRAPPED."""
    if allocation.from_stock:
        return False
    if allocation.line is not None:
        return allocation.line.status in _PLACED_LINE
    if allocation.lot is not None:
        return allocation.lot.status not in _UNPLACED_LOT
    return False


@dataclass(frozen=True)
class DemandCoverage:
    """The totals the demand table compares with the demand quantity.
    `allocated` and `delivered` cover the order and lot allocations only;
    `all_placed` is true when every one of them with a quantity above zero is
    placed."""

    allocated: float
    stock: float
    delivered: float
    all_placed: bool


def demand_coverage(facts: DemandFacts) -> DemandCoverage:
    covering = [a for a in facts.allocations if not a.from_stock]
    return DemandCoverage(
        allocated=sum((a.quantity for a in covering), 0.0),
        stock=sum((a.quantity for a in facts.allocations if a.from_stock), 0.0),
        delivered=sum((covered_pieces(a) for a in covering), 0.0),
        all_placed=all(is_placed(a) for a in covering if not is_zero_quantity(a.quantity)),
    )


def _arrived(facts: DemandFacts) -> bool:
    coverage = demand_coverage(facts)
    return quantity_ge(coverage.delivered + coverage.stock, facts.quantity)


def _covered_and_placed(facts: DemandFacts) -> bool:
    coverage = demand_coverage(facts)
    return coverage.all_placed and quantity_ge(coverage.allocated + coverage.stock, facts.quantity)


def _covered_at_all(facts: DemandFacts) -> bool:
    coverage = demand_coverage(facts)
    return quantity_gt(coverage.allocated + coverage.stock, 0.0)


_TERMINAL_VALUES = frozenset({BoughtItemDemandStatus.FULFILLED, BoughtItemDemandStatus.CANCELED})


def uncovered_rest(status: str, quantity: float, covered: float) -> float:
    """What a demand of any family still lacks before it is fully covered,
    `covered` being its allocations from orders or lots and from stock
    together; 0 for a fulfilled or canceled demand and within the
    tolerance. Auto-allocation and auto-assignment select their demands by
    it, so a demand that the derivation calls ORDERED, which is fully
    covered, is never picked again."""
    if status in _TERMINAL_VALUES:
        return 0.0
    rest = quantity - covered
    return rest if quantity_gt(rest, 0.0) else 0.0


def _demand_status_table[S: (BoughtItemDemandStatus, MadeItemDemandStatus, SourceItemDemandStatus)](
    key: str, status: type[S]
) -> DerivationTable[DemandFacts, S]:
    return DerivationTable(
        key=key,
        rules=(
            rule(1, "canceled_at set", status.CANCELED, lambda f: f.canceled_at is not None),
            rule(
                2,
                "fulfilled_manually_at set",
                status.FULFILLED,
                lambda f: f.fulfilled_manually_at is not None,
            ),
            rule(3, "delivered + stock >= quantity", status.FULFILLED, _arrived),
            rule(
                4,
                "allocated + stock >= quantity and every order- or lot-sourced allocation "
                "above zero is placed",
                status.ORDERED,
                _covered_and_placed,
            ),
            rule(5, "allocated + stock > 0", status.ALLOCATED, _covered_at_all),
        ),
        fallback=otherwise(6, status.OPEN),
    )


BOUGHT_DEMAND_STATUS = _demand_status_table("bought_item_demand_status", BoughtItemDemandStatus)
MADE_DEMAND_STATUS = _demand_status_table("made_item_demand_status", MadeItemDemandStatus)
SOURCE_DEMAND_STATUS = _demand_status_table("source_item_demand_status", SourceItemDemandStatus)
