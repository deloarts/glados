"""
Unit tests for machine pool catalogue use cases (create, update,
delete, get). No database, no HTTP. All dependencies replaced with
in-memory fakes.
"""

from datetime import date

import pytest

from src.modules.catalogue.domain.errors import ProductionMachineNotFoundError
from src.modules.fulfillment.application.dto.machine_pool_dto import CreateMachinePoolCommand
from src.modules.fulfillment.application.dto.machine_pool_dto import UpdateMachinePoolCommand
from src.modules.fulfillment.application.use_cases.machine_pool.archive_pool import (
    ArchiveMachinePool,
)
from src.modules.fulfillment.application.use_cases.machine_pool.create_pool import CreateMachinePool
from src.modules.fulfillment.application.use_cases.machine_pool.get_pool import GetMachinePool
from src.modules.fulfillment.application.use_cases.machine_pool.get_pool import GetMachinePools
from src.modules.fulfillment.application.use_cases.machine_pool.restore_pool import (
    RestoreMachinePool,
)
from src.modules.fulfillment.application.use_cases.machine_pool.update_pool import UpdateMachinePool
from src.modules.fulfillment.domain.entities.machine_pool import MachinePool
from src.modules.fulfillment.domain.entities.production_machine import ProductionMachine
from src.modules.fulfillment.domain.errors import MachinePoolNotFoundError
from src.modules.fulfillment.domain.events.machine_pool_events import MachinePoolArchived
from src.modules.fulfillment.domain.events.machine_pool_events import MachinePoolCreated
from src.modules.fulfillment.domain.events.machine_pool_events import MachinePoolRestored
from src.modules.fulfillment.domain.events.machine_pool_events import MachinePoolUpdated
from src.modules.fulfillment.ports.outbound.repositories.machine_pool_repository import (
    MachinePoolFilterDto,
)
from src.modules.fulfillment.ports.outbound.repositories.production_machine_repository import (
    ProductionMachineFilterDto,
)
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.fakes import FakeUnitOfWork

# ── Helpers ───────────────────────────────────────────────────────────


def make_production_machine(id: int = 1, internal_name: str = "Mill 1") -> ProductionMachine:
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


def make_pool(
    id: int = 1,
    name: str = "Milling Machines",
    archived: bool = False,
    machine_ids: list[int] | None = None,
) -> MachinePool:
    return MachinePool(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        archived=archived,
        name=name,
        machine_ids=machine_ids if machine_ids is not None else [],
        note=None,
        creator_id=1,
    )


class FakeEventBus:
    def __init__(self):
        self.published = []

    async def publish(self, event):
        self.published.append(event)


class FakeMachinePoolRepository:
    def __init__(self, pools: list[MachinePool] | None = None):
        self._pools: dict[int, MachinePool] = {}
        self._next_id = 1
        for p in pools or []:
            self._pools[p.id] = p
            self._next_id = max(self._next_id, p.id + 1)

    async def get_by_id(self, id: int) -> MachinePool | None:
        return self._pools.get(id)

    async def get_by_ids(self, ids: list[int]) -> list:
        found = [await self.get_by_id(i) for i in ids]
        return [item for item in found if item is not None]

    async def get_multi(self, filters: MachinePoolFilterDto) -> tuple[int, list[MachinePool]]:
        items = list(self._pools.values())
        if not filters.include_archived:
            items = [p for p in items if not p.archived]
        if filters.id is not None:
            items = [p for p in items if p.id == filters.id]
        if filters.machine_id is not None:
            items = [p for p in items if filters.machine_id in p.machine_ids]
        total = len(items)
        skip = filters.skip or 0
        limit = filters.limit
        return total, items[skip : skip + limit if limit else None]

    async def next_sort_order(self) -> int:
        return max((row.sort_order for row in self._pools.values()), default=-1) + 1

    async def save(self, item: MachinePool) -> MachinePool:
        if item.id == 0:
            item.id = self._next_id
            self._next_id += 1
        self._pools[item.id] = item
        return item

    async def delete(self, item: MachinePool) -> None:
        item.archived = True
        await self.save(item)


class FakeProductionMachineRepository:
    def __init__(self, machines: list[ProductionMachine] | None = None):
        self._machines: dict[int, ProductionMachine] = {m.id: m for m in (machines or [])}

    async def get_by_id(self, id: int) -> ProductionMachine | None:
        return self._machines.get(id)

    async def get_by_ids(self, ids: list[int]) -> list:
        found = [await self.get_by_id(i) for i in ids]
        return [item for item in found if item is not None]

    async def get_multi(
        self, filters: ProductionMachineFilterDto
    ) -> tuple[int, list[ProductionMachine]]:
        raise NotImplementedError

    async def save(self, item: ProductionMachine) -> ProductionMachine:
        raise NotImplementedError

    async def delete(self, item: ProductionMachine) -> None:
        raise NotImplementedError


