"""
Unit tests for the machine calendar CRUD use cases: per-machine
working-hours override (upsert/delete) and calendar exceptions (create/
update/delete). No database, no HTTP, in-memory fakes.
"""

from datetime import date

import pytest

from src.modules.catalogue.domain.errors import ProductionMachineNotFoundError
from src.modules.fulfillment.application.dto.machine_calendar_dto import (
    CreateMachineCalendarExceptionCommand,
)
from src.modules.fulfillment.application.dto.machine_calendar_dto import (
    SetMachineWorkingHoursCommand,
)
from src.modules.fulfillment.application.dto.machine_calendar_dto import (
    UpdateMachineCalendarExceptionCommand,
)
from src.modules.fulfillment.application.dto.machine_calendar_dto import WorkIntervalDto
from src.modules.fulfillment.application.use_cases.production_machine.calendar_exceptions import (
    CreateMachineCalendarException,
)
from src.modules.fulfillment.application.use_cases.production_machine.calendar_exceptions import (
    DeleteMachineCalendarException,
)
from src.modules.fulfillment.application.use_cases.production_machine.calendar_exceptions import (
    UpdateMachineCalendarException,
)
from src.modules.fulfillment.application.use_cases.production_machine.working_hours import (
    DeleteMachineWorkingHours,
)
from src.modules.fulfillment.application.use_cases.production_machine.working_hours import (
    GetMachineWorkingHours,
)
from src.modules.fulfillment.application.use_cases.production_machine.working_hours import (
    SetMachineWorkingHours,
)
from src.modules.fulfillment.domain.entities.machine_calendar_exception import (
    MachineCalendarException,
)
from src.modules.fulfillment.domain.entities.machine_working_hours import MachineWorkingHours
from src.modules.fulfillment.domain.entities.production_machine import ProductionMachine
from src.modules.fulfillment.domain.errors import MachineCalendarExceptionNotFoundError
from src.modules.fulfillment.domain.errors import MachineWorkingHoursNotFoundError
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.exceptions import InvalidScheduleCalendarError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.fakes import FakeUnitOfWork


class FakeMachineRepo:
    def __init__(self, machines: dict[int, ProductionMachine]):
        self._machines = machines

    async def get_by_id(self, id: int) -> ProductionMachine | None:
        return self._machines.get(id)

    async def get_by_ids(self, ids: list[int]) -> list:
        found = [await self.get_by_id(i) for i in ids]
        return [item for item in found if item is not None]


class FakeMachineCalendarRepo:
    def __init__(self):
        self._working_hours: dict[int, MachineWorkingHours] = {}
        self._exceptions: dict[int, MachineCalendarException] = {}
        self._next_wh_id = 1
        self._next_exc_id = 1

    async def get_working_hours_by_machine_id(self, machine_id: int) -> MachineWorkingHours | None:
        return next((w for w in self._working_hours.values() if w.machine_id == machine_id), None)

    async def get_working_hours_by_machine_ids(
        self, machine_ids: list[int]
    ) -> list[MachineWorkingHours]:
        # Batch counterpart: empty input -> [], otherwise only the
        # requested machines' rows (subset filtering), mirroring the real
        # adapter's contract.
        if not machine_ids:
            return []
        return [w for w in self._working_hours.values() if w.machine_id in machine_ids]

    async def save_working_hours(self, item: MachineWorkingHours) -> MachineWorkingHours:
        if item.id == 0:
            item.id = self._next_wh_id
            self._next_wh_id += 1
        self._working_hours[item.id] = item
        return item

    async def delete_working_hours(self, item: MachineWorkingHours) -> None:
        self._working_hours.pop(item.id, None)

    async def get_exceptions_by_machine_id(self, machine_id: int) -> list[MachineCalendarException]:
        return [e for e in self._exceptions.values() if e.machine_id == machine_id]

    async def get_exceptions_by_machine_ids(
        self, machine_ids: list[int]
    ) -> list[MachineCalendarException]:
        if not machine_ids:
            return []
        return [e for e in self._exceptions.values() if e.machine_id in machine_ids]

    async def get_holidays(self) -> list:
        return []

    async def get_exception_by_id(self, id: int) -> MachineCalendarException | None:
        return self._exceptions.get(id)

    async def get_exception_by_machine_and_date(self, machine_id, exception_date):
        return next(
            (
                e
                for e in self._exceptions.values()
                if e.machine_id == machine_id and e.exception_date == exception_date
            ),
            None,
        )

    async def save_exception(self, item: MachineCalendarException) -> MachineCalendarException:
        if item.id == 0:
            item.id = self._next_exc_id
            self._next_exc_id += 1
        self._exceptions[item.id] = item
        return item

    async def delete_exception(self, item: MachineCalendarException) -> None:
        self._exceptions.pop(item.id, None)


