"""
CRUD for a machine's own weekly-hours override. At most one row
per machine, SetMachineWorkingHours upserts; DeleteMachineWorkingHours
reverts the machine to AdminProductionSettings.default_weekly_hours.

The default calendar itself, the weekly hours of every machine without an
override and of manual work, is read and written here too. It lives in the
production settings, but changing it is machine work, so it needs the
right to edit machines rather than the settings right.
"""

from dataclasses import replace

from src.modules.catalogue.domain.errors import ProductionMachineNotFoundError
from src.modules.fulfillment.application.dto.machine_calendar_dto import MachineWorkingHoursResult
from src.modules.fulfillment.application.dto.machine_calendar_dto import (
    SetMachineWorkingHoursCommand,
)
from src.modules.fulfillment.application.dto.machine_calendar_dto import WorkIntervalDto
from src.modules.fulfillment.application.mappers.machine_calendar_mapper import (
    MachineWorkingHoursMapper,
)
from src.modules.fulfillment.application.mappers.machine_calendar_mapper import (
    weekly_hours_from_dto,
)
from src.modules.fulfillment.application.mappers.machine_calendar_mapper import weekly_hours_to_dto
from src.modules.fulfillment.domain.entities.machine_working_hours import MachineWorkingHours
from src.modules.fulfillment.domain.errors import MachineWorkingHoursNotFoundError
from src.modules.fulfillment.domain.services.production_machine_rules import ProductionMachineRules
from src.modules.fulfillment.domain.services.scheduling import validate_weekly_hours
from src.modules.fulfillment.ports.outbound.fulfillment_settings_repository import (
    IFulfillmentSettingsRepository,
)
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
from src.modules.platform.domain.entities.admin_settings.audit import AdminSettingsAuditEntry
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class GetMachineWorkingHours:
    def __init__(self, calendar_repo: IMachineCalendarRepository) -> None:
        self._calendars = calendar_repo

    async def execute(self, machine_id: int) -> MachineWorkingHoursResult | None:
        item = await self._calendars.get_working_hours_by_machine_id(machine_id)
        return MachineWorkingHoursMapper.to_result(item) if item else None


class SetMachineWorkingHours:
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
        self, actor: User, machine_id: int, cmd: SetMachineWorkingHoursCommand
    ) -> MachineWorkingHoursResult:
        ProductionMachineRules.assert_can_update(actor)
        if not await self._machines.get_by_id(machine_id):
            raise ProductionMachineNotFoundError(f"Production machine #{machine_id} not found.")
        weekly_hours = weekly_hours_from_dto(cmd.weekly_hours)
        validate_weekly_hours(weekly_hours)

        now = now_utc()
        existing = await self._calendars.get_working_hours_by_machine_id(machine_id)
        item = MachineWorkingHours(
            id=existing.id if existing else 0,
            created=existing.created if existing else now,
            changed=now,
            changes=append_changelog(
                existing.changes if existing else [], actor.full_name, "Working hours updated."
            ),
            weekly_hours=weekly_hours,
            creator_id=existing.creator_id if existing else actor.id,
            machine_id=machine_id,
        )
        saved = await self._calendars.save_working_hours(item)
        await self._uow.commit()
        await recompute_schedule_after_commit(
            self._recompute, after="setting machine working hours; the change itself is committed."
        )
        log.info(f"Set working hours for machine #{machine_id}.")
        return MachineWorkingHoursMapper.to_result(saved)


class DeleteMachineWorkingHours:
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

    async def execute(self, actor: User, machine_id: int) -> None:
        ProductionMachineRules.assert_can_update(actor)
        existing = await self._calendars.get_working_hours_by_machine_id(machine_id)
        if not existing:
            raise MachineWorkingHoursNotFoundError(
                f"Machine #{machine_id} has no working hours override to remove."
            )
        await self._calendars.delete_working_hours(existing)
        await self._uow.commit()
        await recompute_schedule_after_commit(
            self._recompute, after="removing machine working hours; the change itself is committed."
        )
        log.info(
            f"Removed the working hours override for "
            f"machine #{machine_id} (reverts to the global default)."
        )


class GetDefaultWorkingHours:
    def __init__(self, settings_repo: IFulfillmentSettingsRepository) -> None:
        self._settings = settings_repo

    async def execute(self) -> dict[int, list[WorkIntervalDto]]:
        return weekly_hours_to_dto((await self._settings.get_production()).default_weekly_hours)


class SetDefaultWorkingHours:
    def __init__(
        self,
        settings_repo: IFulfillmentSettingsRepository,
        *,
        uow: IUnitOfWork,
        recompute_schedule: ScheduleRecompute | None = None,
    ) -> None:
        self._settings = settings_repo
        self._uow = uow
        self._recompute = recompute_schedule

    async def execute(
        self, actor: User, cmd: SetMachineWorkingHoursCommand
    ) -> dict[int, list[WorkIntervalDto]]:
        ProductionMachineRules.assert_can_update(actor)
        weekly_hours = weekly_hours_from_dto(cmd.weekly_hours)
        validate_weekly_hours(weekly_hours)

        current = await self._settings.get_production()
        saved = await self._settings.save_production(
            replace(current, default_weekly_hours=weekly_hours)
        )
        await self._settings.append_audit(
            AdminSettingsAuditEntry.by_actor(
                actor,
                settings_domain="production",
                summary=f"Default calendar updated by {actor.username}.",
            )
        )
        await self._uow.commit()
        await recompute_schedule_after_commit(
            self._recompute,
            after="changing the default calendar; the change itself is committed.",
        )
        log.info("Updated the default calendar.")
        return weekly_hours_to_dto(saved.default_weekly_hours)
