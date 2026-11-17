"""
Unit tests for machine downtime use cases (add, end, update, delete,
list): open-downtime uniqueness, overlap rejection, range validation,
and that ending a downtime stamps ended_at/ended_by. No database, no
HTTP, all dependencies replaced with in-memory fakes.
"""

from datetime import UTC
from datetime import datetime

import pytest

from src.modules.catalogue.domain.errors import ProductionMachineNotFoundError
from src.modules.fulfillment.application.dto.machine_downtime_dto import AddMachineDowntimeCommand
from src.modules.fulfillment.application.dto.machine_downtime_dto import EndMachineDowntimeCommand
from src.modules.fulfillment.application.dto.machine_downtime_dto import (
    UpdateMachineDowntimeCommand,
)
from src.modules.fulfillment.application.use_cases.production_machine.downtimes import (
    AddMachineDowntime,
)
from src.modules.fulfillment.application.use_cases.production_machine.downtimes import (
    DeleteMachineDowntime,
)
from src.modules.fulfillment.application.use_cases.production_machine.downtimes import (
    EndMachineDowntime,
)
from src.modules.fulfillment.application.use_cases.production_machine.downtimes import (
    GetMachineDowntimes,
)
from src.modules.fulfillment.application.use_cases.production_machine.downtimes import (
    UpdateMachineDowntime,
)
from src.modules.fulfillment.domain.entities.machine_downtime import MachineDowntime
from src.modules.fulfillment.domain.entities.production_machine import ProductionMachine
from src.modules.fulfillment.domain.errors import InvalidDowntimeRangeError
from src.modules.fulfillment.domain.errors import MachineAlreadyDownError
from src.modules.fulfillment.domain.errors import MachineDowntimeAlreadyEndedError
from src.modules.fulfillment.domain.errors import MachineDowntimeNotFoundError
from src.modules.fulfillment.domain.errors import MachineDowntimeOverlapError
from src.modules.fulfillment.domain.events.machine_downtime_events import MachineDowntimeEnded
from src.modules.fulfillment.domain.events.machine_downtime_events import MachineDowntimeStarted
from src.modules.fulfillment.domain.value_objects.machine_downtime_reason import (
    MachineDowntimeReason,
)
from src.modules.fulfillment.ports.outbound.repositories.machine_downtime_repository import (
    MachineDowntimeFilterDto,
)
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.fakes import FakeEventBus
from tests.unit.fakes import FakeUnitOfWork

# ── Helpers ───────────────────────────────────────────────────────────


def make_machine(id: int = 1, internal_name: str = "Mill 1") -> ProductionMachine:
    from datetime import date

    return ProductionMachine(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        archived=False,
        internal_name=internal_name,
        vendor="Contoso",
        model="VF-2",
        fabrication_method_ids=[],
        max_part_dimension=None,
        note=None,
        creator_id=1,
    )


def make_downtime(
    id: int = 1,
    machine_id: int = 1,
    started_at: datetime = datetime(2026, 1, 1, 8, 0, tzinfo=UTC),
    ended_at: datetime | None = None,
    reason: MachineDowntimeReason = MachineDowntimeReason.BREAKDOWN,
) -> MachineDowntime:
    return MachineDowntime(
        id=id,
        created=started_at,
        changed=started_at,
        changes=[],
        machine_id=machine_id,
        started_at=started_at,
        ended_at=ended_at,
        reason=reason,
        note=None,
        reported_by_id=1,
        ended_by_id=None,
        machine_internal_name="Mill 1",
        reported_by_full_name="Test User",
    )


class FakeProductionMachineRepository:
    def __init__(self, machines: list[ProductionMachine] | None = None):
        self._machines = {m.id: m for m in (machines or [])}

    async def get_by_id(self, id: int) -> ProductionMachine | None:
        return self._machines.get(id)

    async def get_by_ids(self, ids: list[int]) -> list:
        found = [await self.get_by_id(i) for i in ids]
        return [item for item in found if item is not None]


