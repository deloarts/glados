"""
Rules of a quote request (RFQ): who may act on one, when it may change, what
its lines and demand shares must satisfy, how offers compare and which lines
an award gives to which supplier.

Every action needs write:orders, the permission an award needs anyway to
create orders. Lines, suppliers and offers change while the request is DRAFT
or SENT; the request's own actions are checked against its intent table
(lifecycle/quote_request.py). A demand share is no allocation: shares
together stay within the line, and a share names a demand of the line's
item, but nothing reserves the demand until the award allocates it.

A bought or source line can take another item of its own kind: for every
supplier by replacing the line, or for one supplier through an alternative
in its quote, each with an optional reason. An alternative competes with
the other offers for the line like any quote.

Offers compare per line by unit price, and per supplier by the total of the
lines it quoted plus its extra costs. The cheapest choice per line and the
cheapest choice overall can name different suppliers, so both are reported.
"""

from collections.abc import Iterable
from collections.abc import Mapping
from dataclasses import dataclass

from src.modules.fulfillment.domain.entities.quote_request import QuoteRequest
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequestLine
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequestSupplier
from src.modules.fulfillment.domain.errors import QuoteRequestActionRefusedError
from src.modules.fulfillment.domain.errors import QuoteRequestInvalidError
from src.modules.fulfillment.domain.errors import QuoteRequestLineNotFoundError
from src.modules.fulfillment.domain.errors import QuoteRequestLineNotOpenError
from src.modules.fulfillment.domain.errors import QuoteRequestNotOpenError
from src.modules.fulfillment.domain.errors import QuoteRequestSupplierNotFoundError
from src.modules.fulfillment.domain.services.extra_cost_rules import extra_costs_total
from src.modules.fulfillment.domain.services.lifecycle.quote_request import QUOTE_REQUEST_INTENTS
from src.modules.fulfillment.domain.services.lifecycle.quote_request import is_quote_request_open
from src.modules.fulfillment.domain.services.lifecycle.quote_request import quote_request_context
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.quote_request_status import (
    QuoteRequestDemandFamily,
)
from src.modules.fulfillment.domain.value_objects.quote_request_status import QuoteRequestLineState
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.crud_permission_rules import assert_has_permission
from src.modules.platform.domain.services.quantities import quantity_gt
from src.modules.platform.domain.value_objects.permission import Permission
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction

_VERBS = {
    LifecycleAction.SEND: "send",
    LifecycleAction.AWARD: "award",
    LifecycleAction.CLOSE: "close",
    LifecycleAction.CANCEL: "cancel",
    LifecycleAction.REOPEN: "reopen",
}


def assert_can_write_quote_requests(actor: User) -> None:
    assert_has_permission(actor, Permission.WRITE_ORDERS, "change", "quote requests")


def assert_quote_request_open(request: QuoteRequest) -> None:
    """Refuses a change to a request that was awarded, closed or canceled."""
    if not is_quote_request_open(request.status):
        raise QuoteRequestNotOpenError(
            f"Quote request {request.request_number} is {request.status.value} and takes no change."
        )


def assert_quote_request_action(
    action: LifecycleAction, request: QuoteRequest, actor: User
) -> None:
    """Refuses an action the request's state does not allow now."""
    assert_can_write_quote_requests(actor)
    refusal = QUOTE_REQUEST_INTENTS.check(action, request, quote_request_context(request), actor)
    if refusal is None:
        return
    raise QuoteRequestActionRefusedError(
        refusal.message(
            f"Quote request {request.request_number}",
            request.status.value,
            _VERBS.get(action, "act"),
        )
    )


def allowed_quote_request_actions(request: QuoteRequest, actor: User) -> list[str]:
    """The actions the actor may take on the request now, for the client."""
    if not actor.has_permission(Permission.WRITE_ORDERS):
        return []
    return [
        action.value
        for action in QUOTE_REQUEST_INTENTS.allowed_actions(
            request, quote_request_context(request), actor
        )
    ]


