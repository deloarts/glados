"""
The shared OrderSchedulingContext factory and calendar/date constants used by every
scheduling_service test module, so each test file builds its scheduling contexts the same
way instead of duplicating fixture setup. walk_machine_queue and walk_pool_queue run a
single queue through schedule_all, the walk production uses.
"""

from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import tzinfo

from src.modules.fulfillment.domain.services.scheduling import MachineCalendar
from src.modules.fulfillment.domain.services.scheduling import OrderSchedulingContext
from src.modules.fulfillment.domain.services.scheduling import ScheduledOrder
from src.modules.fulfillment.domain.services.scheduling import build_machine_calendar
from src.modules.fulfillment.domain.services.scheduling import schedule_all

WEEKDAY_HOURS = {0: 480, 1: 480, 2: 480, 3: 480, 4: 480, 5: 0, 6: 0}  # Mon-Fri 8h, weekend off

# 2026-07-27 is a Monday.
MONDAY = date(2026, 7, 27)
TUESDAY = date(2026, 7, 28)
SATURDAY = date(2026, 8, 1)
SUNDAY = date(2026, 8, 2)


def make_context(
    order_id=1,
    queue_sequence=1,
    status="queued",
    pinned=False,
    estimated_duration_minutes=60,
    not_before=None,
    actual_start=None,
    existing_planned_start=None,
    existing_planned_end=None,
    predecessor_ready_at=None,
    material_ready_at=None,
    target_date=None,
    capability_mismatch=False,
    uncategorized_step=False,
    position_not_fully_queued=False,
    time_estimate_source="measured",
    is_manual_step=False,
    upstream_input_available=True,
    position_sequence=1,
    predecessor_chain_unknown=False,
    machine_pool_id=None,
    zone: tzinfo = UTC,
) -> OrderSchedulingContext:
    return OrderSchedulingContext(
        order_id=order_id,
        queue_sequence=queue_sequence,
        status=status,
        pinned=pinned,
        estimated_duration_minutes=estimated_duration_minutes,
        not_before=not_before,
        actual_start=actual_start,
        existing_planned_start=existing_planned_start,
        existing_planned_end=existing_planned_end,
        predecessor_ready_at=predecessor_ready_at,
        material_ready_at=material_ready_at,
        target_date=target_date,
        capability_mismatch=capability_mismatch,
        uncategorized_step=uncategorized_step,
        position_not_fully_queued=position_not_fully_queued,
        time_estimate_source=time_estimate_source,
        is_manual_step=is_manual_step,
        upstream_input_available=upstream_input_available,
        position_sequence=position_sequence,
        predecessor_chain_unknown=predecessor_chain_unknown,
        machine_pool_id=machine_pool_id,
        zone=zone,
    )


_MACHINE_ID = 1
_POOL_ID = 1


def walk_machine_queue(
    orders: list[OrderSchedulingContext], calendar: MachineCalendar, now: datetime
) -> list[ScheduledOrder]:
    """The placements of one machine's queue when it is the only queue."""
    result = schedule_all(
        machine_queues={_MACHINE_ID: orders},
        machine_calendars={_MACHINE_ID: calendar},
        pool_queues={},
        pool_members={},
        manual_queue=[],
        manual_calendar=calendar,
        unassigned=[],
        now=now,
    )
    return result.by_machine[_MACHINE_ID]


def walk_pool_queue(
    orders: list[OrderSchedulingContext],
    member_calendars: dict[int, MachineCalendar],
    now: datetime,
    machine_queues: dict[int, list[OrderSchedulingContext]] | None = None,
) -> list[ScheduledOrder]:
    """The placements of one pool's queue, whose members are the keys of
    member_calendars. machine_queues holds the members' own machine-assigned
    orders, which are walked first and occupy the members before the pool."""
    result = schedule_all(
        machine_queues=machine_queues or {},
        machine_calendars=member_calendars,
        pool_queues={_POOL_ID: orders},
        pool_members={_POOL_ID: list(member_calendars)},
        manual_queue=[],
        manual_calendar=build_machine_calendar(WEEKDAY_HOURS, None, {}),
        unassigned=[],
        now=now,
    )
    return result.by_pool[_POOL_ID]