class FakeMachineDowntimeRepository:
    def __init__(self, rows: list[MachineDowntime] | None = None):
        self._rows: dict[int, MachineDowntime] = {r.id: r for r in (rows or [])}
        self._next_id = max([r.id for r in (rows or [])], default=0) + 1
        self.locked: list[int] = []

    async def get_by_id(self, id: int) -> MachineDowntime | None:
        return self._rows.get(id)

    async def get_for_update(self, id: int) -> MachineDowntime | None:
        self.locked.append(id)
        return self._rows.get(id)

    async def get_multi(
        self, filters: MachineDowntimeFilterDto
    ) -> tuple[int, list[MachineDowntime]]:
        items = list(self._rows.values())
        if filters.machine_id is not None:
            items = [r for r in items if r.machine_id == filters.machine_id]
        return len(items), items

    async def get_open_by_machine_ids(
        self, machine_ids: list[int], *, started_by: datetime | None = None
    ) -> dict[int, MachineDowntime]:
        return {
            r.machine_id: r
            for r in self._rows.values()
            if r.machine_id in machine_ids
            and r.ended_at is None
            and (started_by is None or r.started_at <= started_by)
        }

    async def minutes_by_machine_in_period(
        self, machine_ids: list[int], start: datetime, end: datetime
    ) -> dict[int, int]:
        raise NotImplementedError

    async def save(self, item: MachineDowntime) -> MachineDowntime:
        if item.id == 0:
            item.id = self._next_id
            self._next_id += 1
        self._rows[item.id] = item
        return item

    async def delete(self, item: MachineDowntime) -> None:
        self._rows.pop(item.id, None)


# ── AddMachineDowntime ───────────────────────────────────────────────


class TestAddMachineDowntime:
    def setup_method(self):
        self.machine_repo = FakeProductionMachineRepository([make_machine(id=1)])
        self.downtime_repo = FakeMachineDowntimeRepository()
        self.actor = make_user(permissions=[Permission.WRITE_MACHINES])
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()
        self.use_case = AddMachineDowntime(
            self.downtime_repo, self.machine_repo, event_bus=self.bus, uow=self.uow
        )

    def _cmd(self, **kwargs) -> AddMachineDowntimeCommand:
        defaults = dict(
            machine_id=1,
            started_at=datetime(2026, 1, 1, 8, 0, tzinfo=UTC),
            reason=MachineDowntimeReason.BREAKDOWN,
        )
        defaults.update(kwargs)
        return AddMachineDowntimeCommand(**defaults)

    async def test_adds_open_downtime(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        assert result.machine_id == 1
        assert result.ended_at is None
        assert result.reason == MachineDowntimeReason.BREAKDOWN.value
        assert self.uow.commits == 1

    async def test_publishes_started_event(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        (event,) = self.bus.published
        assert isinstance(event, MachineDowntimeStarted)
        assert event.downtime_id == result.id
        assert event.machine_id == 1
        assert event.actor_id == self.actor.id

    async def test_closed_downtime_publishes_both_events(self):
        await self.use_case.execute(
            actor=self.actor,
            cmd=self._cmd(ended_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC)),
        )
        kinds = [type(e) for e in self.bus.published]
        assert kinds == [MachineDowntimeStarted, MachineDowntimeEnded]

    async def test_machine_not_found_raises(self):
        with pytest.raises(ProductionMachineNotFoundError):
            await self.use_case.execute(actor=self.actor, cmd=self._cmd(machine_id=999))

    async def test_second_open_downtime_on_same_machine_raises(self):
        await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        with pytest.raises(MachineAlreadyDownError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=self._cmd(started_at=datetime(2026, 1, 2, 8, 0, tzinfo=UTC)),
            )

    async def test_overlapping_closed_downtime_raises(self):
        await self.use_case.execute(
            actor=self.actor,
            cmd=self._cmd(
                started_at=datetime(2026, 1, 1, 8, 0, tzinfo=UTC),
                ended_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
            ),
        )
        with pytest.raises(MachineDowntimeOverlapError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=self._cmd(
                    started_at=datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
                    ended_at=datetime(2026, 1, 1, 14, 0, tzinfo=UTC),
                ),
            )

    async def test_non_overlapping_closed_downtime_succeeds(self):
        await self.use_case.execute(
            actor=self.actor,
            cmd=self._cmd(
                started_at=datetime(2026, 1, 1, 8, 0, tzinfo=UTC),
                ended_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
            ),
        )
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=self._cmd(
                started_at=datetime(2026, 1, 1, 13, 0, tzinfo=UTC),
                ended_at=datetime(2026, 1, 1, 14, 0, tzinfo=UTC),
            ),
        )
        assert result.id != 0

    async def test_end_before_start_raises(self):
        with pytest.raises(InvalidDowntimeRangeError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=self._cmd(
                    started_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
                    ended_at=datetime(2026, 1, 1, 8, 0, tzinfo=UTC),
                ),
            )

    async def test_unprivileged_cannot_add(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, cmd=self._cmd())