def make_machine(id: int = 1) -> ProductionMachine:
    return ProductionMachine(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        archived=False,
        internal_name="Mill 1",
        vendor="Acme",
        model="X1",
        fabrication_method_ids=[1],
        max_part_dimension=None,
        note=None,
        creator_id=1,
    )


def _intervals(minutes_by_day: dict[int, int]) -> dict[int, list[WorkIntervalDto]]:
    """A week of minute counts as intervals from 08:00, the command's form."""
    return {
        day: [WorkIntervalDto(start="08:00", minutes=minutes)] if minutes else []
        for day, minutes in minutes_by_day.items()
    }


def _minutes(weekly_hours: dict[int, list[WorkIntervalDto]]) -> dict[int, int]:
    return {day: sum(i.minutes for i in intervals) for day, intervals in weekly_hours.items()}


class TestSetMachineWorkingHours:
    def setup_method(self):
        self.calendars = FakeMachineCalendarRepo()
        self.machines = FakeMachineRepo({1: make_machine(1)})
        self.use_case = SetMachineWorkingHours(self.calendars, self.machines, uow=FakeUnitOfWork())
        self.actor = make_user(permissions=[Permission.WRITE_MACHINES])

    async def test_creates_override_when_none_exists(self):
        weekly = {0: 600, 1: 600, 2: 600, 3: 600, 4: 600, 5: 0, 6: 0}
        result = await self.use_case.execute(
            self.actor,
            machine_id=1,
            cmd=SetMachineWorkingHoursCommand(weekly_hours=_intervals(weekly)),
        )
        assert _minutes(result.weekly_hours) == weekly
        assert result.machine_id == 1

    async def test_upserts_existing_override(self):
        weekly = {0: 600, 1: 600, 2: 600, 3: 600, 4: 600, 5: 0, 6: 0}
        first = await self.use_case.execute(
            self.actor,
            machine_id=1,
            cmd=SetMachineWorkingHoursCommand(weekly_hours=_intervals(weekly)),
        )
        updated_weekly = {**weekly, 5: 240}
        second = await self.use_case.execute(
            self.actor,
            machine_id=1,
            cmd=SetMachineWorkingHoursCommand(weekly_hours=_intervals(updated_weekly)),
        )
        assert second.id == first.id
        assert _minutes(second.weekly_hours)[5] == 240

    async def test_rejects_incomplete_weekday_map(self):
        with pytest.raises(InvalidScheduleCalendarError):
            await self.use_case.execute(
                self.actor,
                machine_id=1,
                cmd=SetMachineWorkingHoursCommand(weekly_hours=_intervals({0: 480})),
            )

    async def test_unknown_machine_raises(self):
        weekly = {0: 480, 1: 480, 2: 480, 3: 480, 4: 480, 5: 0, 6: 0}
        with pytest.raises(ProductionMachineNotFoundError):
            await self.use_case.execute(
                self.actor,
                machine_id=999,
                cmd=SetMachineWorkingHoursCommand(weekly_hours=_intervals(weekly)),
            )

    async def test_unprivileged_cannot_set(self):
        weekly = {0: 480, 1: 480, 2: 480, 3: 480, 4: 480, 5: 0, 6: 0}
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(
                actor,
                machine_id=1,
                cmd=SetMachineWorkingHoursCommand(weekly_hours=_intervals(weekly)),
            )


class TestDeleteMachineWorkingHours:
    def setup_method(self):
        self.calendars = FakeMachineCalendarRepo()
        self.machines = FakeMachineRepo({1: make_machine(1)})
        self.actor = make_user(permissions=[Permission.WRITE_MACHINES])

    async def test_deletes_existing_override(self):
        weekly = {0: 480, 1: 480, 2: 480, 3: 480, 4: 480, 5: 0, 6: 0}
        await SetMachineWorkingHours(self.calendars, self.machines, uow=FakeUnitOfWork()).execute(
            self.actor,
            machine_id=1,
            cmd=SetMachineWorkingHoursCommand(weekly_hours=_intervals(weekly)),
        )
        await DeleteMachineWorkingHours(self.calendars, uow=FakeUnitOfWork()).execute(
            self.actor, machine_id=1
        )
        assert await GetMachineWorkingHours(self.calendars).execute(machine_id=1) is None

    async def test_missing_override_raises(self):
        with pytest.raises(MachineWorkingHoursNotFoundError):
            await DeleteMachineWorkingHours(self.calendars, uow=FakeUnitOfWork()).execute(
                self.actor, machine_id=1
            )


