"""
The spans of booked work derived from a production order's bookings, and
their clipping to working time (domain/policies/booked_work.py).
"""

from collections.abc import Sequence
from datetime import UTC
from datetime import date
from datetime import datetime

from src.modules.fulfillment.domain.entities.production_order_completion import (
    ProductionOrderCompletion,
)
from src.modules.fulfillment.domain.entities.production_order_interruption import (
    ProductionOrderInterruption,
)
from src.modules.fulfillment.domain.policies.booked_work import BookedOrder
from src.modules.fulfillment.domain.policies.booked_work import WorkSpan
from src.modules.fulfillment.domain.policies.booked_work import clip_to_windows
from src.modules.fulfillment.domain.policies.booked_work import derive_work_spans
from src.modules.fulfillment.domain.value_objects.interruption_ended_by import InterruptionEndedBy
from src.modules.fulfillment.domain.value_objects.interruption_reason import InterruptionReason

ALEX, SAM = 7, 8


def _at(hour: int, minute: int = 0, day: int = 2) -> datetime:
    """An instant in March 2026, in UTC."""
    return datetime(2026, 3, day, hour, minute, tzinfo=UTC)


def _pause(
    paused: datetime,
    resumed: datetime | None,
    *,
    ended_by: InterruptionEndedBy | None = InterruptionEndedBy.RESUME,
    operator: int | None = None,
    reason: InterruptionReason = InterruptionReason.MANUAL,
) -> ProductionOrderInterruption:
    return ProductionOrderInterruption(
        id=0,
        production_order_id=1,
        paused_at=paused,
        resumed_at=resumed,
        paused_by_id=ALEX,
        resumed_by_id=ALEX if resumed else None,
        created=paused,
        reason=reason,
        resumed_operator_id=operator,
        ended_by=ended_by if resumed else None,
    )


def _completion(
    id: int, created: datetime, accepted: float, *, reverses: int | None = None
) -> ProductionOrderCompletion:
    return ProductionOrderCompletion(
        id=id,
        production_order_id=1,
        quantity=accepted,
        quantity_accepted=accepted,
        quantity_rejected=0.0,
        completion_date=date(2026, 3, 2),
        note=None,
        operator_id=ALEX,
        recorded_by_id=ALEX,
        created=created,
        reverses_completion_id=reverses,
    )


def _order(
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    canceled: datetime | None = None,
    pauses: Sequence[ProductionOrderInterruption] = (),
    completions: Sequence[ProductionOrderCompletion] = (),
    operator: int | None = ALEX,
) -> BookedOrder:
    return BookedOrder(
        actual_start=start,
        actual_end=end,
        canceled_at=canceled,
        quantity=10.0,
        first_started_operator_id=operator,
        interruptions=pauses,
        completions=completions,
    )


def _spans(order: BookedOrder, until: datetime | None = None) -> list[tuple[int, int, int | None]]:
    """Each span as (start hour, end hour, operator), worked until 18:00
    unless `until` says otherwise."""
    spans = derive_work_spans(order, until or _at(18))
    return [(s.start.hour, s.end.hour, s.operator_id) for s in spans]


def test_an_order_that_never_started_has_no_work() -> None:
    assert derive_work_spans(_order(), _at(18)) == []


def test_a_run_without_pauses_is_one_span_under_the_first_operator() -> None:
    assert _spans(_order(start=_at(8), end=_at(12))) == [(8, 12, ALEX)]


def test_a_running_order_is_worked_until_now() -> None:
    assert _spans(_order(start=_at(8)), until=_at(11)) == [(8, 11, ALEX)]


def test_a_resume_by_another_operator_hands_the_next_span_over() -> None:
    order = _order(start=_at(8), end=_at(14), pauses=[_pause(_at(10), _at(11), operator=SAM)])

    assert _spans(order) == [(8, 10, ALEX), (11, 14, SAM)]


def test_a_lot_resume_keeps_the_operator_of_the_last_start() -> None:
    hold = _pause(_at(10), _at(11), operator=None, reason=InterruptionReason.LOT_HOLD)

    assert _spans(_order(start=_at(8), end=_at(14), pauses=[hold])) == [
        (8, 10, ALEX),
        (11, 14, ALEX),
    ]


def test_a_pause_ended_by_a_cancel_opens_no_work() -> None:
    pause = _pause(_at(10), _at(13), ended_by=InterruptionEndedBy.CANCEL)

    assert _spans(_order(start=_at(8), canceled=_at(13), pauses=[pause])) == [(8, 10, ALEX)]


def test_a_pause_ended_by_a_cut_opens_no_work() -> None:
    pause = _pause(_at(10), _at(13), ended_by=InterruptionEndedBy.CUT)

    assert _spans(_order(start=_at(8), end=_at(13), pauses=[pause])) == [(8, 10, ALEX)]


def test_an_open_pause_ends_the_work_at_the_pause() -> None:
    assert _spans(_order(start=_at(8), pauses=[_pause(_at(10), None)])) == [(8, 10, ALEX)]


def test_a_closed_row_from_before_ended_by_counts_as_a_resume() -> None:
    pause = _pause(_at(10), _at(11), ended_by=None)

    assert _spans(_order(start=_at(8), end=_at(12), pauses=[pause])) == [
        (8, 10, ALEX),
        (11, 12, ALEX),
    ]


def test_a_reversed_final_completion_is_not_work_until_the_reversal() -> None:
    # Completed at 12, reversed at 14, completed again at 16.
    order = _order(
        start=_at(8),
        end=_at(16),
        completions=[
            _completion(1, _at(12), 10.0),
            _completion(2, _at(14), -10.0, reverses=1),
            _completion(3, _at(16), 10.0),
        ],
    )

    assert _spans(order) == [(8, 12, ALEX), (14, 16, None)]


def test_reversing_a_partial_completion_changes_no_span() -> None:
    order = _order(
        start=_at(8),
        end=_at(16),
        completions=[
            _completion(1, _at(10), 4.0),
            _completion(2, _at(11), -4.0, reverses=1),
            _completion(3, _at(16), 10.0),
        ],
    )

    assert _spans(order) == [(8, 16, ALEX)]


def test_clipping_keeps_working_time_and_counts_the_rest() -> None:
    # Left running overnight: booked from 14:00 to 10:00 the next day
    # against a day shift of 08:00 to 16:00.
    span = WorkSpan(_at(14), _at(10, day=3), ALEX)
    windows = [(_at(8), _at(16)), (_at(8, day=3), _at(16, day=3))]

    clipped = clip_to_windows([span], windows)

    assert [(s.start, s.end) for s in clipped.inside] == [
        (_at(14), _at(16)),
        (_at(8, day=3), _at(10, day=3)),
    ]
    assert clipped.outside_minutes == 16 * 60