def find_line(request: QuoteRequest, line_id: int) -> QuoteRequestLine:
    line = request.line(line_id)
    if line is None:
        raise QuoteRequestLineNotFoundError(
            f"Line #{line_id} is not on quote request {request.request_number}."
        )
    return line


def find_supplier_row(request: QuoteRequest, row_id: int) -> QuoteRequestSupplier:
    row = request.supplier_row(row_id)
    if row is None:
        raise QuoteRequestSupplierNotFoundError(
            f"Supplier entry #{row_id} is not on quote request {request.request_number}."
        )
    return row


def assert_line_open(line: QuoteRequestLine) -> None:
    if line.state is not QuoteRequestLineState.OPEN:
        raise QuoteRequestLineNotOpenError(
            f"Line #{line.id} is {line.state.value} and takes no change."
        )


def assert_shares_fit(line_quantity: float, shares: Iterable[float]) -> None:
    """Refuses a share that is not positive and shares beyond the line."""
    amounts = list(shares)
    if any(not quantity_gt(amount, 0.0) for amount in amounts):
        raise QuoteRequestInvalidError("A demand share needs a quantity above zero.")
    if quantity_gt(sum(amounts), line_quantity):
        raise QuoteRequestInvalidError("The demand shares exceed the line's quantity.")


# ── Substitution ─────────────────────────────────────────────────────────


def assert_line_substitutable(line: QuoteRequestLine) -> None:
    """Refuses another item for a line that cannot take one: a MADE line
    asks for a lot position and a free-text line names no item, and a bought
    line with a share of a source item demand stays on its item, since such
    a demand is sourced from that bought item and takes no substitute."""
    if line.line_type not in (OrderLineType.BOUGHT, OrderLineType.SOURCE):
        raise QuoteRequestInvalidError(
            f"Line {line.position} names no catalogue item, so it takes no substitute."
        )
    if line.line_type == OrderLineType.BOUGHT and any(
        d.family == QuoteRequestDemandFamily.SOURCE for d in line.demands
    ):
        raise QuoteRequestInvalidError(
            f"Line {line.position} is for a source item demand sourced from this item, "
            "so it takes no substitute."
        )


def substitute_of_line_kind(
    line: QuoteRequestLine, bought_item_id: int | None, source_item_id: int | None
) -> int:
    """The substitute item named for the line: exactly one item, a bought
    item for a bought line and a source item for a source line."""
    if (bought_item_id is None) == (source_item_id is None):
        raise QuoteRequestInvalidError("A substitute names exactly one item.")
    if line.line_type == OrderLineType.BOUGHT and bought_item_id is not None:
        return bought_item_id
    if line.line_type == OrderLineType.SOURCE and source_item_id is not None:
        return source_item_id
    raise QuoteRequestInvalidError(
        f"Line {line.position} takes a substitute of its own kind only, "
        f"a {'bought' if line.line_type == OrderLineType.BOUGHT else 'source'} item."
    )


def line_item_id(line: QuoteRequestLine) -> int | None:
    """The catalogue item a bought or source line asks for."""
    return line.bought_item_id if line.line_type == OrderLineType.BOUGHT else (line.source_item_id)


def substitute_reason(reason: str | None) -> str | None:
    """The reason of a substitution as stored, None when none is given."""
    return (reason or "").strip() or None


# ── Comparison ───────────────────────────────────────────────────────────


@dataclass(frozen=True, kw_only=True)
class SupplierOfferTotals:
    """A supplier's offer in net cents: the lines it priced, times the line
    quantities, plus its extra costs with a discount subtracted, and how many
    of the request's live lines it priced."""

    lines_total: int
    extra_costs_total: int
    priced_lines: int

    @property
    def total(self) -> int:
        return self.lines_total + self.extra_costs_total


def _live_lines(request: QuoteRequest) -> list[QuoteRequestLine]:
    return [line for line in request.lines if line.state is not QuoteRequestLineState.DROPPED]


