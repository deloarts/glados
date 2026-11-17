"""
A purchase order sent to a supplier.
Groups one or more OrderItems.
Status: DRAFT | REQUESTED | PARTIALLY_ORDERED | ORDERED | PARTIALLY_DELIVERED | DELIVERED | CANCELED
"""

from dataclasses import dataclass
from dataclasses import field
from datetime import date
from datetime import datetime

from src.modules.fulfillment.domain.entities.order_extra_cost import OrderExtraCost
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.platform.domain.entities.user import User
from src.shared_kernel.domain.entities.base import Entity


@dataclass(frozen=True)
class OrderQuoteRequestRef:
    """A quote request one of the order's lines was awarded from."""

    id: int
    request_number: str


@dataclass
class Order(Entity):
    # ── Server-managed ────────────────────────────────────────────────
    order_number: str  # generated on creation (e.g. "ORD-2025-0042")
    created: datetime
    changed: datetime | None
    changes: list[str]

    # ── Core fields ───────────────────────────────────────────────────
    # OrderStatus: DRAFT | REQUESTED | PARTIALLY_ORDERED | ORDERED | PARTIALLY_DELIVERED |
    # DELIVERED | CANCELED
    status: OrderStatus
    note: str | None

    # ── Status-driven fields ──────────────────────────────────────────
    # `ordered_date` / `delivery_date` record when something actually
    # happened → full timestamps (UTC). `expected_delivery_date` is a
    # target the user picks in advance → stays a plain calendar date.
    ordered_date: datetime | None
    expected_delivery_date: date | None
    delivery_date: datetime | None
    storage_place: str | None

    # ── Relations (FK ids only) ───────────────────────────────────────
    creator_id: int
    supplier_id: int

    # ── Lifecycle intents ─────────────────────────────────────────────
    # When a price request went out and when the order was canceled, None
    # until then. Together with `ordered_date` they are the intents the
    # order's derived status reads (src/modules/fulfillment/domain/services/lifecycle/order.py).
    requested_at: datetime | None = None
    canceled_at: datetime | None = None
    # Moves on every user edit and irreversible action, never on a derived
    # status or date (domain/services/edit_version.py).
    edit_version: int = 0

    # ── Denormalized (read-only, populated by repository mapper) ──────
    creator: User | None = None
    changed_by_id: int | None = None
    changed_by: User | None = None
    supplier_name: str = ""
    supplier_vat_id: str = ""
    # Whether the supplier was archived; an order may still name one, the
    # pages only warn about it.
    supplier_archived: bool = False
    # Shipping, packaging, surcharges and the like, in position order;
    # written as a whole through the order repository.
    extra_costs: list[OrderExtraCost] = field(default_factory=list)
    # The quote requests the order's lines were awarded from, in request
    # order; read through the lines' links, never stored on the order.
    quote_requests: list[OrderQuoteRequestRef] = field(default_factory=list)
