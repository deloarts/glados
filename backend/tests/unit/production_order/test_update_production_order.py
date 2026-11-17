"""
Covers updating an existing production order's fields, including recomputing its planned
end time by walking the assigned machine's working calendar and triggering the global
schedule recompute. Unit tests for TestUpdateProductionOrder. No database, no HTTP. All
dependencies replaced with in-memory fakes.
"""

import logging
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from datetime import timezone

import pytest

from src.modules.fulfillment.application.dto.production_order_dto import (
    UpdateProductionOrderCommand,
)
from src.modules.fulfillment.application.use_cases.production_order.update_production_order import (
    UpdateProductionOrder,
)
from src.modules.fulfillment.domain.errors import ProductionOrderInvalidScheduleError
from src.modules.fulfillment.domain.errors import ProductionOrderInvalidStatusTransitionError
from src.modules.fulfillment.domain.errors import ProductionOrderNoMachineAssignedError
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.production_order._helpers import make_order
from tests.unit.production_order.fakes import FakeAdminSettingsRepository
from tests.unit.production_order.fakes import FakeLockPlan
from tests.unit.production_order.fakes import FakeProductionOrderRepository
from tests.unit.production_order.fakes import FakeRecomputeSchedule


class FakeMachineCalendarRepository:
    """No per-machine override, no exceptions: every machine just uses
    the admin default weekly hours."""

    async def get_working_hours_by_machine_id(self, machine_id: int):
        return None

    async def get_working_hours_by_machine_ids(self, machine_ids: list[int]):
        # Additive stub for the new batch port method, see
        # get_working_hours_by_machine_id above.
        return []

    async def get_exceptions_by_machine_id(self, machine_id: int):
        return []

    async def get_exceptions_by_machine_ids(self, machine_ids: list[int]):
        # Additive stub, see get_working_hours_by_machine_ids above.
        return []

    async def get_holidays(self) -> list:
        return []

    def __getattr__(self, item):
        raise NotImplementedError(item)