def offer_totals(request: QuoteRequest, row: QuoteRequestSupplier) -> SupplierOfferTotals:
    priced = 0
    total = 0.0
    for line in _live_lines(request):
        quote = row.quote_for(line.id)
        if quote is None or quote.no_offer or quote.unit_price is None:
            continue
        priced += 1
        total += quote.unit_price * line.quantity
    return SupplierOfferTotals(
        lines_total=round(total),
        extra_costs_total=extra_costs_total((c.kind, c.amount) for c in row.extra_costs),
        priced_lines=priced,
    )


def cheapest_per_line(request: QuoteRequest) -> dict[int, int]:
    """The supplier row with the lowest unit price per live line that has a
    priced offer, the earlier row on a tie."""
    best: dict[int, tuple[int, int]] = {}
    for row in request.suppliers:
        for quote in row.quotes:
            if quote.no_offer or quote.unit_price is None:
                continue
            current = best.get(quote.line_id)
            if current is None or quote.unit_price < current[0]:
                best[quote.line_id] = (quote.unit_price, row.id)
    live = {line.id for line in _live_lines(request)}
    return {line_id: row_id for line_id, (_, row_id) in best.items() if line_id in live}


def cheapest_complete_offer(request: QuoteRequest) -> int | None:
    """The supplier row whose offer prices every live line at the lowest
    total, extra costs included; None when no supplier priced them all."""
    lines = len(_live_lines(request))
    if lines == 0:
        return None
    complete = [
        (offer_totals(request, row).total, index, row.id)
        for index, row in enumerate(request.suppliers)
        if offer_totals(request, row).priced_lines == lines
    ]
    return min(complete)[2] if complete else None


# ── Award ────────────────────────────────────────────────────────────────


@dataclass(frozen=True, kw_only=True)
class AwardedLine:
    """A line as an award places it: the item goes onto the order line, the
    supplier's alternative when it quoted one, and the reason travels with
    it so the order path can record the substitution."""

    line: QuoteRequestLine
    unit_price: int | None
    lead_time_days: int | None
    bought_item_id: int | None = None
    source_item_id: int | None = None
    substitute_reason: str | None = None


def plan_award(request: QuoteRequest, awards: Mapping[int, int]) -> dict[int, list[AwardedLine]]:
    """The lines each supplier row wins, keyed by row id in the request's
    supplier order, from `awards` (line id to supplier row id). Every line
    must be open and every row on the request; a row that declined the line
    cannot win it, one that sent no offer for it wins it without a price.
    A row that quoted an alternative wins the line with that item."""
    if not awards:
        raise QuoteRequestInvalidError("An award names at least one line.")
    planned: dict[int, list[AwardedLine]] = {}
    for line_id, row_id in awards.items():
        line = find_line(request, line_id)
        assert_line_open(line)
        row = find_supplier_row(request, row_id)
        quote = row.quote_for(line.id)
        if quote is not None and quote.no_offer:
            raise QuoteRequestInvalidError(
                f"{row.supplier_name or f'Supplier #{row.supplier_id}'} made no offer for "
                f"line #{line.id}, so it cannot win it."
            )
        alternative = quote is not None and quote.is_alternative
        planned.setdefault(row.id, []).append(
            AwardedLine(
                line=line,
                unit_price=quote.unit_price if quote is not None else None,
                lead_time_days=quote.lead_time_days if quote is not None else None,
                bought_item_id=(
                    quote.substitute_bought_item_id
                    if quote is not None and alternative
                    else line.bought_item_id
                ),
                source_item_id=(
                    quote.substitute_source_item_id
                    if quote is not None and alternative
                    else line.source_item_id
                ),
                substitute_reason=(
                    quote.substitute_reason
                    if quote is not None and alternative
                    else line.substitute_reason
                ),
            )
        )
    order = {row.id: index for index, row in enumerate(request.suppliers)}
    return {
        row_id: sorted(lines, key=lambda a: a.line.position)
        for row_id, lines in sorted(planned.items(), key=lambda item: order[item[0]])
    }
