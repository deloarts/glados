"""The wait after a position of a lot, such as curing or a lab result.

A method can make the pieces wait a number of clock minutes after its step
before the next step may start. A position waits as long as its last step
does, since that step hands the pieces on. The internal share of a MIXED
position waits as long as its last step done in house, and an EXTERNAL
position waits nothing, because the supplier's lead time already covers it.
The wait runs on clock time, overnight and over weekends too, so it is added
to a moment, and the backward passes count it in whole calendar days.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta

from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.shared_kernel.domain.services.clock import as_utc

_MINUTES_PER_DAY = 24 * 60


@dataclass(frozen=True)
class StepWait:
    """What the wait of a position reads from one of its steps: its place in
    the routing, whether a supplier usually does it, and its method's wait."""

    sequence: int
    usually_external: bool
    minutes: int | None


def step_waits(steps: Iterable[LotStep]) -> list[StepWait]:
    """The StepWait of each lot step, from the method fields its repository
    mapper fills."""
    return [
        StepWait(
            sequence=step.sequence,
            usually_external=(
                step.role == StepRole.FABRICATION and step.fabrication_method_required_external
            ),
            minutes=step.method_wait_after_minutes,
        )
        for step in steps
    ]


def position_wait_after_minutes(kind: str, steps: Iterable[StepWait]) -> int:
    """The clock minutes the pieces of a position wait after it: its last
    step's wait for an INTERNAL position, its last in-house step's for a
    MIXED one, and none for any other kind."""
    if kind == LotPositionKind.INTERNAL:
        candidates = list(steps)
    elif kind == LotPositionKind.MIXED:
        candidates = [step for step in steps if not step.usually_external]
    else:
        return 0
    if not candidates:
        return 0
    last = max(candidates, key=lambda step: step.sequence)
    return max(last.minutes or 0, 0)


def wait_days(minutes: int) -> int:
    """A wait in whole calendar days, rounded up, for the backward passes."""
    return -(-max(minutes, 0) // _MINUTES_PER_DAY)


def ready_after_wait(end: datetime, minutes: int) -> datetime:
    """The moment the pieces of a step that ends at `end` are ready for the
    next one."""
    return as_utc(end) + timedelta(minutes=max(minutes, 0))


def latest_ready_moment(ends: Iterable[tuple[datetime | None, int]]) -> datetime | None:
    """The latest of several ends each followed by its wait, such as the
    orders of a lot, ignoring unknown ends. A lot is finished once the
    pieces of its last position are ready, so this is the moment its late
    checks compare with the target date. None when no end is known."""
    moments = [ready_after_wait(end, minutes) for end, minutes in ends if end is not None]
    return max(moments) if moments else None
