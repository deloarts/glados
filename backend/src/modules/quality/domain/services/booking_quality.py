"""
The booking quality view: where the bookings of the production orders do
not yet carry what the planning features will read from them.

Three findings come from the bookings alone. An order that ran through
hours without working time was probably left running, so its booked work
overstates what it took. A final completion without an assessment leaves
the order without the operator's own minutes. A manual pause without a
cause cannot be counted by cause. Lot holds have no cause by design and are
never counted, and pauses booked before the planning settings'
booking_quality_since are left out, since no cause could be picked then.

The findings tell the planners how far the bookings can be trusted, long
before anything is learned from them.
"""

from collections.abc import Callable
from collections.abc import Iterable
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from src.modules.fulfillment.domain.policies.booked_work import BookedOrder
from src.modules.fulfillment.domain.policies.booked_work import Window
from src.modules.fulfillment.domain.policies.booked_work import WorkSpan
from src.modules.fulfillment.domain.policies.booked_work import clip_to_windows
from src.modules.fulfillment.domain.policies.booked_work import derive_work_spans
from src.shared_kernel.domain.services.clock import as_utc

# Booked work outside working time below this many minutes is a late
# booking at the end of a shift, not an order left running.
OUTSIDE_WORKING_TIME_TOLERANCE_MINUTES = 30


@dataclass(frozen=True)
class BookingQualityOrder:
    """One production order with bookings in the period."""

    order_id: int
    production_order_number: str
    lot_id: int
    lot_number: str
    machine_id: int | None
    completed: bool
    has_assessment: bool
    booked: BookedOrder


@dataclass(frozen=True)
class OutsideWorkingTimeFinding:
    order_id: int
    production_order_number: str
    lot_id: int
    lot_number: str
    machine_id: int | None
    booked_minutes: int
    outside_minutes: int


@dataclass(frozen=True)
class MissingAssessmentFinding:
    order_id: int
    production_order_number: str
    lot_id: int
    lot_number: str
    machine_id: int | None
    completed_at: datetime


@dataclass(frozen=True)
class UncausedPause:
    """One manual pause booked without a cause."""

    order_id: int
    production_order_number: str
    lot_id: int
    lot_number: str
    machine_id: int | None
    paused_at: datetime
    operator_id: int | None


@dataclass(frozen=True)
class BookingQuality:
    orders_with_bookings: int
    outside_working_time: tuple[OutsideWorkingTimeFinding, ...]
    final_completions: int
    missing_assessments: tuple[MissingAssessmentFinding, ...]
    manual_pauses: int
    uncaused_pauses: tuple[UncausedPause, ...]


def compute_booking_quality(
    orders: Iterable[BookingQualityOrder],
    manual_pauses: Iterable[UncausedPause | None],
    *,
    period_start: datetime,
    period_end: datetime,
    now: datetime,
    windows_for: Callable[[int | None, datetime, datetime], Sequence[Window]],
) -> BookingQuality:
    """The findings for the period [period_start, period_end). `manual_pauses`
    holds one entry per manual pause in the period, None for one with a
    cause. `windows_for(machine_id, start, end)` gives the working windows
    of the order's machine, or of the default calendar for an order without
    one, between start and end."""
    orders = list(orders)
    pauses = list(manual_pauses)
    outside: list[OutsideWorkingTimeFinding] = []
    missing: list[MissingAssessmentFinding] = []
    final_completions = 0
    for order in orders:
        spans = _within(derive_work_spans(order.booked, until=now), period_start, period_end)
        if spans:
            clipped = clip_to_windows(
                spans, windows_for(order.machine_id, spans[0].start, spans[-1].end)
            )
            if clipped.outside_minutes >= OUTSIDE_WORKING_TIME_TOLERANCE_MINUTES:
                outside.append(
                    OutsideWorkingTimeFinding(
                        order_id=order.order_id,
                        production_order_number=order.production_order_number,
                        lot_id=order.lot_id,
                        lot_number=order.lot_number,
                        machine_id=order.machine_id,
                        booked_minutes=round(sum(s.minutes for s in spans)),
                        outside_minutes=round(clipped.outside_minutes),
                    )
                )
        completed_at = order.booked.actual_end
        if (
            order.completed
            and completed_at is not None
            and (period_start <= as_utc(completed_at) < period_end)
        ):
            final_completions += 1
            if not order.has_assessment:
                missing.append(
                    MissingAssessmentFinding(
                        order_id=order.order_id,
                        production_order_number=order.production_order_number,
                        lot_id=order.lot_id,
                        lot_number=order.lot_number,
                        machine_id=order.machine_id,
                        completed_at=completed_at,
                    )
                )
    return BookingQuality(
        orders_with_bookings=len(orders),
        outside_working_time=tuple(sorted(outside, key=lambda f: -f.outside_minutes)),
        final_completions=final_completions,
        missing_assessments=tuple(sorted(missing, key=lambda f: as_utc(f.completed_at))),
        manual_pauses=len(pauses),
        uncaused_pauses=tuple(
            sorted((p for p in pauses if p is not None), key=lambda p: as_utc(p.paused_at))
        ),
    )


def _within(spans: Iterable[WorkSpan], start: datetime, end: datetime) -> list[WorkSpan]:
    """The parts of `spans` inside [start, end)."""
    result = []
    for span in spans:
        piece_start, piece_end = max(span.start, start), min(span.end, end)
        if piece_end > piece_start:
            result.append(WorkSpan(piece_start, piece_end, span.operator_id))
    return result
