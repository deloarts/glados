"""
The booking quality findings (domain/services/booking_quality.py): orders
that ran through hours without working time, final completions without an
assessment, and manual pauses without a cause.
"""

from collections.abc import Sequence
from datetime import UTC
from datetime import datetime

from src.modules.fulfillment.domain.policies.booked_work import BookedOrder
from src.modules.quality.domain.services.booking_quality import BookingQuality
from src.modules.quality.domain.services.booking_quality import BookingQualityOrder
from src.modules.quality.domain.services.booking_quality import UncausedPause
from src.modules.quality.domain.services.booking_quality import compute_booking_quality

PERIOD_START = datetime(2026, 3, 2, tzinfo=UTC)
PERIOD_END = datetime(2026, 3, 9, tzinfo=UTC)
NOW = datetime(2026, 3, 6, 12, tzinfo=UTC)


def _at(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 3, day, hour, minute, tzinfo=UTC)


def _windows(
    _machine_id: int | None, start: datetime, end: datetime
) -> list[tuple[datetime, datetime]]:
    """A day shift from 08:00 to 16:00 on every day of the period."""
    return [(_at(day, 8), _at(day, 16)) for day in range(1, 10)]


def _order(
    id: int,
    start: datetime,
    end: datetime | None,
    *,
    completed: bool = False,
    assessed: bool = False,
) -> BookingQualityOrder:
    return BookingQualityOrder(
        order_id=id,
        production_order_number=f"PO-{id}",
        lot_id=1,
        lot_number="L-1",
        machine_id=1,
        completed=completed,
        has_assessment=assessed,
        booked=BookedOrder(
            actual_start=start,
            actual_end=end,
            canceled_at=None,
            quantity=10.0,
            first_started_operator_id=7,
            interruptions=(),
            completions=(),
        ),
    )


def _quality(
    orders: Sequence[BookingQualityOrder], pauses: Sequence[UncausedPause | None] = ()
) -> BookingQuality:
    return compute_booking_quality(
        orders,
        pauses,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        now=NOW,
        windows_for=_windows,
    )


def test_an_order_left_running_overnight_is_reported_with_its_minutes_outside() -> None:
    quality = _quality([_order(1, _at(3, 14), _at(4, 10), completed=True, assessed=True)])

    [finding] = quality.outside_working_time
    assert (finding.order_id, finding.booked_minutes, finding.outside_minutes) == (1, 1200, 960)


def test_a_short_overrun_at_the_end_of_the_shift_is_tolerated() -> None:
    quality = _quality([_order(1, _at(3, 14), _at(3, 16, 20), completed=True, assessed=True)])

    assert quality.outside_working_time == ()


def test_a_final_completion_without_an_assessment_is_reported() -> None:
    quality = _quality(
        [
            _order(1, _at(3, 8), _at(3, 12), completed=True, assessed=False),
            _order(2, _at(3, 8), _at(3, 12), completed=True, assessed=True),
            _order(3, _at(3, 8), None),
        ]
    )

    assert quality.final_completions == 2
    assert [f.order_id for f in quality.missing_assessments] == [1]
    assert quality.orders_with_bookings == 3


def test_a_completion_before_the_period_is_not_counted() -> None:
    quality = _quality([_order(1, _at(1, 8), _at(1, 12), completed=True, assessed=False)])

    assert (quality.final_completions, quality.missing_assessments) == (0, ())


def test_only_pauses_without_a_cause_are_listed_out_of_all_manual_pauses() -> None:
    uncaused = UncausedPause(
        order_id=1,
        production_order_number="PO-1",
        lot_id=1,
        lot_number="L-1",
        machine_id=1,
        paused_at=_at(3, 10),
        operator_id=7,
    )

    quality = _quality([], [None, uncaused, None])

    assert quality.manual_pauses == 3
    assert [p.order_id for p in quality.uncaused_pauses] == [1]
