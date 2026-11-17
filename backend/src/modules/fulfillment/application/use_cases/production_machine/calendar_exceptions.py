"""
CRUD for a machine's per-date calendar exceptions, holidays,
maintenance windows, extra shifts. Always applies on top of whichever
weekly template is in effect underneath (own override or global default).
"""

from src.modules.catalogue.domain.errors import ProductionMachineNotFoundError
from src.modules.fulfillment.application.dto.machine_calendar_dto import (
    CreateMachineCalendarExceptionCommand,
)
from src.modules.fulfillment.application.dto.machine_calendar_dto import (
    MachineCalendarExceptionResult,
)
from src.modules.fulfillment.application.dto.machine_calendar_dto import (
    UpdateMachineCalendarExceptionCommand,
)
from src.modules.fulfillment.application.mappers.machine_calendar_mapper import (
    MachineCalendarExceptionMapper,
)
from src.modules.fulfillment.domain.entities.machine_calendar_exception import (
    MachineCalendarException,
)
from src.modules.fulfillment.domain.errors import MachineCalendarExceptionNotFoundError
from src.modules.fulfillment.domain.services.production_machine_rules import ProductionMachineRules
from src.modules.fulfillment.domain.value_objects.work_interval import clock_minute
from src.modules.fulfillment.ports.outbound.repositories.machine_calendar_repository import (
    IMachineCalendarRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_machine_repository import (
    IProductionMachineRepository,
)
from src.modules.platform.application.services.schedule_recompute_port import ScheduleRecompute
from src.modules.platform.application.services.schedule_recompute_port import (
    recompute_schedule_after_commit,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InvalidScheduleCalendarError
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class GetMachineCalendarExceptions:
    def __init__(self, calendar_repo: IMachineCalendarRepository) -> None:
        self._calendars = calendar_repo

    async def execute(self, machine_id: int) -> list[MachineCalendarExceptionResult]:
        items = await self._calendars.get_exceptions_by_machine_id(machine_id)
        return [MachineCalendarExceptionMapper.to_result(i) for i in items]


class CreateMachineCalendarException:
    def __init__(
        self,
        calendar_repo: IMachineCalendarRepository,
        machine_repo: IProductionMachineRepository,
        *,
        uow: IUnitOfWork,
        recompute_schedule: ScheduleRecompute | None = None,
    ) -> None:
        self._calendars = calendar_repo
        self._machines = machine_repo
        self._uow = uow
        self._recompute = recompute_schedule

    async def execute(
        self, actor: User, machine_id: int, cmd: CreateMachineCalendarExceptionCommand
    ) -> MachineCalendarExceptionResult:
        ProductionMachineRules.assert_can_update(actor)
        if not await self._machines.get_by_id(machine_id):
            raise ProductionMachineNotFoundError(f"Production machine #{machine_id} not found.")
        if await self._calendars.get_exception_by_machine_and_date(machine_id, cmd.exception_date):
            raise InvalidScheduleCalendarError(
                f"Machine #{machine_id} already has a calendar exception for "
                f"{cmd.exception_date.isoformat()}."
            )

        now = now_utc()
        item = MachineCalendarException(
            id=0,
            created=now,
            changed=now,
            changes=append_changelog([], actor.full_name, "Calendar exception created."),
            exception_date=cmd.exception_date,
            available_minutes=cmd.available_minutes,
            note=cmd.note,
            creator_id=actor.id,
            machine_id=machine_id,
            start_minute=clock_minute(cmd.start),
        )
        saved = await self._calendars.save_exception(item)
        await self._uow.commit()
        await recompute_schedule_after_commit(
            self._recompute, after="adding a calendar exception; the change itself is committed."
        )
        log.info(
            f"Added a calendar exception for machine #{machine_id} "
            f"on {cmd.exception_date.isoformat()}."
        )
        return MachineCalendarExceptionMapper.to_result(saved)


class UpdateMachineCalendarException:
    def __init__(
        self,
        calendar_repo: IMachineCalendarRepository,
        *,
        uow: IUnitOfWork,
        recompute_schedule: ScheduleRecompute | None = None,
    ) -> None:
        self._calendars = calendar_repo
        self._uow = uow
        self._recompute = recompute_schedule

    async def execute(
        self, actor: User, exception_id: int, cmd: UpdateMachineCalendarExceptionCommand
    ) -> MachineCalendarExceptionResult:
        ProductionMachineRules.assert_can_update(actor)
        item = await self._calendars.get_exception_by_id(exception_id)
        if not item:
            raise MachineCalendarExceptionNotFoundError(
                f"Calendar exception #{exception_id} not found."
            )

        item.available_minutes = cmd.available_minutes
        item.start_minute = clock_minute(cmd.start)
        item.note = cmd.note
        item.changed = now_utc()
        item.changes = append_changelog(
            item.changes, actor.full_name, "Calendar exception updated."
        )

        saved = await self._calendars.save_exception(item)
        await self._uow.commit()
        await recompute_schedule_after_commit(
            self._recompute, after="changing a calendar exception; the change itself is committed."
        )
        log.info(f"Updated calendar exception #{exception_id}.")
        return MachineCalendarExceptionMapper.to_result(saved)


class DeleteMachineCalendarException:
    def __init__(
        self,
        calendar_repo: IMachineCalendarRepository,
        *,
        uow: IUnitOfWork,
        recompute_schedule: ScheduleRecompute | None = None,
    ) -> None:
        self._calendars = calendar_repo
        self._uow = uow
        self._recompute = recompute_schedule

    async def execute(self, actor: User, exception_id: int) -> None:
        ProductionMachineRules.assert_can_update(actor)
        item = await self._calendars.get_exception_by_id(exception_id)
        if not item:
            raise MachineCalendarExceptionNotFoundError(
                f"Calendar exception #{exception_id} not found."
            )
        await self._calendars.delete_exception(item)
        await self._uow.commit()
        await recompute_schedule_after_commit(
            self._recompute, after="removing a calendar exception; the change itself is committed."
        )
        log.info(f"Deleted calendar exception #{exception_id}.")