# ── EndMachineDowntime ───────────────────────────────────────────────


class TestEndMachineDowntime:
    def setup_method(self):
        self.downtime = make_downtime(id=1, machine_id=1)
        self.downtime_repo = FakeMachineDowntimeRepository([self.downtime])
        self.machine_repo = FakeProductionMachineRepository([make_machine(id=1)])
        self.actor = make_user(id=2, username="ender", permissions=[Permission.WRITE_MACHINES])
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()
        self.use_case = EndMachineDowntime(
            self.downtime_repo, self.machine_repo, event_bus=self.bus, uow=self.uow
        )

    async def test_end_sets_ended_at_and_actor(self):
        result = await self.use_case.execute(
            actor=self.actor,
            downtime_id=1,
            cmd=EndMachineDowntimeCommand(ended_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC)),
        )
        assert result.ended_at == datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        assert result.ended_by_id == self.actor.id

    async def test_end_defaults_to_now_when_omitted(self):
        result = await self.use_case.execute(
            actor=self.actor, downtime_id=1, cmd=EndMachineDowntimeCommand()
        )
        assert result.ended_at is not None

    async def test_publishes_ended_event(self):
        await self.use_case.execute(
            actor=self.actor,
            downtime_id=1,
            cmd=EndMachineDowntimeCommand(ended_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC)),
        )
        (event,) = self.bus.published
        assert isinstance(event, MachineDowntimeEnded)
        assert event.downtime_id == 1
        assert event.actor_id == self.actor.id

    async def test_end_before_start_raises(self):
        with pytest.raises(InvalidDowntimeRangeError):
            await self.use_case.execute(
                actor=self.actor,
                downtime_id=1,
                cmd=EndMachineDowntimeCommand(ended_at=datetime(2026, 1, 1, 7, 0, tzinfo=UTC)),
            )

    async def test_not_found_raises(self):
        with pytest.raises(MachineDowntimeNotFoundError):
            await self.use_case.execute(
                actor=self.actor, downtime_id=999, cmd=EndMachineDowntimeCommand()
            )

    async def test_end_reads_the_downtime_under_its_row_lock(self):
        await self.use_case.execute(
            actor=self.actor,
            downtime_id=1,
            cmd=EndMachineDowntimeCommand(ended_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC)),
        )
        assert self.downtime_repo.locked == [1]

    async def test_ending_an_ended_downtime_is_refused(self):
        ended_at = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
        self.downtime.ended_at = ended_at
        with pytest.raises(MachineDowntimeAlreadyEndedError):
            await self.use_case.execute(
                actor=self.actor,
                downtime_id=1,
                cmd=EndMachineDowntimeCommand(ended_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC)),
            )
        assert self.downtime_repo._rows[1].ended_at == ended_at
        assert self.bus.published == []
        assert self.uow.commits == 0

    async def test_ending_into_another_window_is_refused(self):
        await self.downtime_repo.save(
            make_downtime(
                id=2,
                machine_id=1,
                started_at=datetime(2026, 1, 1, 14, 0, tzinfo=UTC),
                ended_at=datetime(2026, 1, 1, 16, 0, tzinfo=UTC),
            )
        )
        with pytest.raises(MachineDowntimeOverlapError):
            await self.use_case.execute(
                actor=self.actor,
                downtime_id=1,
                cmd=EndMachineDowntimeCommand(ended_at=datetime(2026, 1, 1, 15, 0, tzinfo=UTC)),
            )
        assert self.downtime_repo._rows[1].ended_at is None
        assert self.bus.published == []


# ── UpdateMachineDowntime ────────────────────────────────────────────


