"""Allocation-quantity maths and allocation guards shared by the bought-item,
source-item and made-item demand aggregates. Bought and source items take
coverage from order items (OrderItemCoverageSource), made items from their
covering lots. The quantity summaries built on it are what the demand tables
show; a demand's status is derived by the lifecycle reconciler
(domain/services/lifecycle/demand.py), whose placement and covered share the
coverage sources reuse, so the summary and the status agree. No I/O."""

from collections.abc import Iterable
from collections.abc import Mapping
from collections.abc import Sequence
from dataclasses import dataclass
from typing import ClassVar
from typing import Protocol

from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.errors import AllocationOrderItemCanceledError
from src.modules.fulfillment.domain.errors import AllocationOverflowError
from src.modules.fulfillment.domain.services.demand_terms import DemandTerms
from src.modules.fulfillment.domain.services.lifecycle.demand import FillEntry
from src.modules.fulfillment.domain.services.lifecycle.demand import arrived_pieces
from src.modules.fulfillment.domain.services.lifecycle.demand import is_placed
from src.modules.fulfillment.domain.services.lifecycle.demand import pieces_ahead
from src.modules.fulfillment.domain.services.lifecycle.facts import AllocationFacts
from src.modules.fulfillment.domain.services.lifecycle.facts import CoveringLineFacts
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.crud_permission_rules import assert_has_permission
from src.modules.platform.domain.services.quantities import assert_whole_pieces
from src.modules.platform.domain.services.quantities import quantity_gt
from src.modules.platform.domain.value_objects.permission import Permission


@dataclass(frozen=True)
class CoverageInfo:
    is_placed: bool  # counts toward "ordered" (e.g. order placed / lot beyond DRAFT)
    arrived: float  # pieces arrived on the line or completed on the lot, for its fill


class AllocationCoverageSource(Protocol):
    def coverage_for(self, ref_id: int) -> CoverageInfo | None: ...


class _AllocationLike(Protocol):
    demand_item_id: int
    quantity: float

    @property
    def source(self) -> str: ...

    @property
    def coverage_ref_id(self) -> int | None: ...


class _FillableAllocation(Protocol):
    demand_item_id: int
    quantity: float

    @property
    def source(self) -> str: ...

    @property
    def coverage_ref_id(self) -> int | None: ...


def fill_by_reference(
    *families: tuple[int, Iterable[_FillableAllocation], str],
) -> dict[int, list[FillEntry]]:
    """The fill entries of every line or lot, from the allocations of each
    family given as (fill rank, allocations, stock source value); stock
    allocations take no part. A caller passes every allocation on the lines
    or lots it reads, of other demands too, or a demand's place in the fill
    comes out too early."""
    fill: dict[int, list[FillEntry]] = {}
    for rank, allocations, stock_source_value in families:
        for a in allocations:
            if a.source != stock_source_value and a.coverage_ref_id is not None:
                fill.setdefault(a.coverage_ref_id, []).append((rank, a.demand_item_id, a.quantity))
    return fill


def compute_coverage_totals(
    allocations: Sequence[_AllocationLike],
    coverage: AllocationCoverageSource,
    stock_source_value: str,
    *,
    rank: int,
    fill: Mapping[int, Sequence[FillEntry]],
) -> tuple[float, float, float, float]:
    """(allocated, ordered, delivered, fulfilled_from_stock) totals. The
    delivered pieces of an allocation are the ones that reach it in the fill
    of its line or lot (`fill`, by reference id; `rank` is the family's fill
    rank), as the demand derivation counts them."""
    coverage_allocations = [a for a in allocations if a.source != stock_source_value]
    allocated = sum(a.quantity for a in coverage_allocations)
    fulfilled_from_stock = sum(a.quantity for a in allocations if a.source == stock_source_value)

    ordered = 0.0
    delivered = 0.0
    for a in coverage_allocations:
        if a.coverage_ref_id is None:
            continue
        info = coverage.coverage_for(a.coverage_ref_id)
        if info is None:
            continue
        if info.is_placed:
            ordered += a.quantity
        ahead = pieces_ahead(fill.get(a.coverage_ref_id, ()), rank, a.demand_item_id)
        delivered += min(max(info.arrived - ahead, 0.0), a.quantity)

    return allocated, ordered, delivered, fulfilled_from_stock


def line_coverage(order_item: OrderItem) -> CoverageInfo:
    """Whether a line is placed and how many pieces arrived on it, as the
    demand derivation reads them: its accepted pieces, never the ones lost at
    receipt, and nothing on a canceled line."""
    facts = AllocationFacts.on_line(
        1.0,
        CoveringLineFacts(
            status=OrderItemStatus(order_item.status),
            quantity=order_item.quantity,
            delivered=order_item.quantity_delivered,
            lost=order_item.quantity_rejected_lost,
        ),
    )
    return CoverageInfo(is_placed=is_placed(facts), arrived=arrived_pieces(facts))


