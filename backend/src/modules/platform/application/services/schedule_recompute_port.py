"""
The production schedule is a derived view of the work, so a write that
changes what the schedule depends on runs the global schedule walk after
its own commit: a holiday or the tenant's working time, a project's time
budget, a machine, method or supplier of the catalogue, and every planning
write. The code below Planning & fulfillment that runs it only knows this
port; the composition root wires RecomputeMachineSchedule into it.

recompute_schedule_after_commit is the guard every such use case runs. A
failed walk must not turn an already committed write into an error
response; it is logged and the next recompute catches up.
"""

from typing import Protocol

from src.modules.platform.infrastructure.logging.logger import log


class ScheduleRecompute(Protocol):
    """The global schedule walk, implemented by RecomputeMachineSchedule."""

    async def execute_all(self) -> object: ...


async def recompute_schedule_after_commit(
    recompute: ScheduleRecompute | None, *, after: str
) -> None:
    """Runs the global schedule walk after a committed write and logs a
    failure instead of raising it.

    `after` completes the log line "Schedule recompute failed after ...",
    naming the action and stating that it is committed. A use case built
    without a recompute (None) skips the walk.
    """
    if recompute is None:
        return
    try:
        await recompute.execute_all()
    except Exception:
        log.exception(f"Schedule recompute failed after {after}")
