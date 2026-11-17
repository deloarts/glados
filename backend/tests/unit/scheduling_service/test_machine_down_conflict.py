"""
Unit tests for ScheduleConflictReason.MACHINE_DOWN, raised in
_static_conflicts off OrderSchedulingContext.machine_down. No database,
no HTTP, pure functions only.
"""

from dataclasses import replace
from datetime import UTC
from datetime import datetime

from src.modules.fulfillment.domain.services.scheduling import compute_order_conflicts
from src.modules.fulfillment.domain.value_objects.schedule_conflict import ScheduleConflictReason
from tests.unit.scheduling_service._helpers import make_context

NOW = datetime(2026, 8, 6, 8, 0, tzinfo=UTC)


def test_machine_down_is_flagged_for_a_non_terminal_order():
    ctx = replace(make_context(status="queued"), machine_down=True)

    conflicts = compute_order_conflicts(ctx, planned_end=None, now=NOW)

    assert ScheduleConflictReason.MACHINE_DOWN.value in conflicts


def test_machine_not_down_is_not_flagged():
    ctx = replace(make_context(status="queued"), machine_down=False)

    conflicts = compute_order_conflicts(ctx, planned_end=None, now=NOW)

    assert ScheduleConflictReason.MACHINE_DOWN.value not in conflicts


def test_a_terminal_order_is_never_flagged_even_on_a_down_machine():
    for status in ("completed", "canceled"):
        ctx = replace(make_context(status=status), machine_down=True)
        conflicts = compute_order_conflicts(ctx, planned_end=None, now=NOW)
        assert ScheduleConflictReason.MACHINE_DOWN.value not in conflicts, status


def test_machine_down_combines_with_other_conflicts():
    ctx = replace(
        make_context(status="queued", capability_mismatch=True),
        machine_down=True,
    )

    conflicts = compute_order_conflicts(ctx, planned_end=None, now=NOW)

    assert ScheduleConflictReason.MACHINE_DOWN.value in conflicts
    assert ScheduleConflictReason.CAPABILITY_MISMATCH.value in conflicts
