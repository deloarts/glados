"""
The tenant holiday calendar: public holidays and plant shutdowns that close
every machine. Every signed-in user can read it, like a machine calendar;
changes and deletes need write:machines. The next
schedule walk plans around a change.
"""

from src.modules.platform.application.dto.tenant_holiday_dto import SaveTenantHolidayCommand
from src.modules.platform.application.dto.tenant_holiday_dto import TenantHolidayResult
from src.modules.platform.application.mappers.tenant_holiday_mapper import TenantHolidayMapper
from src.modules.platform.application.services.schedule_recompute_port import ScheduleRecompute
from src.modules.platform.application.services.schedule_recompute_port import (
    recompute_schedule_after_commit,
)
from src.modules.platform.domain.entities.tenant_holiday import TenantHoliday
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import TenantHolidayNotFoundError
from src.modules.platform.domain.services.tenant_holiday_rules import TenantHolidayRules
from src.modules.platform.domain.services.tenant_holiday_rules import validate_holiday
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.repositories.tenant_holiday_repository import (
    ITenantHolidayRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class ListTenantHolidays:
    def __init__(self, calendar_repo: ITenantHolidayRepository) -> None:
        self._calendars = calendar_repo

    async def execute(self) -> list[TenantHolidayResult]:
        return [TenantHolidayMapper.to_result(h) for h in await self._calendars.get_holidays()]


class CreateTenantHoliday:
    def __init__(
        self,
        calendar_repo: ITenantHolidayRepository,
        *,
        uow: IUnitOfWork,
        recompute_schedule: ScheduleRecompute | None = None,
    ) -> None:
        self._calendars = calendar_repo
        self._uow = uow
        self._recompute = recompute_schedule

    async def execute(self, actor: User, cmd: SaveTenantHolidayCommand) -> TenantHolidayResult:
        TenantHolidayRules.assert_can_write(actor)
        validate_holiday(cmd.name, cmd.start_date, cmd.end_date)
        now = now_utc()
        saved = await self._calendars.save_holiday(
            TenantHoliday(
                id=0,
                created=now,
                changed=now,
                changes=append_changelog([], actor.full_name, "Holiday created."),
                name=cmd.name.strip(),
                category=cmd.category,
                start_date=cmd.start_date,
                end_date=cmd.end_date,
                creator_id=actor.id,
            )
        )
        await self._uow.commit()
        await recompute_schedule_after_commit(
            self._recompute, after="adding a holiday; the change itself is committed."
        )
        log.info(f"Added holiday #{saved.id} from {saved.start_date} to {saved.end_date}.")
        return TenantHolidayMapper.to_result(saved)


class UpdateTenantHoliday:
    def __init__(
        self,
        calendar_repo: ITenantHolidayRepository,
        *,
        uow: IUnitOfWork,
        recompute_schedule: ScheduleRecompute | None = None,
    ) -> None:
        self._calendars = calendar_repo
        self._uow = uow
        self._recompute = recompute_schedule

    async def execute(
        self, actor: User, holiday_id: int, cmd: SaveTenantHolidayCommand
    ) -> TenantHolidayResult:
        TenantHolidayRules.assert_can_write(actor)
        holiday = await self._calendars.get_holiday_by_id(holiday_id)
        if holiday is None:
            raise TenantHolidayNotFoundError(f"Holiday #{holiday_id} not found.")
        validate_holiday(cmd.name, cmd.start_date, cmd.end_date)
        holiday.name = cmd.name.strip()
        holiday.category = cmd.category
        holiday.start_date = cmd.start_date
        holiday.end_date = cmd.end_date
        holiday.changed = now_utc()
        holiday.changes = append_changelog(holiday.changes, actor.full_name, "Holiday updated.")
        saved = await self._calendars.save_holiday(holiday)
        await self._uow.commit()
        await recompute_schedule_after_commit(
            self._recompute, after="changing a holiday; the change itself is committed."
        )
        log.info(f"Updated holiday #{holiday_id}.")
        return TenantHolidayMapper.to_result(saved)


class DeleteTenantHoliday:
    def __init__(
        self,
        calendar_repo: ITenantHolidayRepository,
        *,
        uow: IUnitOfWork,
        recompute_schedule: ScheduleRecompute | None = None,
    ) -> None:
        self._calendars = calendar_repo
        self._uow = uow
        self._recompute = recompute_schedule

    async def execute(self, actor: User, holiday_id: int) -> None:
        TenantHolidayRules.assert_can_delete(actor)
        holiday = await self._calendars.get_holiday_by_id(holiday_id)
        if holiday is None:
            raise TenantHolidayNotFoundError(f"Holiday #{holiday_id} not found.")
        await self._calendars.delete_holiday(holiday)
        await self._uow.commit()
        await recompute_schedule_after_commit(
            self._recompute, after="removing a holiday; the change itself is committed."
        )
        log.info(f"Deleted holiday #{holiday_id}.")