class TestUpdateProductionOrder:
    def setup_method(self):
        self.order_repo = FakeProductionOrderRepository([make_order(id=1, queue_sequence=1)])
        self.write_actor = make_user(permissions=[Permission.WRITE_PRODUCTION_ORDERS])
        self.manage_actor = make_user(
            permissions=[Permission.WRITE_PRODUCTION_ORDERS, Permission.MANAGE_PRODUCTION_ORDERS]
        )
        self.uow = FakeUnitOfWork()
        self.use_case = UpdateProductionOrder(
            self.order_repo, uow=self.uow, lock_plan=FakeLockPlan()
        )

    async def test_updates_note_with_write_permission_only(self):
        cmd = UpdateProductionOrderCommand(note="hello")
        result = await self.use_case.execute(self.write_actor, production_order_id=1, cmd=cmd)
        assert result.note == "hello"
        assert self.uow.committed

    async def test_a_successful_update_logs_one_info_line_naming_order_and_fields(
        self, glados_caplog
    ):
        """The acting user is not named in the message: contextvars already
        stamp request_id/user on every log record (see ContextFilter)."""
        cmd = UpdateProductionOrderCommand(priority="high")

        await self.use_case.execute(self.manage_actor, production_order_id=1, cmd=cmd)

        (record,) = [r for r in glados_caplog.records if r.name == "glados"]
        assert record.levelno == logging.INFO
        message = record.getMessage()
        assert "#1" in message
        assert "priority" in message

    async def test_a_no_op_update_logs_nothing(self, glados_caplog):
        cmd = UpdateProductionOrderCommand()

        await self.use_case.execute(self.write_actor, production_order_id=1, cmd=cmd)

        assert [r for r in glados_caplog.records if r.name == "glados"] == []

    async def test_rejects_priority_edit_on_completed_order(self):
        # A terminal order cannot be edited at all.
        self.order_repo._orders[1].status = ProductionOrderStatus.COMPLETED
        before = self.order_repo._orders[1].priority
        cmd = UpdateProductionOrderCommand(priority="high")
        with pytest.raises(ProductionOrderInvalidStatusTransitionError):
            await self.use_case.execute(self.manage_actor, production_order_id=1, cmd=cmd)
        assert (await self.order_repo.get_by_id(1)).priority == before

    async def test_rejects_pinned_edit_on_canceled_order(self):
        self.order_repo._orders[1].status = ProductionOrderStatus.CANCELED
        cmd = UpdateProductionOrderCommand(pinned=True)
        with pytest.raises(ProductionOrderInvalidStatusTransitionError):
            await self.use_case.execute(self.manage_actor, production_order_id=1, cmd=cmd)
        assert (await self.order_repo.get_by_id(1)).pinned is False

    async def test_permission_check_precedes_the_terminal_state_check(self):
        """A permission-less caller must get 403, never a 422 that would leak
        the order's state."""
        self.order_repo._orders[1].status = ProductionOrderStatus.COMPLETED
        permissionless = make_user(permissions=[])
        cmd = UpdateProductionOrderCommand(note="hello")
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(permissionless, production_order_id=1, cmd=cmd)

    async def test_setting_schedule_requires_manage_permission(self):
        cmd = UpdateProductionOrderCommand(
            planned_start=datetime(2026, 7, 22, 8, 0),
            planned_end=datetime(2026, 7, 23, 8, 0),
        )
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(self.write_actor, production_order_id=1, cmd=cmd)

    async def test_sets_planned_start_and_end_and_auto_pins(self):
        # A client may send these without an offset. planned_start/planned_end
        # are `timestamptz`, so a naive value is pinned to UTC on the way in
        # rather than left for the database to read in its session timezone.
        start = datetime(2026, 7, 22, 8, 0)
        end = datetime(2026, 7, 23, 8, 0)
        cmd = UpdateProductionOrderCommand(planned_start=start, planned_end=end)
        result = await self.use_case.execute(self.manage_actor, production_order_id=1, cmd=cmd)
        assert result.planned_start == start.replace(tzinfo=UTC)
        assert result.planned_end == end.replace(tzinfo=UTC)
        assert result.pinned is True

    async def test_an_offset_bearing_planned_window_is_converted_not_relabelled(self):
        """An aware value keeps its instant: 10:00+02:00 is 08:00 UTC."""
        cmd = UpdateProductionOrderCommand(
            planned_start=datetime(2026, 7, 22, 10, 0, tzinfo=timezone(timedelta(hours=2))),
            planned_end=datetime(2026, 7, 23, 10, 0, tzinfo=timezone(timedelta(hours=2))),
        )
        result = await self.use_case.execute(self.manage_actor, production_order_id=1, cmd=cmd)
        assert result.planned_start == datetime(2026, 7, 22, 8, 0, tzinfo=UTC)
        assert result.planned_end == datetime(2026, 7, 23, 8, 0, tzinfo=UTC)

    async def test_setting_schedule_respects_explicit_pinned_false(self):
        cmd = UpdateProductionOrderCommand(
            planned_start=datetime(2026, 7, 22, 8, 0),
            planned_end=datetime(2026, 7, 23, 8, 0),
            pinned=False,
        )
        result = await self.use_case.execute(self.manage_actor, production_order_id=1, cmd=cmd)
        assert result.pinned is False

    async def test_rejects_schedule_on_in_progress_order(self):
        self.order_repo._orders[1].status = ProductionOrderStatus.IN_PROGRESS
        cmd = UpdateProductionOrderCommand(
            planned_start=datetime(2026, 7, 22, 8, 0),
            planned_end=datetime(2026, 7, 23, 8, 0),
        )
        with pytest.raises(ProductionOrderInvalidScheduleError):
            await self.use_case.execute(self.manage_actor, production_order_id=1, cmd=cmd)

    def test_rejects_planned_start_without_planned_end(self):
        with pytest.raises(Exception):  # noqa: B017, pydantic ValidationError
            UpdateProductionOrderCommand(planned_start=datetime(2026, 7, 22, 8, 0))

    def test_rejects_planned_end_before_planned_start(self):
        with pytest.raises(Exception):  # noqa: B017, pydantic ValidationError
            UpdateProductionOrderCommand(
                planned_start=datetime(2026, 7, 23, 8, 0),
                planned_end=datetime(2026, 7, 22, 8, 0),
            )

    def test_rejects_planned_end_alongside_recompute_planned_end(self):
        with pytest.raises(Exception):  # noqa: B017, pydantic ValidationError
            UpdateProductionOrderCommand(
                planned_start=datetime(2026, 7, 22, 8, 0),
                planned_end=datetime(2026, 7, 23, 8, 0),
                recompute_planned_end=True,
            )

    def test_rejects_recompute_planned_end_without_planned_start(self):
        with pytest.raises(Exception):  # noqa: B017, pydantic ValidationError
            UpdateProductionOrderCommand(recompute_planned_end=True)

    async def test_recompute_planned_end_walks_the_machine_calendar(self):
        # 2026-07-20 is a Monday, so a plain 30-minute order (make_order's
        # default estimated_duration_minutes) started at the calendar's own
        # 08:00 day-start stays within the same working day.
        use_case = UpdateProductionOrder(
            self.order_repo,
            calendar_repo=FakeMachineCalendarRepository(),
            settings_repo=FakeAdminSettingsRepository(),
            uow=FakeUnitOfWork(),
            lock_plan=FakeLockPlan(),
        )
        start = datetime(2026, 7, 20, 8, 0, tzinfo=UTC)
        cmd = UpdateProductionOrderCommand(planned_start=start, recompute_planned_end=True)
        result = await use_case.execute(self.manage_actor, production_order_id=1, cmd=cmd)
        assert result.planned_start == start
        assert result.planned_end == datetime(2026, 7, 20, 8, 30, tzinfo=UTC)
        assert result.pinned is True

    async def test_recompute_planned_end_skips_the_weekend(self):
        self.order_repo._orders[1].estimated_duration_minutes = 500
        use_case = UpdateProductionOrder(
            self.order_repo,
            calendar_repo=FakeMachineCalendarRepository(),
            settings_repo=FakeAdminSettingsRepository(),
            uow=FakeUnitOfWork(),
            lock_plan=FakeLockPlan(),
        )
        # Friday 08:00 + 500min: 480min fill Friday's 8h working day,
        # the remaining 20min roll to Monday 08:00-08:20 (Sat/Sun closed).
        start = datetime(2026, 8, 14, 8, 0, tzinfo=UTC)
        cmd = UpdateProductionOrderCommand(planned_start=start, recompute_planned_end=True)
        result = await use_case.execute(self.manage_actor, production_order_id=1, cmd=cmd)
        assert result.planned_end == datetime(2026, 8, 17, 8, 20, tzinfo=UTC)

    async def test_recompute_planned_end_rejects_order_with_no_machine(self):
        self.order_repo._orders[1].machine_id = None
        use_case = UpdateProductionOrder(
            self.order_repo,
            calendar_repo=FakeMachineCalendarRepository(),
            settings_repo=FakeAdminSettingsRepository(),
            uow=FakeUnitOfWork(),
            lock_plan=FakeLockPlan(),
        )
        cmd = UpdateProductionOrderCommand(
            planned_start=datetime(2026, 7, 20, 8, 0), recompute_planned_end=True
        )
        with pytest.raises(ProductionOrderNoMachineAssignedError):
            await use_case.execute(self.manage_actor, production_order_id=1, cmd=cmd)

    async def test_update_triggers_a_single_global_schedule_recompute(self):
        """A single execute_all() call always covers every machine/pool/bucket,
        including any later position's machine in the same lot, so there's no
        separate "downstream" recompute to opt into."""
        recompute = FakeRecomputeSchedule()
        use_case = UpdateProductionOrder(
            self.order_repo,
            recompute_schedule=recompute,
            uow=FakeUnitOfWork(),
            lock_plan=FakeLockPlan(),
        )
        cmd = UpdateProductionOrderCommand(
            planned_start=datetime(2026, 7, 22, 8, 0),
            planned_end=datetime(2026, 7, 23, 8, 0),
        )
        await use_case.execute(self.manage_actor, production_order_id=1, cmd=cmd)
        assert recompute.execute_all_calls == 1
