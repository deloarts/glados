"""Status of a quote request, derived from its own intents and line states,
and the actions it accepts.

Nothing a quote request does changes an order line or a demand until an
award. A line's state reads one fact outside the request: an awarded line
stays AWARDED only while an order line its award created is live, and is
open again once that line is canceled or removed. The lifecycle reconciler
therefore derives and stores the request's status, the last aggregate in
the lock order, whenever an order line that points back at it changes.

Someone canceling the request or closing it decides; otherwise a request
whose every line is awarded or dropped, one of them awarded, is AWARDED,
one whose every line was dropped is CLOSED, one that went out to a supplier
is SENT, and any other is DRAFT. A request CLOSED that way, with no close
recorded, takes a dropped line back (lines_restorable), since nothing but
the dropped lines closed it.

Lines, suppliers and offers are edited while the request is DRAFT or SENT.
An award takes open lines of such a request, a close drops the lines still
open once one line was awarded, and a cancel ends a request that awarded
nothing. A closed request stays closed when an award on it is voided; the
void opens that line again, and a reopen clears the close so the line can
be awarded anew, with the status derived again from the lines.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from src.modules.fulfillment.domain.entities.quote_request import QuoteRequest
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequestLine
from src.modules.fulfillment.domain.services.lifecycle.rules import Derivation
from src.modules.fulfillment.domain.services.lifecycle.rules import DerivationTable
from src.modules.fulfillment.domain.services.lifecycle.rules import otherwise
from src.modules.fulfillment.domain.services.lifecycle.rules import rule
from src.modules.fulfillment.domain.value_objects.quote_request_status import QuoteRequestLineState
from src.modules.fulfillment.domain.value_objects.quote_request_status import QuoteRequestStatus
from src.modules.platform.domain.services.intent_table import Check
from src.modules.platform.domain.services.intent_table import HasStatus
from src.modules.platform.domain.services.intent_table import IntentRule
from src.modules.platform.domain.services.intent_table import IntentTable
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction

_OPEN_STATUSES = (QuoteRequestStatus.DRAFT, QuoteRequestStatus.SENT)


@dataclass(frozen=True, kw_only=True)
class QuoteRequestFacts:
    canceled_at: datetime | None
    closed_at: datetime | None
    sent: bool  # whether a supplier was sent the request
    line_states: tuple[QuoteRequestLineState, ...]


def quote_request_facts(request: QuoteRequest) -> QuoteRequestFacts:
    return QuoteRequestFacts(
        canceled_at=request.canceled_at,
        closed_at=request.closed_at,
        sent=any(row.sent_at is not None for row in request.suppliers),
        line_states=tuple(line.state for line in request.lines),
    )


def _all_decided_one_awarded(facts: QuoteRequestFacts) -> bool:
    states = facts.line_states
    return (
        bool(states)
        and QuoteRequestLineState.OPEN not in states
        and QuoteRequestLineState.AWARDED in states
    )


def _all_dropped(facts: QuoteRequestFacts) -> bool:
    states = facts.line_states
    return bool(states) and all(s == QuoteRequestLineState.DROPPED for s in states)


QUOTE_REQUEST_STATUS = DerivationTable[QuoteRequestFacts, QuoteRequestStatus](
    key="quote_request_status",
    rules=(
        rule(
            1, "canceled_at set", QuoteRequestStatus.CANCELED, lambda f: f.canceled_at is not None
        ),
        rule(2, "closed_at set", QuoteRequestStatus.CLOSED, lambda f: f.closed_at is not None),
        rule(
            3,
            "every line awarded or dropped, at least one awarded",
            QuoteRequestStatus.AWARDED,
            _all_decided_one_awarded,
        ),
        rule(4, "every line dropped", QuoteRequestStatus.CLOSED, _all_dropped),
        rule(5, "sent to a supplier", QuoteRequestStatus.SENT, lambda f: f.sent),
    ),
    fallback=otherwise(6, QuoteRequestStatus.DRAFT),
)


def derive_quote_request_status(facts: QuoteRequestFacts) -> Derivation[QuoteRequestStatus]:
    return QUOTE_REQUEST_STATUS.derive(facts)


def is_quote_request_open(status: str) -> bool:
    """Whether lines, suppliers and offers of the request may change."""
    return status in _OPEN_STATUSES


def lines_restorable(request: QuoteRequest) -> bool:
    """Whether a dropped line may be taken back: while the request is open,
    and while it is CLOSED or AWARDED only because every line was decided,
    which a taken back line undoes, so the request reads sent or draft
    again. A recorded close holds until the request is reopened."""
    if is_quote_request_open(request.status):
        return True
    return (
        request.status in (QuoteRequestStatus.CLOSED, QuoteRequestStatus.AWARDED)
        and request.closed_at is None
        and request.canceled_at is None
    )


def award_voided_note(request: QuoteRequest, line: QuoteRequestLine) -> str:
    """The changelog text for an award of `line` voided by the cancel or
    removal of the order line it created."""
    row = (
        request.supplier_row(line.awarded_supplier_id)
        if line.awarded_supplier_id is not None
        else None
    )
    supplier = row.supplier_name if row is not None and row.supplier_name else "the supplier"
    if line.order_item_id is not None and line.order_number:
        cause = f"its line on order {line.order_number} was canceled"
    elif line.order_item_id is not None:
        cause = "its order line was canceled"
    else:
        cause = "its order line was removed"
    return f"Award of line {line.position} to {supplier} voided: {cause}."


# ── Actions ──────────────────────────────────────────────────────────────


@dataclass(frozen=True, kw_only=True)
class QuoteRequestContext:
    """What the actions read beside the status: the request's line states,
    whether it names a supplier, whether a close was recorded and whether
    a line is open again because its award was voided."""

    line_states: Sequence[QuoteRequestLineState]
    has_suppliers: bool
    closed: bool
    has_voided_line: bool


def has_voided_open_line(request: QuoteRequest) -> bool:
    """Whether a line of the request is open again because the order line
    of its award was canceled or removed. A voided line the user dropped
    since does not count."""
    return any(
        line.award_voided and line.state is QuoteRequestLineState.OPEN for line in request.lines
    )


def quote_request_context(request: QuoteRequest) -> QuoteRequestContext:
    return QuoteRequestContext(
        line_states=tuple(line.state for line in request.lines),
        has_suppliers=bool(request.suppliers),
        closed=request.closed_at is not None,
        has_voided_line=has_voided_open_line(request),
    )


def _has_line(_r: HasStatus, c: QuoteRequestContext) -> bool:
    return bool(c.line_states)


def _has_supplier(_r: HasStatus, c: QuoteRequestContext) -> bool:
    return c.has_suppliers


def _has_open_line(_r: HasStatus, c: QuoteRequestContext) -> bool:
    return QuoteRequestLineState.OPEN in c.line_states


def _has_awarded_line(_r: HasStatus, c: QuoteRequestContext) -> bool:
    return QuoteRequestLineState.AWARDED in c.line_states


def _has_no_awarded_line(r: HasStatus, c: QuoteRequestContext) -> bool:
    return not _has_awarded_line(r, c)


def _closed_by_someone(_r: HasStatus, c: QuoteRequestContext) -> bool:
    return c.closed


def _has_voided_line(_r: HasStatus, c: QuoteRequestContext) -> bool:
    return c.has_voided_line


QUOTE_REQUEST_INTENTS = IntentTable[HasStatus, QuoteRequestContext](
    key="quote_request",
    rules=(
        IntentRule(
            action=LifecycleAction.SEND,
            allowed_from=_OPEN_STATUSES,
            checks=(Check("a line", _has_line), Check("a supplier", _has_supplier)),
            effect="the request is recorded as sent to the supplier, who is then asked every line",
        ),
        IntentRule(
            action=LifecycleAction.AWARD,
            allowed_from=_OPEN_STATUSES,
            checks=(Check("an open line", _has_open_line),),
            effect="each chosen line goes onto a draft order of the supplier that won it",
        ),
        IntentRule(
            action=LifecycleAction.CLOSE,
            allowed_from=_OPEN_STATUSES,
            checks=(Check("an awarded line", _has_awarded_line),),
            effect="the lines still open are dropped and the request is closed",
        ),
        IntentRule(
            action=LifecycleAction.CANCEL,
            allowed_from=_OPEN_STATUSES,
            checks=(Check("no awarded line", _has_no_awarded_line),),
            effect="the request is canceled; its demands stay open",
        ),
        IntentRule(
            action=LifecycleAction.REOPEN,
            allowed_from=(QuoteRequestStatus.CLOSED,),
            checks=(
                Check("a recorded close", _closed_by_someone),
                Check("a line whose award was voided", _has_voided_line),
            ),
            effect=(
                "the close is cleared and the status derived again from the lines; "
                "the offers stay and the dropped lines stay dropped"
            ),
        ),
    ),
)