class TestUpdateMachineDowntime:
    def setup_method(self):
        self.downtime = make_downtime(id=1, machine_id=1)
        self.downtime_repo = FakeMachineDowntimeRepository([self.downtime])
        self.machine_repo = FakeProductionMachineRepository([make_machine(id=1)])
        self.actor = make_user(permissions=[Permission.WRITE_MACHINES])
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()
        self.use_case = UpdateMachineDowntime(
            self.downtime_repo, self.machine_repo, event_bus=self.bus, uow=self.uow
        )

    async def test_updates_reason_and_note(self):
        result = await self.use_case.execute(
            actor=self.actor,
            downtime_id=1,
            cmd=UpdateMachineDowntimeCommand(
                started_at=self.downtime.started_at,
                reason=MachineDowntimeReason.TOOLING,
                note="Tool change",
            ),
        )
        assert result.reason == MachineDowntimeReason.TOOLING.value
        assert result.note == "Tool change"

    async def test_range_change_checked_for_overlap(self):
        other = make_downtime(
            id=2,
            machine_id=1,
            started_at=datetime(2026, 1, 2, 8, 0, tzinfo=UTC),
            ended_at=datetime(2026, 1, 2, 12, 0, tzinfo=UTC),
        )
        await self.downtime_repo.save(other)
        # Close the row under test first so both are closed ranges.
        self.downtime.ended_at = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        with pytest.raises(MachineDowntimeOverlapError):
            await self.use_case.execute(
                actor=self.actor,
                downtime_id=1,
                cmd=UpdateMachineDowntimeCommand(
                    started_at=datetime(2026, 1, 2, 10, 0, tzinfo=UTC),
                    ended_at=datetime(2026, 1, 2, 14, 0, tzinfo=UTC),
                    reason=MachineDowntimeReason.BREAKDOWN,
                ),
            )

    async def test_not_found_raises(self):
        with pytest.raises(MachineDowntimeNotFoundError):
            await self.use_case.execute(
                actor=self.actor,
                downtime_id=999,
                cmd=UpdateMachineDowntimeCommand(
                    started_at=self.downtime.started_at, reason=MachineDowntimeReason.OTHER
                ),
            )

    async def test_update_reads_the_downtime_under_its_row_lock(self):
        await self.use_case.execute(
            actor=self.actor,
            downtime_id=1,
            cmd=UpdateMachineDowntimeCommand(
                started_at=self.downtime.started_at, reason=MachineDowntimeReason.TOOLING
            ),
        )
        assert self.downtime_repo.locked == [1]

    async def test_closing_an_open_window_publishes_ended(self):
        await self.use_case.execute(
            actor=self.actor,
            downtime_id=1,
            cmd=UpdateMachineDowntimeCommand(
                started_at=self.downtime.started_at,
                ended_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
                reason=MachineDowntimeReason.BREAKDOWN,
            ),
        )
        (event,) = self.bus.published
        assert isinstance(event, MachineDowntimeEnded)
        assert (event.downtime_id, event.machine_id) == (1, 1)

    async def test_reopening_a_closed_window_publishes_started(self):
        self.downtime.ended_at = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        await self.use_case.execute(
            actor=self.actor,
            downtime_id=1,
            cmd=UpdateMachineDowntimeCommand(
                started_at=self.downtime.started_at, reason=MachineDowntimeReason.TOOLING
            ),
        )
        (event,) = self.bus.published
        assert isinstance(event, MachineDowntimeStarted)
        assert (event.downtime_id, event.reason) == (1, MachineDowntimeReason.TOOLING.value)

    async def test_an_edit_that_keeps_the_window_open_publishes_nothing(self):
        await self.use_case.execute(
            actor=self.actor,
            downtime_id=1,
            cmd=UpdateMachineDowntimeCommand(
                started_at=self.downtime.started_at, reason=MachineDowntimeReason.TOOLING
            ),
        )
        assert self.bus.published == []


# ── DeleteMachineDowntime ────────────────────────────────────────────


class TestDeleteMachineDowntime:
    def setup_method(self):
        self.downtime = make_downtime(id=1, machine_id=1)
        self.downtime_repo = FakeMachineDowntimeRepository([self.downtime])
        self.machine_repo = FakeProductionMachineRepository([make_machine(id=1)])
        self.actor = make_user(permissions=[Permission.WRITE_MACHINES])
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()
        self.use_case = DeleteMachineDowntime(
            self.downtime_repo, self.machine_repo, event_bus=self.bus, uow=self.uow
        )

    async def test_deletes_downtime(self):
        await self.use_case.execute(actor=self.actor, downtime_id=1)
        assert await self.downtime_repo.get_by_id(1) is None

    async def test_not_found_raises(self):
        with pytest.raises(MachineDowntimeNotFoundError):
            await self.use_case.execute(actor=self.actor, downtime_id=999)


# ── GetMachineDowntimes ──────────────────────────────────────────────


class TestGetMachineDowntimes:
    async def test_lists_downtimes_for_machine(self):
        repo = FakeMachineDowntimeRepository(
            [make_downtime(id=1, machine_id=1), make_downtime(id=2, machine_id=2)]
        )
        result = await GetMachineDowntimes(repo).execute(MachineDowntimeFilterDto(machine_id=1))
        assert result.total == 1
        assert result.items[0].machine_id == 1