class TestMachineCalendarExceptions:
    def setup_method(self):
        self.calendars = FakeMachineCalendarRepo()
        self.machines = FakeMachineRepo({1: make_machine(1)})
        self.actor = make_user(permissions=[Permission.WRITE_MACHINES])

    async def test_create_then_get(self):
        result = await CreateMachineCalendarException(
            self.calendars, self.machines, uow=FakeUnitOfWork()
        ).execute(
            self.actor,
            machine_id=1,
            cmd=CreateMachineCalendarExceptionCommand(
                exception_date=date(2026, 12, 25), available_minutes=0, note="Holiday"
            ),
        )
        assert result.available_minutes == 0
        exceptions = await self.calendars.get_exceptions_by_machine_id(1)
        assert len(exceptions) == 1

    async def test_duplicate_date_rejected(self):
        cmd = CreateMachineCalendarExceptionCommand(
            exception_date=date(2026, 12, 25), available_minutes=0, note=None
        )
        await CreateMachineCalendarException(
            self.calendars, self.machines, uow=FakeUnitOfWork()
        ).execute(self.actor, machine_id=1, cmd=cmd)
        with pytest.raises(InvalidScheduleCalendarError):
            await CreateMachineCalendarException(
                self.calendars, self.machines, uow=FakeUnitOfWork()
            ).execute(self.actor, machine_id=1, cmd=cmd)

    async def test_update_changes_minutes_and_note(self):
        created = await CreateMachineCalendarException(
            self.calendars, self.machines, uow=FakeUnitOfWork()
        ).execute(
            self.actor,
            machine_id=1,
            cmd=CreateMachineCalendarExceptionCommand(
                exception_date=date(2026, 12, 25), available_minutes=0, note=None
            ),
        )
        updated = await UpdateMachineCalendarException(
            self.calendars, uow=FakeUnitOfWork()
        ).execute(
            self.actor,
            exception_id=created.id,
            cmd=UpdateMachineCalendarExceptionCommand(available_minutes=240, note="Half day"),
        )
        assert updated.available_minutes == 240
        assert updated.note == "Half day"

    async def test_update_missing_raises(self):
        with pytest.raises(MachineCalendarExceptionNotFoundError):
            await UpdateMachineCalendarException(self.calendars, uow=FakeUnitOfWork()).execute(
                self.actor,
                exception_id=999,
                cmd=UpdateMachineCalendarExceptionCommand(available_minutes=0, note=None),
            )

    async def test_delete_removes_exception(self):
        created = await CreateMachineCalendarException(
            self.calendars, self.machines, uow=FakeUnitOfWork()
        ).execute(
            self.actor,
            machine_id=1,
            cmd=CreateMachineCalendarExceptionCommand(
                exception_date=date(2026, 12, 25), available_minutes=0, note=None
            ),
        )
        await DeleteMachineCalendarException(self.calendars, uow=FakeUnitOfWork()).execute(
            self.actor, exception_id=created.id
        )
        assert await self.calendars.get_exceptions_by_machine_id(1) == []


class TestGetWorkingHoursByMachineIdsBatch:
    """get_working_hours_by_machine_ids is API surface: a
    batch counterpart to get_working_hours_by_machine_id, added so the
    scheduler's per-machine calendar loops (auto-plan, schedule board,
    pool recompute) can fetch every candidate machine's override row in
    one query instead of one per machine. No use case calls it directly
    (only scheduling_context.build_machine_calendars does), so this is a contract
    test against the repository method itself: empty input -> [],
    otherwise only the requested machines' rows (subset filtering),
    mirroring get_exceptions_by_machine_ids' already-established
    contract."""

    def setup_method(self):
        self.calendars = FakeMachineCalendarRepo()
        self.machines = FakeMachineRepo(
            {1: make_machine(1), 2: make_machine(2), 3: make_machine(3)}
        )
        self.actor = make_user(permissions=[Permission.WRITE_MACHINES])

    async def test_empty_input_returns_empty_list(self):
        assert await self.calendars.get_working_hours_by_machine_ids([]) == []

    async def test_returns_only_the_requested_machines(self):
        weekly = {0: 480, 1: 480, 2: 480, 3: 480, 4: 480, 5: 0, 6: 0}
        await SetMachineWorkingHours(self.calendars, self.machines, uow=FakeUnitOfWork()).execute(
            self.actor,
            machine_id=1,
            cmd=SetMachineWorkingHoursCommand(weekly_hours=_intervals(weekly)),
        )
        await SetMachineWorkingHours(self.calendars, self.machines, uow=FakeUnitOfWork()).execute(
            self.actor,
            machine_id=2,
            cmd=SetMachineWorkingHoursCommand(weekly_hours=_intervals(weekly)),
        )
        # Machine 3 never gets an override row, so it is absent from the
        # result, same as get_working_hours_by_machine_id would return None for it.

        result = await self.calendars.get_working_hours_by_machine_ids([1, 3])

        assert {wh.machine_id for wh in result} == {1}
