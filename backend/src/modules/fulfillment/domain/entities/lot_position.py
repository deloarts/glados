"""The execution unit of a ProductionLot: consecutive steps done by one
party. Adding an EXTERNAL position to an order is the supplier assignment;
INTERNAL positions are worked through production orders. Kind, status and
completed count are derived from the position's live order line and its
production orders and stored, never set by users."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from datetime import date
from datetime import datetime
from typing import TYPE_CHECKING

from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.shared_kernel.domain.entities.base import Entity

if TYPE_CHECKING:
    from src.modules.fulfillment.domain.entities.lot_step import LotStep
    from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
    from src.modules.platform.domain.entities.user import User


@dataclass
class EarlierOrderLine:
    """A live order line of a position older than its newest one, read for
    display. Only a line closed short can be followed by another, so each
    such line was closed short."""

    order_item_id: int
    order_id: int | None
    order_number: str
    supplier_name: str
    quantity: float
    quantity_delivered: float
    unit: str
    closed_short: bool


@dataclass
class LotPosition(Entity):
    # ── Server-managed ────────────────────────────────────────────────
    created: datetime
    changed: datetime | None
    changes: list[str]

    # ── Core fields ───────────────────────────────────────────────────
    sequence: int  # 1-based, gapless, position in the lot's execution timeline
    kind: LotPositionKind  # UNASSIGNED | EXTERNAL | INTERNAL | MIXED, derived + stored
    status: LotPositionStatus  # derived + stored
    # The lot's quantity, or more on a position before a scrap point, whose
    # output also fed the scrapped pieces.
    quantity: float
    quantity_completed: float  # derived + stored, never above `quantity`
    note: str | None

    # ── Relations (FK ids only) ───────────────────────────────────────
    creator_id: int
    lot_id: int  # → ProductionLot

    # ── Denormalized (read-only, populated by repository mapper) ──────
    creator: User | None = None
    changed_by_id: int | None = None
    changed_by: User | None = None
    steps: list[LotStep] = field(default_factory=list)  # this position's steps, ordered by sequence

    # Joined from the position's newest live order item, which holds the
    # FK. Earlier live lines of the position were closed short; they count
    # only through closed_lines_quantity.
    order_item_id: int | None = None
    order_id: int | None = None
    order_number: str = ""
    supplier_name: str = ""
    order_item_status: OrderItemStatus | None = None  # None without a live line
    expected_delivery_date: date | None = None
    # Needed for MIXED remaining and completed quantities.
    order_item_quantity: float | None = None
    order_item_quantity_delivered: float | None = None
    # Whether that line was closed short, which leaves the rest of the
    # position to a new line.
    order_item_closed_short: bool = False
    # What the earlier lines closed short hold, the pieces they delivered
    # and lost, and the pieces they delivered.
    closed_lines_quantity: float = 0.0
    closed_lines_delivered: float = 0.0
    # Those earlier lines themselves, newest first, for display.
    earlier_order_lines: list[EarlierOrderLine] = field(default_factory=list)
    # The pieces handed to the supplier of an EXTERNAL or MIXED position.
    provisioned_quantity: float = 0.0
    # Delivery facts, so the lots list needs no extra order fetch.
    order_item_delivery_date: datetime | None = None
    order_item_expected_pickup_date: date | None = None
    order_item_ready_for_pickup_date: datetime | None = None
    # More than one means a split delivery.
    order_item_delivery_record_count: int = 0
    order_item_unit: str = ""
    order_item_items_per_unit: float = 1.0
    # The line's edit version, which an edit of the line from the lot sends.
    order_item_edit_version: int = 0
    # The orderer, else the item's creator.
    order_item_ordered_by_name: str | None = None

    # An internal position can be split across several orders.
    production_orders: list[ProductionOrder] = field(default_factory=list)

    # The supplier of that line.
    order_item_supplier_id: int | None = None
    # Without it the forecast sums the steps' lead times.
    order_item_supplier_external_lead_time_days: int | None = None

    # Scheduler forecast for EXTERNAL/MIXED positions. A typed date on the
    # order item always wins for readiness.
    planned_pickup_date: date | None = None
    planned_delivery_date: date | None = None
    # External work only: the latest day it can leave for the supplier
    # without making the lot miss its target date, None without one.
    latest_pickup_date: date | None = None
    # The latest pickup plus the lead days, the day it is back at the latest.
    latest_delivery_date: date | None = None
