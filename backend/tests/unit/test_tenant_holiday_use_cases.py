"""
The tenant holiday calendar's use cases: read by anyone, changed and
deleted with write:machines, every holiday named and running forward for at
most a year. A holiday closes every machine's calendar under its own
exceptions.
"""

from dataclasses import replace
from datetime import date

import pytest

from src.modules.fulfillment.application.services.scheduling_context import build_machine_calendars
from src.modules.fulfillment.domain.entities.machine_calendar_exception import (
    MachineCalendarException,
)
from src.modules.platform.application.dto.tenant_holiday_dto import SaveTenantHolidayCommand
from src.modules.platform.application.use_cases.tenant_holiday.tenant_holidays import (
    CreateTenantHoliday,
)
from src.modules.platform.application.use_cases.tenant_holiday.tenant_holidays import (
    DeleteTenantHoliday,
)
from src.modules.platform.application.use_cases.tenant_holiday.tenant_holidays import (
    ListTenantHolidays,
)
from src.modules.platform.application.use_cases.tenant_holiday.tenant_holidays import (
    UpdateTenantHoliday,
)
from src.modules.platform.domain.entities.tenant_holiday import TenantHoliday
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.exceptions import InvalidScheduleCalendarError
from src.modules.platform.domain.exceptions import TenantHolidayNotFoundError
from src.modules.platform.domain.value_objects.holiday_category import HolidayCategory
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.fakes import FakeUnitOfWork

CHRISTMAS = date(2026, 12, 24)
WEEK = {day: (480 if day < 5 else 0) for day in range(7)}


class FakeCalendarRepo:
    def __init__(self) -> None:
        self.holidays: dict[int, TenantHoliday] = {}
        self.exceptions: list[MachineCalendarException] = []

    async def get_holidays(self) -> list[TenantHoliday]:
        return sorted(self.holidays.values(), key=lambda h: (h.start_date, h.id))

    async def get_holiday_by_id(self, id: int) -> TenantHoliday | None:
        holiday = self.holidays.get(id)
        return replace(holiday) if holiday else None

    async def save_holiday(self, item: TenantHoliday) -> TenantHoliday:
        if item.id == 0:
            item = replace(item, id=len(self.holidays) + 1)
        self.holidays[item.id] = item
        return item

    async def delete_holiday(self, item: TenantHoliday) -> None:
        self.holidays.pop(item.id, None)

    async def get_working_hours_by_machine_ids(self, machine_ids: list[int]) -> list:
        return []

    async def get_exceptions_by_machine_ids(self, machine_ids: list[int]) -> list:
        return [e for e in self.exceptions if e.machine_id in machine_ids]


def _command(**overrides) -> SaveTenantHolidayCommand:
    values = {
        "name": "Christmas",
        "category": HolidayCategory.PLANT_SHUTDOWN,
        "start_date": CHRISTMAS,
        "end_date": date(2026, 12, 31),
    }
    return SaveTenantHolidayCommand(**{**values, **overrides})


@pytest.fixture
def repo() -> FakeCalendarRepo:
    return FakeCalendarRepo()


@pytest.fixture
def admin():
    return make_user(permissions=[Permission.WRITE_MACHINES])


async def test_a_holiday_is_created_listed_changed_and_deleted(repo, admin) -> None:
    created = await CreateTenantHoliday(repo, uow=FakeUnitOfWork()).execute(admin, _command())
    assert (created.name, created.category, created.end_date) == (
        "Christmas",
        HolidayCategory.PLANT_SHUTDOWN,
        date(2026, 12, 31),
    )

    updated = await UpdateTenantHoliday(repo, uow=FakeUnitOfWork()).execute(
        admin, created.id, _command(name=" Christmas Eve ", end_date=CHRISTMAS)
    )
    assert (updated.name, updated.end_date) == ("Christmas Eve", CHRISTMAS)
    assert [h.name for h in await ListTenantHolidays(repo).execute()] == ["Christmas Eve"]

    await DeleteTenantHoliday(repo, uow=FakeUnitOfWork()).execute(admin, created.id)
    assert await ListTenantHolidays(repo).execute() == []


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": "  "},
        {"end_date": date(2026, 12, 23)},
        {"end_date": date(2027, 12, 31)},
    ],
)
async def test_a_holiday_without_a_name_backwards_or_longer_than_a_year_is_refused(
    repo, admin, overrides
) -> None:
    with pytest.raises(InvalidScheduleCalendarError):
        await CreateTenantHoliday(repo, uow=FakeUnitOfWork()).execute(admin, _command(**overrides))
    assert repo.holidays == {}


async def test_changing_and_deleting_holidays_need_write_machines(repo, admin) -> None:
    created = await CreateTenantHoliday(repo, uow=FakeUnitOfWork()).execute(admin, _command())
    reader = make_user(permissions=[])

    with pytest.raises(InsufficientPermissionsError):
        await CreateTenantHoliday(repo, uow=FakeUnitOfWork()).execute(reader, _command())
    with pytest.raises(InsufficientPermissionsError):
        await DeleteTenantHoliday(repo, uow=FakeUnitOfWork()).execute(reader, created.id)
    assert list(repo.holidays) == [created.id]

    writer = make_user(permissions=[Permission.WRITE_MACHINES])
    await DeleteTenantHoliday(repo, uow=FakeUnitOfWork()).execute(writer, created.id)
    assert list(repo.holidays) == []


async def test_an_unknown_holiday_is_not_found(repo, admin) -> None:
    with pytest.raises(TenantHolidayNotFoundError):
        await UpdateTenantHoliday(repo, uow=FakeUnitOfWork()).execute(admin, 99, _command())
    with pytest.raises(TenantHolidayNotFoundError):
        await DeleteTenantHoliday(repo, uow=FakeUnitOfWork()).execute(admin, 99)


async def test_a_holiday_closes_every_machine_unless_its_own_exception_opens_it(
    repo, admin
) -> None:
    await CreateTenantHoliday(repo, uow=FakeUnitOfWork()).execute(admin, _command())
    repo.exceptions.append(
        MachineCalendarException(
            id=1,
            created=CHRISTMAS,
            changed=None,
            changes=[],
            exception_date=CHRISTMAS,
            available_minutes=240,
            note=None,
            creator_id=1,
            machine_id=2,
        )
    )

    calendars = await build_machine_calendars([1, 2], repo, WEEK)  # type: ignore[arg-type]

    assert calendars[1].minutes_available_on(CHRISTMAS) == 0
    assert calendars[1].minutes_available_on(date(2026, 12, 28)) == 0
    assert calendars[2].minutes_available_on(CHRISTMAS) == 240
    assert calendars[2].minutes_available_on(date(2027, 1, 4)) == 480