class OrderItemCoverageSource:
    """Order-item-backed coverage adapter for compute_coverage_totals,
    shared by the bought-item and source-item allocation aggregates."""

    def __init__(self, order_items_by_id: dict[int, OrderItem]) -> None:
        self._order_items_by_id = order_items_by_id

    def coverage_for(self, ref_id: int) -> CoverageInfo | None:
        order_item = self._order_items_by_id.get(ref_id)
        if order_item is None:
            return None
        return line_coverage(order_item)


def order_item_capacity_left(
    order_item: OrderItem, allocated_on_line: float, released: float = 0.0
) -> float:
    """How much of an order item is still free to allocate. allocated_on_line
    is everything allocated to the line by bought and source item demands
    together, since both draw on the same quantity; released is the quantity
    of an allocation that is about to be replaced, which no longer counts
    against the line. Pieces lost at receipt never come, so they are no
    capacity, and pieces delivered within the over-delivery tolerance beyond
    the line's quantity are (OrderItem.allocatable_quantity). The result is
    never below zero."""
    return max(0.0, order_item.allocatable_quantity - (allocated_on_line - released))


@dataclass(frozen=True)
class RecordedSubstitution:
    """The substitution fields an order line allocation stores: the item the
    line is for and the reason, or both None for a plain match."""

    item_id: int | None
    reason: str | None


def recorded_substitution(
    demanded_item_id: int | None, line_item_id: int | None, reason: str | None
) -> RecordedSubstitution:
    """What an order line allocation records as its substitution. It is a
    substitution only when the line's item differs from the item the demand
    asks for, and then it records the line's item with the reason given. A
    line for the demand's own item is a plain match whatever the caller
    sent, so a declared substitute and any reason are dropped. Every writer
    of a new or repointed order line allocation goes through this, in the
    bought and the source item family alike."""
    if line_item_id == demanded_item_id:
        return RecordedSubstitution(item_id=None, reason=None)
    return RecordedSubstitution(item_id=line_item_id, reason=reason)


class _DemandLike(Protocol):
    id: int
    quantity: float
    unit: str

    @property
    def status(self) -> str: ...


class DemandAllocationRules:
    """The allocation guards every demand family shares. A family's rules
    class subclasses it, binds its `terms` and adds only the checks its own
    family has, such as which order line may cover its demands."""

    terms: ClassVar[DemandTerms]

    @staticmethod
    def assert_can_allocate(actor: User) -> None:
        assert_has_permission(actor, Permission.WRITE_ALLOCATIONS, "manage", "allocations")

    @classmethod
    def assert_not_terminal(cls, demand: _DemandLike) -> None:
        """Raises when the demand is already fulfilled or canceled."""
        terms = cls.terms
        if demand.status == terms.fulfilled:
            raise terms.already_fulfilled_error(f"{terms.noun} #{demand.id} is already fulfilled.")
        if demand.status == terms.canceled:
            raise terms.already_canceled_error(f"{terms.noun} #{demand.id} is canceled.")

    @classmethod
    def assert_release_allowed(cls, demand: _DemandLike) -> None:
        """Raises when one of the demand's allocations may not be deleted,
        which is the case once the demand is fulfilled. Canceling a demand
        releases its allocations, but a demand canceled before cancels did
        so can still hold some. Releasing them stays allowed, as the one
        exception to the demand intent table (lifecycle/intents.py
        DEMAND_INTENTS, which allows allocation writes on live demands only),
        so the line or stock they hold can be freed."""
        terms = cls.terms
        if demand.status == terms.fulfilled:
            raise terms.already_fulfilled_error(f"{terms.noun} #{demand.id} is already fulfilled.")

    @classmethod
    def assert_no_overallocation(
        cls,
        demand: _DemandLike,
        existing_allocated: float,
        new_quantity: float,
        exclude_existing: float = 0.0,
    ) -> None:
        """Raises when the new allocation, replacing any existing one of
        `exclude_existing`, would exceed the demand's total quantity, or is
        not a whole number while the demand's unit counts whole things."""
        assert_whole_pieces(new_quantity, what="The allocated quantity", unit=demand.unit)
        effective_existing = existing_allocated - exclude_existing
        if quantity_gt(effective_existing + new_quantity, demand.quantity):
            raise AllocationOverflowError(
                f"{cls.terms.noun} #{demand.id} requests {demand.quantity} {demand.unit}. "
                f"Net allocated: {effective_existing:.3f}. "
                f"Attempting to allocate: {new_quantity:.3f}. "
                f"Total {effective_existing + new_quantity:.3f} would exceed demand."
            )


def assert_line_takes_allocations(order_item: OrderItem) -> None:
    """Raises when the order line is canceled. A canceled line keeps its
    quantity and holds no allocation, since canceling it released them, so
    an allocation writer checks this besides the line's free capacity."""
    if order_item.canceled_at is not None or order_item.status == OrderItemStatus.CANCELED:
        raise AllocationOrderItemCanceledError(
            f"Order item #{order_item.id} is canceled and takes no allocation."
        )


def units_differ(demand_unit: str, line_unit: str) -> bool:
    """Whether a demand and the order line it draws on name different
    units, compared without case and surrounding spaces. The allocation is
    still allowed, since nothing converts between units yet; the clients
    warn on it, because the line's pieces may not mean the demand's."""
    return demand_unit.strip().upper() != line_unit.strip().upper()
