"""
A quote request (RFQ): the lines purchasing asks several suppliers to quote
before anything is ordered, the suppliers asked, and each supplier's offer.

A line names what is asked for as an order line would: a bought or source
item with the demands it is for, a lot position worked by a supplier, or a
free-text item. A demand share is no allocation and covers nothing; only
the award turns a line into an order line and allocates the demands then.
An awarded line records which supplier won it at which price; the order line
the award created points back at it (order_item.quote_request_line_id). The
line counts as awarded only while such an order line is live: once it is
canceled or removed, the award is void and the line is open again, keeping
the award fields as the record of what was awarded until a new award
overwrites them.

A substitution happens on two levels. A line can replace another line for
every supplier: the replaced line is dropped and names its replacement, which
carries its demand shares and the reason, if given. And a single supplier can
offer an alternative item for a line in its quote, with an optional reason;
the award then puts
that item on the order line. Either way the order path records the
substitution against each demand, as it does for any order line whose item
differs from the demand's.

A supplier row holds when the request went out to that supplier and when it
answered, its offer per line (Quote) and the extra costs of its offer
(QuoteExtraCost), which carry over to the order at the award.
"""

from dataclasses import dataclass
from dataclasses import field
from datetime import date
from datetime import datetime

from src.modules.fulfillment.domain.value_objects.extra_cost_kind import ExtraCostKind
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.quote_request_status import (
    QuoteRequestDemandFamily,
)
from src.modules.fulfillment.domain.value_objects.quote_request_status import QuoteRequestLineState
from src.modules.fulfillment.domain.value_objects.quote_request_status import QuoteRequestStatus
from src.modules.platform.domain.entities.user import User
from src.shared_kernel.domain.entities.base import Entity


@dataclass(kw_only=True)
class QuoteRequestLineDemand:
    """The share of a line one bought or source item demand is for."""

    id: int
    line_id: int
    family: QuoteRequestDemandFamily
    demand_item_id: int
    quantity: float


@dataclass(kw_only=True)
class QuoteRequestLine(Entity):
    quote_request_id: int
    position: int  # display order within the request, starts at 1
    line_type: OrderLineType  # BOUGHT | SOURCE | MADE | VIRTUAL
    quantity: float
    unit: str
    created: datetime
    project_id: int | None = None
    bought_item_id: int | None = None
    source_item_id: int | None = None
    lot_position_id: int | None = None
    virtual_name: str | None = None
    note: str | None = None
    # Why the line asks for another item than its demands do, set on a line
    # that replaced another one.
    substitute_reason: str | None = None

    # ── Intents ───────────────────────────────────────────────────────
    # The supplier row that won the line and its unit price in cents, set
    # together by an award; dropped_at when nobody gets the line.
    awarded_supplier_id: int | None = None
    awarded_price: int | None = None
    awarded_at: datetime | None = None
    awarded_by_id: int | None = None
    dropped_at: datetime | None = None
    # The line that replaced this one; a replaced line is always dropped.
    substituted_by_line_id: int | None = None

    demands: list[QuoteRequestLineDemand] = field(default_factory=list)

    # ── Denormalized (read-only, populated by repository mapper) ──────
    item_name: str = ""
    item_code: str = ""
    project_number: str = ""
    lot_id: int | None = None
    lot_number: str = ""
    # The order line the award created, found through its back-link.
    order_item_id: int | None = None
    order_id: int | None = None
    order_number: str = ""
    # Whether an order line the award created is still live, that is not
    # canceled. A line built in code has no order lines to look at and
    # keeps the award it records.
    award_live: bool = True

    @property
    def state(self) -> QuoteRequestLineState:
        if self.awarded_at is not None and self.award_live:
            return QuoteRequestLineState.AWARDED
        if self.dropped_at is not None:
            return QuoteRequestLineState.DROPPED
        return QuoteRequestLineState.OPEN

    @property
    def award_voided(self) -> bool:
        """Whether the line was awarded and the order line of that award was
        canceled or removed since, which made the line open again."""
        return self.awarded_at is not None and not self.award_live


@dataclass(kw_only=True)
class Quote:
    """A supplier's offer for one line: a unit price in net cents, or no
    offer at all, with an optional lead time and minimum quantity. A quote
    for an alternative item names it, of the line's own kind, with the
    reason the supplier gave, if any."""

    id: int
    supplier_row_id: int
    line_id: int
    unit_price: int | None = None
    no_offer: bool = False
    lead_time_days: int | None = None
    min_quantity: float | None = None
    note: str | None = None
    substitute_bought_item_id: int | None = None
    substitute_source_item_id: int | None = None
    substitute_reason: str | None = None

    # ── Denormalized (read-only, populated by repository mapper) ──────
    substitute_item_name: str = ""
    substitute_item_code: str = ""

    @property
    def is_alternative(self) -> bool:
        return self.substitute_bought_item_id is not None or (
            self.substitute_source_item_id is not None
        )


@dataclass(kw_only=True)
class QuoteExtraCost:
    """An extra cost of a supplier's offer, of the kinds an order takes.
    `line_id` names the request line it belongs to, None for the offer."""

    id: int
    supplier_row_id: int
    kind: ExtraCostKind
    amount: int  # net, in EUR cents, always positive; a discount is subtracted
    position: int
    label: str | None = None
    note: str | None = None
    line_id: int | None = None


@dataclass(kw_only=True)
class QuoteRequestSupplier(Entity):
    quote_request_id: int
    supplier_id: int
    position: int
    # When the request last went out to the supplier; a line created after
    # it has not been asked of that supplier yet.
    sent_at: datetime | None = None
    responded_at: datetime | None = None
    declined_at: datetime | None = None
    valid_until: date | None = None
    note: str | None = None
    quotes: list[Quote] = field(default_factory=list)
    extra_costs: list[QuoteExtraCost] = field(default_factory=list)

    # ── Denormalized (read-only, populated by repository mapper) ──────
    supplier_name: str = ""
    supplier_archived: bool = False

    def quote_for(self, line_id: int) -> Quote | None:
        return next((q for q in self.quotes if q.line_id == line_id), None)

    def asked_for(self, line: QuoteRequestLine) -> bool:
        """Whether the request that went out to the supplier included the
        line, that is it was sent after the line was added."""
        return self.sent_at is not None and self.sent_at >= line.created


@dataclass(kw_only=True)
class QuoteRequest(Entity):
    request_number: str  # generated on creation (e.g. "RFQ-26-00042")
    created: datetime
    changed: datetime | None
    changes: list[str]
    status: QuoteRequestStatus  # derived
    creator_id: int
    note: str | None = None
    deadline: date | None = None  # the date offers are due by

    # ── Intents ───────────────────────────────────────────────────────
    closed_at: datetime | None = None
    canceled_at: datetime | None = None
    # Moves on every user edit and irreversible action, never on the
    # derived status (domain/services/edit_version.py).
    edit_version: int = 0

    lines: list[QuoteRequestLine] = field(default_factory=list)
    suppliers: list[QuoteRequestSupplier] = field(default_factory=list)

    # ── Denormalized (read-only, populated by repository mapper) ──────
    creator: User | None = None
    changed_by_id: int | None = None
    changed_by: User | None = None

    def line(self, line_id: int) -> QuoteRequestLine | None:
        return next((line for line in self.lines if line.id == line_id), None)

    def supplier_row(self, row_id: int) -> QuoteRequestSupplier | None:
        return next((row for row in self.suppliers if row.id == row_id), None)
