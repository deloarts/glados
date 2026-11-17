"""
Events of the production schedule as a whole.
"""

from dataclasses import dataclass

from src.shared_kernel.domain.events.base import DomainEvent


@dataclass(frozen=True)
class ScheduleRecomputeRequested(DomainEvent):
    """A committed write may have moved planned dates, so the schedule is to
    be walked again (RecomputeMachineSchedule). `generation` is the
    coalescing generation the request drew, None when the coordinator was
    unavailable, in which case the walk runs unconditionally."""

    generation: int | None
