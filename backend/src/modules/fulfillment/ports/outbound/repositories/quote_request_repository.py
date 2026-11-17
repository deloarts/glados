"""
Repository interface of the quote request (RFQ) aggregate: the request with
its lines, demand shares, suppliers, offers and offer extra costs, read as a
whole, and the writes of each part.
"""

from dataclasses import dataclass
from dataclasses import field
from typing import Protocol
from typing import runtime_checkable

from src.modules.fulfillment.domain.entities.quote_request import Quote
from src.modules.fulfillment.domain.entities.quote_request import QuoteExtraCost
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequest
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequestLine
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequestSupplier


@dataclass
class QuoteRequestFilterDto:
    skip: int | None = None
    limit: int | None = None
    ids: list[int] | None = None
    status: list[str] | None = None
    supplier_id: int | None = None
    creator_id: int | None = None
    search: str | None = None
    order_by: str | None = None
    order_dir: str | None = None


@dataclass(frozen=True)
class OpenQuoteRequestRef:
    """A quote request still asking for something, as a marker shows it."""

    id: int
    request_number: str


@dataclass
class OpenQuoteRequestLinks:
    """The open quote requests whose open lines name each demand or lot
    position, keyed by its id."""

    bought_demands: dict[int, list[OpenQuoteRequestRef]] = field(default_factory=dict)
    source_demands: dict[int, list[OpenQuoteRequestRef]] = field(default_factory=dict)
    lot_positions: dict[int, list[OpenQuoteRequestRef]] = field(default_factory=dict)


@runtime_checkable
class IQuoteRequestRepository(Protocol):
    async def get_by_id(self, id: int) -> QuoteRequest | None: ...

    async def get_by_id_for_update(self, id: int) -> QuoteRequest | None:
        """Same as get_by_id but locks the request row until the transaction
        ends (Postgres only) and re-reads the aggregate. A writer that locks
        nothing else takes it first; one that also takes lifecycle locks
        takes it last, through the lock plan (lifecycle_lock_plan.py)."""
        ...

    async def get_by_ids(self, ids: list[int], *, refresh: bool = False) -> list[QuoteRequest]:
        """The requests with their lines, for the lifecycle reconciler. With
        refresh, rows the session holds are read again."""
        ...

    async def lock_for_update(self, ids: list[int]) -> None:
        """Locks the request rows in ascending id order (Postgres only)."""
        ...

    async def get_ids_after(self, after_id: int, limit: int) -> list[int]:
        """Up to `limit` request ids above `after_id`, ascending, for the
        lifecycle drift report."""
        ...

    async def get_multi(self, filters: QuoteRequestFilterDto) -> tuple[int, list[QuoteRequest]]: ...

    async def save(self, request: QuoteRequest) -> QuoteRequest:
        """Writes the request's own fields, not its lines or suppliers."""
        ...

    async def save_line(self, line: QuoteRequestLine) -> QuoteRequestLine:
        """Writes the line and makes its demand shares the given ones."""
        ...

    async def delete_line(self, line_id: int) -> None: ...

    async def save_supplier(self, row: QuoteRequestSupplier) -> QuoteRequestSupplier:
        """Writes the supplier row's own fields, not its offer."""
        ...

    async def delete_supplier(self, row_id: int) -> None: ...

    async def set_offer(
        self, row_id: int, quotes: list[Quote], extra_costs: list[QuoteExtraCost]
    ) -> None:
        """Makes `quotes` and `extra_costs` the supplier row's offer."""
        ...

    async def next_request_number(self, template: str) -> str: ...

    async def get_open_links(
        self,
        *,
        bought_demand_ids: list[int],
        source_demand_ids: list[int],
        lot_position_ids: list[int],
    ) -> OpenQuoteRequestLinks: ...
