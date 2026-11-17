"""
CRUD for machine downtime windows: reporting a machine going down,
ending it, editing or removing a record, and listing them with filters.
At most one open window per machine is enforced here (backed by a
partial unique index at the database level too); overlapping closed
windows are rejected here only, see machine_downtime_rules.py for the
pure comparison logic. Ending a window is the one move from open to
closed, so an ended window refuses a second end; its end is corrected by
an edit. An end and an edit read the window under its row lock, so two of
them cannot both find it open. Whatever opens or closes a window, an end or
an edit, publishes MachineDowntimeStarted or MachineDowntimeEnded.
"""

from datetime import datetime

from src.modules.catalogue.domain.errors import ProductionMachineNotFoundError
from src.modules.fulfillment.application.dto.machine_downtime_dto import AddMachineDowntimeCommand
from src.modules.fulfillment.application.dto.machine_downtime_dto import EndMachineDowntimeCommand
from src.modules.fulfillment.application.dto.machine_downtime_dto import MachineDowntimeResult
from src.modules.fulfillment.application.dto.machine_downtime_dto import (
    UpdateMachineDowntimeCommand,
)
from src.modules.fulfillment.application.mappers.machine_downtime_mapper import (
    MachineDowntimeMapper,
)
from src.modules.fulfillment.domain.entities.machine_downtime import MachineDowntime
from src.modules.fulfillment.domain.errors import InvalidDowntimeRangeError
from src.modules.fulfillment.domain.errors import MachineAlreadyDownError
from src.modules.fulfillment.domain.errors import MachineDowntimeAlreadyEndedError
from src.modules.fulfillment.domain.errors import MachineDowntimeNotFoundError
from src.modules.fulfillment.domain.errors import MachineDowntimeOverlapError
from src.modules.fulfillment.domain.events.machine_downtime_events import MachineDowntimeEnded
from src.modules.fulfillment.domain.events.machine_downtime_events import MachineDowntimeStarted
from src.modules.fulfillment.domain.services.machine_downtime_rules import is_valid_range
from src.modules.fulfillment.domain.services.machine_downtime_rules import windows_overlap
from src.modules.fulfillment.domain.services.production_machine_rules import ProductionMachineRules
from src.modules.fulfillment.ports.outbound.repositories.machine_downtime_repository import (
    IMachineDowntimeRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.machine_downtime_repository import (
    MachineDowntimeFilterDto,
)
from src.modules.fulfillment.ports.outbound.repositories.production_machine_repository import (
    IProductionMachineRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.services.schedule_recompute_port import ScheduleRecompute
from src.modules.platform.application.services.schedule_recompute_port import (
    recompute_schedule_after_commit,
)
from src.modules.platform.const import MAX_PAGE_SIZE
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class PaginatedMachineDowntimes:
    def __init__(self, total: int, items: list[MachineDowntimeResult]):
        self.total = total
        self.items = items


class GetMachineDowntimes:
    def __init__(self, downtime_repo: IMachineDowntimeRepository) -> None:
        self._downtimes = downtime_repo

    async def execute(self, filters: MachineDowntimeFilterDto) -> PaginatedMachineDowntimes:
        total, items = await self._downtimes.get_multi(filters)
        return PaginatedMachineDowntimes(
            total=total, items=[MachineDowntimeMapper.to_result(i) for i in items]
        )


class _MachineDowntimeBase:
    def __init__(
        self,
        downtime_repo: IMachineDowntimeRepository,
        machine_repo: IProductionMachineRepository,
        *,
        event_bus: IEventBus,
        uow: IUnitOfWork,
        recompute_schedule: ScheduleRecompute | None = None,
    ) -> None:
        self._downtimes = downtime_repo
        self._machines = machine_repo
        self._bus = event_bus
        self._uow = uow
        self._recompute = recompute_schedule

    async def _assert_no_overlap(
        self,
        machine_id: int,
        started_at: datetime,
        ended_at: datetime | None,
        *,
        exclude_id: int | None = None,
    ) -> None:
        """Every window is compared in Python, not SQL. See
        machine_downtime_rules.windows_overlap. A single machine's
        lifetime downtime history is always small enough to fetch in one
        page (MAX_PAGE_SIZE), unlike the unbounded-table queries the KPI
        repository has to guard against."""
        _, existing = await self._downtimes.get_multi(
            MachineDowntimeFilterDto(machine_id=machine_id, limit=MAX_PAGE_SIZE)
        )
        for row in existing:
            if row.id == exclude_id:
                continue
            if windows_overlap(started_at, ended_at, row.started_at, row.ended_at):
                window = (
                    f"{started_at.isoformat()}–{ended_at.isoformat()}"
                    if ended_at is not None
                    else f"{started_at.isoformat()} (open-ended)"
                )
                raise MachineDowntimeOverlapError(
                    f"Machine #{machine_id} already has downtime #{row.id} overlapping {window}."
                )


class AddMachineDowntime(_MachineDowntimeBase):
    async def execute(self, actor: User, cmd: AddMachineDowntimeCommand) -> MachineDowntimeResult:
        ProductionMachineRules.assert_can_update(actor)
        if not await self._machines.get_by_id(cmd.machine_id):
            raise ProductionMachineNotFoundError(f"Production machine #{cmd.machine_id} not found.")
        if not is_valid_range(cmd.started_at, cmd.ended_at):
            raise InvalidDowntimeRangeError(
                f"Downtime end ({cmd.ended_at}) must be after its start ({cmd.started_at})."
            )
        if cmd.ended_at is None:
            open_by_machine = await self._downtimes.get_open_by_machine_ids([cmd.machine_id])
            existing_open = open_by_machine.get(cmd.machine_id)
            if existing_open is not None:
                raise MachineAlreadyDownError(
                    f"Machine #{cmd.machine_id} already has an open downtime (#{existing_open.id})."
                )
        await self._assert_no_overlap(cmd.machine_id, cmd.started_at, cmd.ended_at)

        now = now_utc()
        downtime = MachineDowntime(
            id=0,
            created=now,
            changed=now,
            changes=append_changelog([], actor.full_name, "Downtime reported."),
            machine_id=cmd.machine_id,
            started_at=cmd.started_at,
            ended_at=cmd.ended_at,
            reason=cmd.reason,
            note=cmd.note,
            reported_by_id=actor.id,
            ended_by_id=actor.id if cmd.ended_at is not None else None,
        )
        saved = await self._downtimes.save(downtime)

        await self._bus.publish(
            MachineDowntimeStarted(
                downtime_id=saved.id,
                machine_id=saved.machine_id,
                reason=saved.reason,
                actor_id=actor.id,
            )
        )
        if cmd.ended_at is not None:
            await self._bus.publish(
                MachineDowntimeEnded(
                    downtime_id=saved.id, machine_id=saved.machine_id, actor_id=actor.id
                )
            )
        await self._uow.commit()
        await recompute_schedule_after_commit(
            self._recompute, after="adding a machine downtime; the change itself is committed."
        )

        log.info(f"Reported machine #{cmd.machine_id} down ({cmd.reason.value}).")
        return MachineDowntimeMapper.to_result(saved)


class EndMachineDowntime(_MachineDowntimeBase):
    async def execute(
        self, actor: User, downtime_id: int, cmd: EndMachineDowntimeCommand
    ) -> MachineDowntimeResult:
        ProductionMachineRules.assert_can_update(actor)
        downtime = found_or_raise(
            await self._downtimes.get_for_update(downtime_id),
            MachineDowntimeNotFoundError,
            f"Downtime #{downtime_id} not found.",
        )
        if downtime.ended_at is not None:
            raise MachineDowntimeAlreadyEndedError(
                f"Downtime #{downtime_id} already ended at {downtime.ended_at.isoformat()}; "
                f"edit it to correct its end."
            )

        ended_at = cmd.ended_at or now_utc()
        if not is_valid_range(downtime.started_at, ended_at):
            raise InvalidDowntimeRangeError(
                f"Downtime end ({ended_at}) must be after its start ({downtime.started_at})."
            )
        await self._assert_no_overlap(
            downtime.machine_id, downtime.started_at, ended_at, exclude_id=downtime.id
        )

        downtime.ended_at = ended_at
        downtime.ended_by_id = actor.id
        downtime.changed = now_utc()
        downtime.changes = append_changelog(downtime.changes, actor.full_name, "Downtime ended.")
        saved = await self._downtimes.save(downtime)

        await self._bus.publish(
            MachineDowntimeEnded(
                downtime_id=saved.id, machine_id=saved.machine_id, actor_id=actor.id
            )
        )
        await self._uow.commit()
        await recompute_schedule_after_commit(
            self._recompute, after="ending a machine downtime; the change itself is committed."
        )

        log.info(f"Ended downtime #{downtime_id}.")
        return MachineDowntimeMapper.to_result(saved)


class UpdateMachineDowntime(_MachineDowntimeBase):
    async def execute(
        self, actor: User, downtime_id: int, cmd: UpdateMachineDowntimeCommand
    ) -> MachineDowntimeResult:
        ProductionMachineRules.assert_can_update(actor)
        downtime = found_or_raise(
            await self._downtimes.get_for_update(downtime_id),
            MachineDowntimeNotFoundError,
            f"Downtime #{downtime_id} not found.",
        )
        if not is_valid_range(cmd.started_at, cmd.ended_at):
            raise InvalidDowntimeRangeError(
                f"Downtime end ({cmd.ended_at}) must be after its start ({cmd.started_at})."
            )
        if cmd.ended_at is None and downtime.ended_at is not None:
            # Reopening a previously closed downtime: still at most one
            # open window per machine.
            open_by_machine = await self._downtimes.get_open_by_machine_ids([downtime.machine_id])
            existing_open = open_by_machine.get(downtime.machine_id)
            if existing_open is not None and existing_open.id != downtime.id:
                raise MachineAlreadyDownError(
                    f"Machine #{downtime.machine_id} already has an open downtime "
                    f"(#{existing_open.id})."
                )
        await self._assert_no_overlap(
            downtime.machine_id, cmd.started_at, cmd.ended_at, exclude_id=downtime.id
        )

        opens = cmd.ended_at is None and downtime.ended_at is not None
        closes = cmd.ended_at is not None and downtime.ended_at is None
        if cmd.ended_at is None:
            downtime.ended_by_id = None
        elif downtime.ended_at is None:
            # Was open, now closed by this edit.
            downtime.ended_by_id = actor.id
        # else stays closed: keep whoever actually ended it.
        downtime.started_at = cmd.started_at
        downtime.ended_at = cmd.ended_at
        downtime.reason = cmd.reason
        downtime.note = cmd.note
        downtime.changed = now_utc()
        downtime.changes = append_changelog(downtime.changes, actor.full_name, "Downtime updated.")
        saved = await self._downtimes.save(downtime)
        if opens:
            await self._bus.publish(
                MachineDowntimeStarted(
                    downtime_id=saved.id,
                    machine_id=saved.machine_id,
                    reason=saved.reason,
                    actor_id=actor.id,
                )
            )
        if closes:
            await self._bus.publish(
                MachineDowntimeEnded(
                    downtime_id=saved.id, machine_id=saved.machine_id, actor_id=actor.id
                )
            )
        await self._uow.commit()
        await recompute_schedule_after_commit(
            self._recompute, after="changing a machine downtime; the change itself is committed."
        )

        log.info(f"Updated downtime #{downtime_id}.")
        return MachineDowntimeMapper.to_result(saved)


class DeleteMachineDowntime(_MachineDowntimeBase):
    async def execute(self, actor: User, downtime_id: int) -> None:
        ProductionMachineRules.assert_can_update(actor)
        downtime = found_or_raise(
            await self._downtimes.get_by_id(downtime_id),
            MachineDowntimeNotFoundError,
            f"Downtime #{downtime_id} not found.",
        )
        await self._downtimes.delete(downtime)
        await self._uow.commit()
        await recompute_schedule_after_commit(
            self._recompute, after="removing a machine downtime; the change itself is committed."
        )
        log.info(f"Deleted downtime #{downtime_id}.")
