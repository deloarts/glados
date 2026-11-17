"""The frozen facts the lifecycle derivations read.

Each dataclass holds what one derivation needs and nothing else: recorded
quantities, intent timestamps, and the derived statuses of the aggregates it
depends on. A lot's facts carry its positions' derived statuses rather than
their stored ones, so the derivations compose in dependency order: order
items and production orders first, then lot positions, lots, orders and
demands. Building the facts from entities is the caller's job; the derivations
never see an entity. Fields are keyword-only, because several of them are
floats that a positional call could silently swap.
"""

from dataclasses import dataclass
from datetime import datetime

from src.modules.fulfillment.domain.value_objects.interruption_reason import InterruptionReason
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus


@dataclass(frozen=True, kw_only=True)
class OrderItemFacts:
    """A supplier order line. `delivered` counts accepted pieces and `lost`
    the rejected pieces the supplier will not replace; both are totals of the
    line's delivery rows."""

    quantity: float
    delivered: float
    lost: float
    requested_at: datetime | None
    ordered_date: datetime | None
    canceled_at: datetime | None


@dataclass(frozen=True, kw_only=True)
class OrderFacts:
    """A supplier order: its intents and the derived statuses of all its
    lines, canceled ones included."""

    requested_at: datetime | None
    ordered_date: datetime | None
    canceled_at: datetime | None
    line_statuses: tuple[OrderItemStatus, ...]


@dataclass(frozen=True, kw_only=True)
class ProductionOrderFacts:
    """A production order. `processed` is the sum of its completion rows'
    quantities, accepted and rejected pieces alike. `open_interruption` is
    the reason of the interruption that has not been resumed, None when there
    is none."""

    quantity: float
    processed: float
    actual_start: datetime | None
    canceled_at: datetime | None
    open_interruption: InterruptionReason | None


@dataclass(frozen=True, kw_only=True)
class PositionLineFacts:
    """The order line linked to a lot position, with its derived status and
    its accepted pieces."""

    status: OrderItemStatus
    quantity: float
    delivered: float


@dataclass(frozen=True, kw_only=True)
class PositionOrderFacts:
    """One production order of a lot position, with its derived status and
    its accepted pieces (`quantity_completed`)."""

    status: ProductionOrderStatus
    quantity: float
    quantity_completed: float


@dataclass(frozen=True, kw_only=True)
class LotPositionFacts:
    """A lot position: its quantity, the order line linked to it (its newest
    live line, else its newest canceled one, None without any), the earlier
    live lines beside it, every production order of the position, canceled
    ones included, and whether its lot is canceled. An earlier live line was
    closed short, and a later line took the rest of the position."""

    quantity: float
    line: PositionLineFacts | None
    orders: tuple[PositionOrderFacts, ...]
    lot_canceled: bool
    closed_lines: tuple[PositionLineFacts, ...] = ()


@dataclass(frozen=True, kw_only=True)
class LotFacts:
    """A production lot: its quantity, the derived statuses of its positions
    in sequence order, and its three intents."""

    quantity: float
    position_statuses: tuple[LotPositionStatus, ...]
    held_at: datetime | None
    canceled_at: datetime | None
    force_completed_at: datetime | None


@dataclass(frozen=True, kw_only=True)
class CoveringLineFacts:
    """The order line an allocation draws on, with its derived status and
    its delivery totals."""

    status: OrderItemStatus
    quantity: float
    delivered: float
    lost: float


@dataclass(frozen=True, kw_only=True)
class CoveringLotFacts:
    """The production lot an allocation draws on, with its derived status and
    its completed count, which is its last position's."""

    status: LotStatus
    quantity: float
    quantity_completed: float


@dataclass(frozen=True, kw_only=True)
class AllocationFacts:
    """One allocation of a demand. A stock allocation has neither a line nor
    a lot; an order allocation has its line and a lot allocation its lot. An
    order or lot allocation without its reference covers nothing and is not
    placed."""

    quantity: float
    from_stock: bool
    line: CoveringLineFacts | None
    lot: CoveringLotFacts | None
    # The pieces of the same line or lot allocated to the demands before this
    # one in the fill order (lifecycle/demand.py), which arrived pieces fill
    # first.
    ahead: float = 0.0

    @classmethod
    def stock(cls, quantity: float) -> "AllocationFacts":
        return cls(quantity=quantity, from_stock=True, line=None, lot=None)

    @classmethod
    def on_line(
        cls, quantity: float, line: CoveringLineFacts, *, ahead: float = 0.0
    ) -> "AllocationFacts":
        return cls(quantity=quantity, from_stock=False, line=line, lot=None, ahead=ahead)

    @classmethod
    def on_lot(
        cls, quantity: float, lot: CoveringLotFacts, *, ahead: float = 0.0
    ) -> "AllocationFacts":
        return cls(quantity=quantity, from_stock=False, line=None, lot=lot, ahead=ahead)


@dataclass(frozen=True, kw_only=True)
class DemandFacts:
    """A demand of any of the three families: its quantity, its allocations
    and its two intents."""

    quantity: float
    allocations: tuple[AllocationFacts, ...]
    canceled_at: datetime | None
    fulfilled_manually_at: datetime | None
