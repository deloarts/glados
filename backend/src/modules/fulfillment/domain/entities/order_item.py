"""A single line item within an Order.

Which catalogue a line points at depends on its line_type:
  BOUGHT  → bought_item_id (BoughtItem)
  SOURCE    → source_item_id (SourceItem)
  MADE    → reached indirectly: lot_position → lot → made_item
  VIRTUAL → no catalogue entry at all; the name lives in virtual_name

Status: PENDING | REQUESTED | ORDERED | PARTIALLY_DELIVERED | DELIVERED | CANCELED
"""

from dataclasses import dataclass
from datetime import date
from datetime import datetime

from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.platform.domain.entities.user import User
from src.modules.workspace.domain.value_objects.project_status import ProjectStatus
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class OrderItem(Entity):
    # ── Server-managed ────────────────────────────────────────────────
    created: datetime
    changed: datetime | None
    changes: list[str]

    # ── Core fields ───────────────────────────────────────────────────
    # OrderItemStatus: PENDING | REQUESTED | ORDERED | PARTIALLY_DELIVERED | DELIVERED | CANCELED
    status: OrderItemStatus
    quantity: float
    quantity_delivered: float
    unit: str
    items_per_unit: float
    price: int | None  # net unit price in EUR cents
    note: str | None

    # ── Status-driven fields ──────────────────────────────────────────
    # `ordered_date` / `delivery_date` record when something actually
    # happened → full timestamps (UTC). `expected_delivery_date` is a
    # target the user picks in advance → stays a plain calendar date.
    ordered_date: datetime | None
    expected_delivery_date: date | None
    delivery_date: datetime | None
    storage_place: str | None

    # ── Pickup tracking, which feeds the scheduler for MADE and SOURCE lines ──
    expected_pickup_date: date | None  # supplier's estimate of ready-to-collect (target → date)
    ready_for_pickup_date: datetime | None  # supplier confirmed readiness (event → timestamp)

    # ── Position within the order ─────────────────────────────────────
    position: int  # display order within the parent order, starts at 1

    # ── Relations (FK ids only) ───────────────────────────────────────
    creator_id: int
    orderer_id: int | None
    receiver_id: int | None
    bought_item_id: int | None  # → BoughtItem (catalogue entry); None for MADE/SOURCE/VIRTUAL lines
    order_id: int  # → Order
    supplier_id: int
    project_id: int  # → Project
    line_type: OrderLineType  # BOUGHT | MADE | SOURCE | VIRTUAL
    lot_position_id: int | None  # → LotPosition (MADE-line linkage)
    # → SourceItem for a SOURCE line, independent of its demand allocations.
    source_item_id: int | None

    # ── Virtual item fields ───────────────────────────────────────────
    # Set only on VIRTUAL lines; every other line takes its name from the
    # catalogue row, so renames propagate.
    virtual_name: str | None = None
    # The quote request line an award created this line from, if any.
    quote_request_line_id: int | None = None

    # Rejected pieces from deliveries; quantity_delivered counts accepted
    # ones only. A line is DELIVERED once delivered plus lost reaches its
    # quantity.
    quantity_rejected: float = 0.0
    quantity_rejected_lost: float = 0.0

    # ── Lifecycle intents ─────────────────────────────────────────────
    # When the line was requested and when it was canceled, None until
    # then. Together with `ordered_date` they are the intents the line's
    # derived status reads (src/modules/fulfillment/domain/services/lifecycle/order_item.py).
    requested_at: datetime | None = None
    canceled_at: datetime | None = None
    # Moves on every user edit and irreversible action, never on a derived
    # status or date (domain/services/edit_version.py).
    edit_version: int = 0
    # When the line was closed short, nothing more to come from the
    # supplier, and the quantity it had before, which reopening it brings
    # back; None while it is not closed short.
    closed_short_at: datetime | None = None
    closed_short_from: float | None = None

    # ── Denormalized (read-only, populated by repository mapper) ──────
    creator: User | None = None
    changed_by_id: int | None = None
    changed_by: User | None = None
    orderer: User | None = None
    receiver: User | None = None
    item_order_code_1: str = ""
    item_order_code_2: str | None = None
    # "material | type" for a SOURCE line without an order code.
    item_specification: str = ""
    item_article_name: str = ""
    item_part_number: str | None = None
    # Descriptors from the live catalogue row, None where a line type has
    # no such concept.
    item_material: str | None = None  # MADE (made_item.material) | SOURCE (source_item.material)
    item_dimension: str | None = None  # SOURCE only
    item_type_name: str | None = None  # SOURCE only (source_item.type.name)
    item_revision: str | None = None  # MADE only
    item_base_size: str | None = None  # MADE only
    item_mass: int | None = None  # in grams; BOUGHT | MADE | SOURCE
    item_manufacturer: str | None = None  # BOUGHT | SOURCE (SourceItem's is nullable)
    made_item_id: int | None = None
    supplier_name: str = ""
    supplier_external_lead_time_days: int | None = None
    project_number: str = ""
    product_number: str | None = None
    project_customer: str = ""
    project_description: str = ""
    project_status: ProjectStatus = ProjectStatus.ARCHIVED  # of the owning project
    lot_id: int | None = None
    lot_number: str = ""
    fabrication_method: str = ""
    # The quote request behind quote_request_line_id.
    quote_request_id: int | None = None
    quote_request_number: str = ""

    @property
    def quantity_settled(self) -> float:
        """Pieces the line is done with, delivered or lost to rejection."""
        return self.quantity_delivered + self.quantity_rejected_lost

    @property
    def allocatable_quantity(self) -> float:
        """What the allocations on the line may sum to: its quantity, or the
        pieces it settled where a delivery within the over-delivery tolerance
        went beyond that, less the pieces lost at receipt, which never
        arrive. Never below zero."""
        return max(max(self.quantity, self.quantity_settled) - self.quantity_rejected_lost, 0.0)