# ── CreateMachinePool ─────────────────────────────────────────────────


class TestCreateMachinePool:
    def setup_method(self):
        self.pool_repo = FakeMachinePoolRepository()
        self.machine_repo = FakeProductionMachineRepository([make_production_machine(id=1)])
        self.actor = make_user(permissions=[Permission.WRITE_MACHINES])
        self.bus = FakeEventBus()
        self.use_case = CreateMachinePool(
            self.pool_repo,
            self.machine_repo,
            event_bus=self.bus,
            uow=FakeUnitOfWork(),
        )

    def _cmd(self, **kwargs) -> CreateMachinePoolCommand:
        defaults = dict(name="Milling Machines")
        defaults.update(kwargs)
        return CreateMachinePoolCommand(**defaults)

    async def test_creates_pool_successfully(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        assert result.name == "Milling Machines"
        assert result.id > 0

    async def test_creates_pool_with_valid_machine_ids(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd(machine_ids=[1]))
        assert result.machine_ids == [1]

    async def test_event_carries_correct_fields(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        (event,) = self.bus.published
        assert isinstance(event, MachinePoolCreated)
        assert event.pool_id == result.id
        assert event.name == "Milling Machines"
        assert event.actor_id == self.actor.id

    async def test_missing_machine_raises(self):
        with pytest.raises(ProductionMachineNotFoundError):
            await self.use_case.execute(actor=self.actor, cmd=self._cmd(machine_ids=[999]))

    async def test_unprivileged_cannot_create(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, cmd=self._cmd())


# ── UpdateMachinePool ─────────────────────────────────────────────────


class TestUpdateMachinePool:
    def setup_method(self):
        self.pool = make_pool(id=1)
        self.pool_repo = FakeMachinePoolRepository([self.pool])
        self.machine_repo = FakeProductionMachineRepository([make_production_machine(id=1)])
        self.actor = make_user(permissions=[Permission.WRITE_MACHINES])
        self.bus = FakeEventBus()
        self.use_case = UpdateMachinePool(
            self.pool_repo,
            self.machine_repo,
            event_bus=self.bus,
            uow=FakeUnitOfWork(),
        )

    async def test_updates_partial_fields_successfully(self):
        result = await self.use_case.execute(
            actor=self.actor,
            pool_id=1,
            cmd=UpdateMachinePoolCommand(name="Turning Machines"),
        )
        assert result.name == "Turning Machines"

    async def test_updates_machine_ids(self):
        result = await self.use_case.execute(
            actor=self.actor,
            pool_id=1,
            cmd=UpdateMachinePoolCommand(machine_ids=[1]),
        )
        assert result.machine_ids == [1]

    async def test_missing_machine_raises(self):
        with pytest.raises(ProductionMachineNotFoundError):
            await self.use_case.execute(
                actor=self.actor,
                pool_id=1,
                cmd=UpdateMachinePoolCommand(machine_ids=[999]),
            )

    async def test_event_carries_correct_fields(self):
        result = await self.use_case.execute(
            actor=self.actor,
            pool_id=1,
            cmd=UpdateMachinePoolCommand(name="Turning Machines"),
        )
        (event,) = self.bus.published
        assert isinstance(event, MachinePoolUpdated)
        assert event.pool_id == result.id
        assert event.name == "Turning Machines"

    async def test_not_found_raises(self):
        with pytest.raises(MachinePoolNotFoundError):
            await self.use_case.execute(
                actor=self.actor, pool_id=999, cmd=UpdateMachinePoolCommand()
            )

    async def test_unprivileged_cannot_update(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, pool_id=1, cmd=UpdateMachinePoolCommand())


# ── ArchiveMachinePool / RestoreMachinePool ───────────────────────────


class TestArchiveMachinePool:
    def setup_method(self):
        self.pool = make_pool(id=1)
        self.pool_repo = FakeMachinePoolRepository([self.pool])
        self.actor = make_user(permissions=[Permission.WRITE_MACHINES])
        self.bus = FakeEventBus()
        self.use_case = ArchiveMachinePool(self.pool_repo, event_bus=self.bus, uow=FakeUnitOfWork())

    async def test_archives_successfully(self):
        result = await self.use_case.execute(actor=self.actor, pool_id=1)
        assert result.archived is True

    async def test_archiving_twice_is_idempotent(self):
        await self.use_case.execute(actor=self.actor, pool_id=1)
        result = await self.use_case.execute(actor=self.actor, pool_id=1)
        assert result.archived is True

    async def test_archived_pool_excluded_from_get_multi_by_default(self):
        await self.use_case.execute(actor=self.actor, pool_id=1)
        total, items = await self.pool_repo.get_multi(MachinePoolFilterDto())
        assert total == 0
        assert items == []

    async def test_archived_pool_included_when_requested(self):
        await self.use_case.execute(actor=self.actor, pool_id=1)
        total, _items = await self.pool_repo.get_multi(MachinePoolFilterDto(include_archived=True))
        assert total == 1

    async def test_archived_pool_still_resolves_by_id(self):
        await self.use_case.execute(actor=self.actor, pool_id=1)
        assert await self.pool_repo.get_by_id(1) is not None

    async def test_event_carries_correct_fields(self):
        await self.use_case.execute(actor=self.actor, pool_id=1)
        (event,) = self.bus.published
        assert isinstance(event, MachinePoolArchived)
        assert event.pool_id == 1

    async def test_not_found_raises(self):
        with pytest.raises(MachinePoolNotFoundError):
            await self.use_case.execute(actor=self.actor, pool_id=999)

    async def test_unprivileged_cannot_archive(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, pool_id=1)


class TestRestoreMachinePool:
    def setup_method(self):
        self.actor = make_user(permissions=[Permission.WRITE_MACHINES])
        self.bus = FakeEventBus()

    async def test_restores_successfully(self):
        pool = make_pool(id=1, archived=True)
        repo = FakeMachinePoolRepository([pool])
        result = await RestoreMachinePool(repo, event_bus=self.bus, uow=FakeUnitOfWork()).execute(
            actor=self.actor, pool_id=1
        )
        assert result.archived is False

    async def test_restoring_twice_is_idempotent(self):
        pool = make_pool(id=1, archived=True)
        repo = FakeMachinePoolRepository([pool])
        use_case = RestoreMachinePool(repo, event_bus=self.bus, uow=FakeUnitOfWork())
        await use_case.execute(actor=self.actor, pool_id=1)
        result = await use_case.execute(actor=self.actor, pool_id=1)
        assert result.archived is False

    async def test_event_carries_correct_fields(self):
        pool = make_pool(id=1, archived=True)
        repo = FakeMachinePoolRepository([pool])
        await RestoreMachinePool(repo, event_bus=self.bus, uow=FakeUnitOfWork()).execute(
            actor=self.actor, pool_id=1
        )
        (event,) = self.bus.published
        assert isinstance(event, MachinePoolRestored)
        assert event.pool_id == 1

    async def test_not_found_raises(self):
        repo = FakeMachinePoolRepository([])
        with pytest.raises(MachinePoolNotFoundError):
            await RestoreMachinePool(repo, event_bus=self.bus, uow=FakeUnitOfWork()).execute(
                actor=self.actor, pool_id=999
            )

    async def test_unprivileged_cannot_restore(self):
        pool = make_pool(id=1, archived=True)
        repo = FakeMachinePoolRepository([pool])
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await RestoreMachinePool(repo, event_bus=self.bus, uow=FakeUnitOfWork()).execute(
                actor=actor, pool_id=1
            )


# ── GetMachinePool / GetMachinePools ──────────────────────────────────


class TestGetMachinePool:
    def setup_method(self):
        self.pool_repo = FakeMachinePoolRepository([make_pool(id=1)])
        self.use_case = GetMachinePool(self.pool_repo)

    async def test_returns_pool_when_found(self):
        result = await self.use_case.execute(pool_id=1)
        assert result.id == 1
        assert result.name == "Milling Machines"

    async def test_not_found_raises(self):
        with pytest.raises(MachinePoolNotFoundError):
            await self.use_case.execute(pool_id=999)


class TestGetMachinePools:
    def setup_method(self):
        self.pool_repo = FakeMachinePoolRepository(
            [
                make_pool(id=1, name="Milling Machines", machine_ids=[1]),
                make_pool(id=2, name="Turning Machines", machine_ids=[2]),
            ]
        )
        self.use_case = GetMachinePools(self.pool_repo)

    async def test_lists_all_pools(self):
        result = await self.use_case.execute(MachinePoolFilterDto())
        assert result.total == 2
        assert {p.name for p in result.items} == {"Milling Machines", "Turning Machines"}

    async def test_filters_by_machine_id(self):
        result = await self.use_case.execute(MachinePoolFilterDto(machine_id=2))
        assert result.total == 1
        assert result.items[0].name == "Turning Machines"

    async def test_filters_by_id(self):
        result = await self.use_case.execute(MachinePoolFilterDto(id=1))
        assert result.total == 1
        assert result.items[0].id == 1
