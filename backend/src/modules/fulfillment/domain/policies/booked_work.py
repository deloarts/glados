"""
The spans of time a production order was actually worked on, derived from
its bookings alone: the first start, the pauses and how each ended, the
reversals of its completions and its end.

Work begins at `actual_start` under the operator of the first start. A pause
ends the running span. A pause that ended by a resume opens the next span,
under the operator who resumed when the order's own start resumed it and
under the previous operator when a lot resume did. A pause ended by a cancel
or a cut opens nothing, since no work follows it. A reversal of the
completion that completed the order sends it back to work without a start:
the span from that completion to the reversal is not work, and work goes on
at the reversal with an unknown operator. Reversing an earlier, partial
completion changes nothing. The last span ends at the order's end, its
cancel, or `until` while it is still running.

Rows booked before `ended_by` existed have none; a closed one counts as a
resume, which is what most of them were, and a cancel or a cut among them
ends the order at the same moment, so the span it would open is empty.

The spans are clipped to working time by `clip_to_windows`, which also
reports what it cut off, so a forgotten pause at the end of a shift does not
count a night as work.
"""

from collections.abc import Iterable
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from src.modules.fulfillment.domain.entities.production_order_completion import (
    ProductionOrderCompletion,
)
from src.modules.fulfillment.domain.entities.production_order_interruption import (
    ProductionOrderInterruption,
)
from src.modules.fulfillment.domain.value_objects.interruption_ended_by import InterruptionEndedBy
from src.modules.platform.domain.services.quantities import quantity_ge
from src.shared_kernel.domain.services.clock import as_utc

type Window = tuple[datetime, datetime]


@dataclass(frozen=True)
class BookedOrder:
    """What the derivation reads of one production order."""

    actual_start: datetime | None
    actual_end: datetime | None
    canceled_at: datetime | None
    quantity: float
    # The operator of the first start; None for orders started before it
    # was recorded.
    first_started_operator_id: int | None
    interruptions: Sequence[ProductionOrderInterruption]
    completions: Sequence[ProductionOrderCompletion]


@dataclass(frozen=True)
class WorkSpan:
    """One span of booked work. `operator_id` is None when the bookings do
    not say who worked it."""

    start: datetime
    end: datetime
    operator_id: int | None

    @property
    def minutes(self) -> float:
        return (self.end - self.start).total_seconds() / 60


@dataclass(frozen=True)
class ClippedSpans:
    """The spans inside working time and the minutes cut off outside it."""

    inside: tuple[WorkSpan, ...]
    outside_minutes: float


@dataclass(frozen=True)
class _Event:
    at: datetime
    # "stop" ends the running span, "go" opens the next one.
    action: Literal["stop", "go"]
    operator_id: int | None
    keep_operator: bool


def derive_work_spans(order: BookedOrder, until: datetime) -> list[WorkSpan]:
    """The order's booked work, oldest first, as described in the module
    docstring. Empty for an order that never started."""
    if order.actual_start is None:
        return []
    start = as_utc(order.actual_start)
    end = _end_of(order, as_utc(until))
    events = sorted(
        [*_pause_events(order.interruptions), *_reversal_events(order)],
        key=lambda e: (e.at, 0 if e.action == "stop" else 1),
    )

    spans: list[WorkSpan] = []
    open_since: datetime | None = start
    operator = order.first_started_operator_id
    for event in events:
        if event.at >= end:
            break
        if event.action == "stop":
            if open_since is not None:
                spans.append(WorkSpan(open_since, max(open_since, event.at), operator))
            open_since = None
            continue
        if open_since is None:
            open_since = max(event.at, start)
            if not event.keep_operator:
                operator = event.operator_id
    if open_since is not None:
        spans.append(WorkSpan(open_since, max(open_since, end), operator))
    return [span for span in spans if span.end > span.start]


def clip_to_windows(spans: Iterable[WorkSpan], windows: Sequence[Window]) -> ClippedSpans:
    """The parts of `spans` inside the working `windows` (UTC, sorted, not
    overlapping) and the minutes outside them."""
    inside: list[WorkSpan] = []
    outside = 0.0
    for span in spans:
        kept = 0.0
        for window_start, window_end in windows:
            if window_end <= span.start:
                continue
            if window_start >= span.end:
                break
            piece_start = max(span.start, window_start)
            piece_end = min(span.end, window_end)
            if piece_end > piece_start:
                piece = WorkSpan(piece_start, piece_end, span.operator_id)
                inside.append(piece)
                kept += piece.minutes
        outside += span.minutes - kept
    return ClippedSpans(inside=tuple(inside), outside_minutes=outside)


def _end_of(order: BookedOrder, until: datetime) -> datetime:
    if order.actual_end is not None:
        return as_utc(order.actual_end)
    if order.canceled_at is not None:
        return as_utc(order.canceled_at)
    return until


def _pause_events(interruptions: Iterable[ProductionOrderInterruption]) -> list[_Event]:
    events: list[_Event] = []
    for row in interruptions:
        events.append(_Event(as_utc(row.paused_at), "stop", None, keep_operator=True))
        if row.resumed_at is None or row.ended_by in (
            InterruptionEndedBy.CANCEL,
            InterruptionEndedBy.CUT,
        ):
            continue
        # The order's own resume names the operator; a lot resume and a row
        # from before the field existed do not, so the work goes on under
        # the operator of the last start or resume.
        events.append(
            _Event(
                as_utc(row.resumed_at),
                "go",
                row.resumed_operator_id,
                keep_operator=row.resumed_operator_id is None,
            )
        )
    return events


def _reversal_events(order: BookedOrder) -> list[_Event]:
    """A stop at every completion a reversal took back that had completed
    the order, and a go at the reversal."""
    by_id = {c.id: c for c in order.completions}
    events: list[_Event] = []
    for reversal in order.completions:
        target = by_id.get(reversal.reverses_completion_id or 0)
        if target is None or not _completed_the_order(target, order):
            continue
        events.append(_Event(as_utc(target.created), "stop", None, keep_operator=True))
        events.append(_Event(as_utc(reversal.created), "go", None, keep_operator=False))
    return events


def _completed_the_order(target: ProductionOrderCompletion, order: BookedOrder) -> bool:
    """Whether the accepted pieces booked up to and including `target`, net
    of the reversals booked before it, reached the order's quantity."""
    moment = as_utc(target.created)
    accepted = sum(
        c.quantity_accepted
        for c in order.completions
        if as_utc(c.created) <= moment and c.id != target.id
    )
    return quantity_ge(accepted + target.quantity_accepted, order.quantity)
