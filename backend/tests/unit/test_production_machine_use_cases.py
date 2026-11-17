"""
Unit tests for production machine catalogue use cases (create, update,
delete, get). No database, no HTTP. All dependencies replaced with
in-memory fakes.
"""

from datetime import UTC
from datetime import date
from datetime import datetime

import pytest

from src.modules.catalogue.domain.entities.fabrication_method import FabricationMethod
from src.modules.catalogue.domain.errors import FabricationMethodNotFoundError
from src.modules.catalogue.domain.errors import ProductionMachineNotFoundError
from src.modules.catalogue.ports.outbound.repositories.fabrication_method_repository import (
    FabricationMethodFilterDto,
)
from src.modules.fulfillment.application.dto.production_machine_dto import (
    CreateProductionMachineCommand,
)
from src.modules.fulfillment.application.dto.production_machine_dto import (
    UpdateProductionMachineCommand,
)
from src.modules.fulfillment.application.use_cases.production_machine.archive_machine import (
    ArchiveProductionMachine,
)
from src.modules.fulfillment.application.use_cases.production_machine.create_machine import (
    CreateProductionMachine,
)
from src.modules.fulfillment.application.use_cases.production_machine.get_machine import (
    GetProductionMachine,
)
from src.modules.fulfillment.application.use_cases.production_machine.get_machine import (
    GetProductionMachines,
)
from src.modules.fulfillment.application.use_cases.production_machine.restore_machine import (
    RestoreProductionMachine,
)
from src.modules.fulfillment.application.use_cases.production_machine.update_machine import (
    UpdateProductionMachine,
)
from src.modules.fulfillment.domain.entities.production_machine import ProductionMachine
from src.modules.fulfillment.domain.errors import ProductionMachineArchiveBlockedError
from src.modules.fulfillment.domain.events.production_machine_events import (
    ProductionMachineArchived,
)
from src.modules.fulfillment.domain.events.production_machine_events import ProductionMachineCreated
from src.modules.fulfillment.domain.events.production_machine_events import (
    ProductionMachineRestored,
)
from src.modules.fulfillment.domain.events.production_machine_events import ProductionMachineUpdated
from src.modules.fulfillment.ports.outbound.repositories.production_machine_repository import (
    ProductionMachineFilterDto,
)
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.fakes import FakeUnitOfWork

# ── Helpers ───────────────────────────────────────────────────────────


def make_fabrication_method(id: int = 1, name: str = "Milling") -> FabricationMethod:
    return FabricationMethod(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        name=name,
        label_color="#999999",
        label_font_color="#000000",
        description="",
        creator_id=1,
    )


def make_machine(
    id: int = 1,
    internal_name: str = "Mill 1",
    archived: bool = False,
    fabrication_method_ids: list[int] | None = None,
) -> ProductionMachine:
    return ProductionMachine(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        archived=archived,
        internal_name=internal_name,
        vendor="Contoso",
        model="VF-2",
        fabrication_method_ids=fabrication_method_ids if fabrication_method_ids is not None else [],
        max_part_dimension=None,
        note=None,
        creator_id=1,
    )


class FakeEventBus:
    def __init__(self):
        self.published = []

    async def publish(self, event):
        self.published.append(event)


class FakeProductionMachineRepository:
    def __init__(self, machines: list[ProductionMachine] | None = None):
        self._machines: dict[int, ProductionMachine] = {}
        self._next_id = 1
        for m in machines or []:
            self._machines[m.id] = m
            self._next_id = max(self._next_id, m.id + 1)

    async def get_by_id(self, id: int) -> ProductionMachine | None:
        return self._machines.get(id)

    async def get_by_ids(self, ids: list[int]) -> list:
        found = [await self.get_by_id(i) for i in ids]
        return [item for item in found if item is not None]

    async def get_multi(
        self, filters: ProductionMachineFilterDto
    ) -> tuple[int, list[ProductionMachine]]:
        items = list(self._machines.values())
        if not filters.include_archived:
            items = [m for m in items if not m.archived]
        if filters.id is not None:
            items = [m for m in items if m.id == filters.id]
        if filters.fabrication_method_id is not None:
            items = [m for m in items if filters.fabrication_method_id in m.fabrication_method_ids]
        total = len(items)
        skip = filters.skip or 0
        limit = filters.limit
        return total, items[skip : skip + limit if limit else None]

    async def next_sort_order(self) -> int:
        return max((row.sort_order for row in self._machines.values()), default=-1) + 1

    async def save(self, item: ProductionMachine) -> ProductionMachine:
        if item.id == 0:
            item.id = self._next_id
            self._next_id += 1
        self._machines[item.id] = item
        return item

    async def delete(self, item: ProductionMachine) -> None:
        item.archived = True
        await self.save(item)


class FakeFabricationMethodRepository:
    def __init__(self, methods: list[FabricationMethod] | None = None):
        self._methods: dict[int, FabricationMethod] = {m.id: m for m in (methods or [])}

    async def get_by_id(self, id: int) -> FabricationMethod | None:
        return self._methods.get(id)

    async def get_live_names(self) -> list[tuple[int, LocalizedText]]:
        raise NotImplementedError

    async def get_multi(
        self, filters: FabricationMethodFilterDto
    ) -> tuple[int, list[FabricationMethod]]:
        raise NotImplementedError

    async def save(self, fabrication_method: FabricationMethod) -> FabricationMethod:
        raise NotImplementedError

    async def delete(self, fabrication_method: FabricationMethod) -> None:
        raise NotImplementedError


# ── CreateProductionMachine ──────────────────────────────────────────


class TestCreateProductionMachine:
    def setup_method(self):
        self.machine_repo = FakeProductionMachineRepository()
        self.fabrication_method_repo = FakeFabricationMethodRepository(
            [make_fabrication_method(id=1)]
        )
        self.actor = make_user(permissions=[Permission.WRITE_MACHINES])
        self.bus = FakeEventBus()
        self.use_case = CreateProductionMachine(
            self.machine_repo,
            self.fabrication_method_repo,
            event_bus=self.bus,
            uow=FakeUnitOfWork(),
        )

    def _cmd(self, **kwargs) -> CreateProductionMachineCommand:
        defaults = dict(internal_name="Mill 1", vendor="Contoso", model="VF-2")
        defaults.update(kwargs)
        return CreateProductionMachineCommand(**defaults)

    async def test_creates_machine_successfully(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        assert result.internal_name == "Mill 1"
        assert result.id > 0

    async def test_creates_machine_with_valid_fabrication_method_ids(self):
        result = await self.use_case.execute(
            actor=self.actor, cmd=self._cmd(fabrication_method_ids=[1])
        )
        assert result.fabrication_method_ids == [1]

    async def test_event_carries_correct_fields(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        (event,) = self.bus.published
        assert isinstance(event, ProductionMachineCreated)
        assert event.machine_id == result.id
        assert event.internal_name == "Mill 1"
        assert event.actor_id == self.actor.id

    async def test_creates_qa_machine(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd(is_qa_machine=True))
        assert result.is_qa_machine is True

    async def test_defaults_to_non_qa_machine(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        assert result.is_qa_machine is False

    async def test_missing_fabrication_method_raises(self):
        with pytest.raises(FabricationMethodNotFoundError):
            await self.use_case.execute(
                actor=self.actor, cmd=self._cmd(fabrication_method_ids=[999])
            )

    async def test_unprivileged_cannot_create(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, cmd=self._cmd())


# ── UpdateProductionMachine ──────────────────────────────────────────


class TestUpdateProductionMachine:
    def setup_method(self):
        self.machine = make_machine(id=1)
        self.machine_repo = FakeProductionMachineRepository([self.machine])
        self.fabrication_method_repo = FakeFabricationMethodRepository(
            [make_fabrication_method(id=1)]
        )
        self.actor = make_user(permissions=[Permission.WRITE_MACHINES])
        self.bus = FakeEventBus()
        self.use_case = UpdateProductionMachine(
            self.machine_repo,
            self.fabrication_method_repo,
            event_bus=self.bus,
            uow=FakeUnitOfWork(),
        )

    async def test_updates_partial_fields_successfully(self):
        result = await self.use_case.execute(
            actor=self.actor,
            machine_id=1,
            cmd=UpdateProductionMachineCommand(internal_name="Mill 2"),
        )
        assert result.internal_name == "Mill 2"
        # unchanged fields retain their prior values
        assert result.vendor == "Contoso"
        assert result.model == "VF-2"

    async def test_updates_fabrication_method_ids(self):
        result = await self.use_case.execute(
            actor=self.actor,
            machine_id=1,
            cmd=UpdateProductionMachineCommand(fabrication_method_ids=[1]),
        )
        assert result.fabrication_method_ids == [1]

    async def test_toggles_is_qa_machine(self):
        result = await self.use_case.execute(
            actor=self.actor,
            machine_id=1,
            cmd=UpdateProductionMachineCommand(is_qa_machine=True),
        )
        assert result.is_qa_machine is True
        # Omitting the field leaves it untouched (partial-update semantics).
        result = await self.use_case.execute(
            actor=self.actor,
            machine_id=1,
            cmd=UpdateProductionMachineCommand(internal_name="Mill 2"),
        )
        assert result.is_qa_machine is True

    async def test_missing_fabrication_method_raises(self):
        with pytest.raises(FabricationMethodNotFoundError):
            await self.use_case.execute(
                actor=self.actor,
                machine_id=1,
                cmd=UpdateProductionMachineCommand(fabrication_method_ids=[999]),
            )

    async def test_event_carries_correct_fields(self):
        result = await self.use_case.execute(
            actor=self.actor,
            machine_id=1,
            cmd=UpdateProductionMachineCommand(internal_name="Mill 2"),
        )
        (event,) = self.bus.published
        assert isinstance(event, ProductionMachineUpdated)
        assert event.machine_id == result.id
        assert event.internal_name == "Mill 2"

    async def test_not_found_raises(self):
        with pytest.raises(ProductionMachineNotFoundError):
            await self.use_case.execute(
                actor=self.actor, machine_id=999, cmd=UpdateProductionMachineCommand()
            )

    async def test_unprivileged_cannot_update(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(
                actor=actor, machine_id=1, cmd=UpdateProductionMachineCommand()
            )


# ── ArchiveProductionMachine / RestoreProductionMachine ───────────────


class _LiveOrders:
    """The production order repository slice the archive reads: the live
    order count per machine."""

    def __init__(self, counts: dict[int, int] | None = None) -> None:
        self.counts = counts or {}
        self.calls: list[str] = []

    async def lock_queue_scope(self, machine_id: int | None, machine_pool_id: int | None = None):
        self.calls.append(f"lock {machine_id}")

    async def count_live_by_machine_ids(self, machine_ids: list[int]) -> dict[int, int]:
        self.calls.append("count")
        return {m: self.counts[m] for m in machine_ids if m in self.counts}


class TestArchiveProductionMachine:
    def setup_method(self):
        self.machine = make_machine(id=1)
        self.machine_repo = FakeProductionMachineRepository([self.machine])
        self.actor = make_user(permissions=[Permission.WRITE_MACHINES])
        self.bus = FakeEventBus()
        self.orders = _LiveOrders()
        self.use_case = ArchiveProductionMachine(
            self.machine_repo, self.orders, event_bus=self.bus, uow=FakeUnitOfWork()
        )

    async def test_live_orders_on_the_machine_refuse_the_archive(self):
        self.orders.counts[1] = 3
        with pytest.raises(ProductionMachineArchiveBlockedError, match="3 production orders"):
            await self.use_case.execute(actor=self.actor, machine_id=1)
        assert (await self.machine_repo.get_by_id(1)).archived is False
        assert self.bus.published == []

    async def test_archives_successfully(self):
        result = await self.use_case.execute(actor=self.actor, machine_id=1)
        assert result.archived is True

    async def test_the_machine_queue_is_locked_before_its_orders_are_counted(self):
        """Every writer that queues an order on a machine holds the machine's
        queue lock and refuses an archived machine under it, so the count
        cannot miss an order placed while the archive runs."""
        await self.use_case.execute(actor=self.actor, machine_id=1)
        assert self.orders.calls == ["lock 1", "count"]

    async def test_archiving_twice_is_idempotent(self):
        await self.use_case.execute(actor=self.actor, machine_id=1)
        result = await self.use_case.execute(actor=self.actor, machine_id=1)
        assert result.archived is True

    async def test_archived_machine_excluded_from_get_multi_by_default(self):
        await self.use_case.execute(actor=self.actor, machine_id=1)
        total, items = await self.machine_repo.get_multi(ProductionMachineFilterDto())
        assert total == 0
        assert items == []

    async def test_archived_machine_included_when_requested(self):
        await self.use_case.execute(actor=self.actor, machine_id=1)
        total, _items = await self.machine_repo.get_multi(
            ProductionMachineFilterDto(include_archived=True)
        )
        assert total == 1

    async def test_archived_machine_still_resolves_by_id(self):
        await self.use_case.execute(actor=self.actor, machine_id=1)
        assert await self.machine_repo.get_by_id(1) is not None

    async def test_event_carries_correct_fields(self):
        await self.use_case.execute(actor=self.actor, machine_id=1)
        (event,) = self.bus.published
        assert isinstance(event, ProductionMachineArchived)
        assert event.machine_id == 1

    async def test_not_found_raises(self):
        with pytest.raises(ProductionMachineNotFoundError):
            await self.use_case.execute(actor=self.actor, machine_id=999)

    async def test_unprivileged_cannot_archive(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, machine_id=1)


class TestRestoreProductionMachine:
    def setup_method(self):
        self.actor = make_user(permissions=[Permission.WRITE_MACHINES])
        self.bus = FakeEventBus()

    async def test_restores_successfully(self):
        machine = make_machine(id=1, archived=True)
        repo = FakeProductionMachineRepository([machine])
        result = await RestoreProductionMachine(
            repo, event_bus=self.bus, uow=FakeUnitOfWork()
        ).execute(actor=self.actor, machine_id=1)
        assert result.archived is False

    async def test_restoring_twice_is_idempotent(self):
        machine = make_machine(id=1, archived=True)
        repo = FakeProductionMachineRepository([machine])
        use_case = RestoreProductionMachine(repo, event_bus=self.bus, uow=FakeUnitOfWork())
        await use_case.execute(actor=self.actor, machine_id=1)
        result = await use_case.execute(actor=self.actor, machine_id=1)
        assert result.archived is False

    async def test_event_carries_correct_fields(self):
        machine = make_machine(id=1, archived=True)
        repo = FakeProductionMachineRepository([machine])
        await RestoreProductionMachine(repo, event_bus=self.bus, uow=FakeUnitOfWork()).execute(
            actor=self.actor, machine_id=1
        )
        (event,) = self.bus.published
        assert isinstance(event, ProductionMachineRestored)
        assert event.machine_id == 1

    async def test_not_found_raises(self):
        repo = FakeProductionMachineRepository([])
        with pytest.raises(ProductionMachineNotFoundError):
            await RestoreProductionMachine(repo, event_bus=self.bus, uow=FakeUnitOfWork()).execute(
                actor=self.actor, machine_id=999
            )

    async def test_unprivileged_cannot_restore(self):
        machine = make_machine(id=1, archived=True)
        repo = FakeProductionMachineRepository([machine])
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await RestoreProductionMachine(repo, event_bus=self.bus, uow=FakeUnitOfWork()).execute(
                actor=actor, machine_id=1
            )


# ── GetProductionMachine / GetProductionMachines ─────────────────────


class TestGetProductionMachine:
    def setup_method(self):
        self.machine_repo = FakeProductionMachineRepository([make_machine(id=1)])
        self.use_case = GetProductionMachine(self.machine_repo)

    async def test_returns_machine_when_found(self):
        result = await self.use_case.execute(machine_id=1)
        assert result.id == 1
        assert result.internal_name == "Mill 1"

    async def test_not_found_raises(self):
        with pytest.raises(ProductionMachineNotFoundError):
            await self.use_case.execute(machine_id=999)


class TestGetProductionMachines:
    def setup_method(self):
        self.machine_repo = FakeProductionMachineRepository(
            [
                make_machine(id=1, internal_name="Mill 1", fabrication_method_ids=[1]),
                make_machine(id=2, internal_name="Lathe 1", fabrication_method_ids=[2]),
            ]
        )
        self.use_case = GetProductionMachines(self.machine_repo)

    async def test_lists_all_machines(self):
        result = await self.use_case.execute(ProductionMachineFilterDto())
        assert result.total == 2
        assert {m.internal_name for m in result.items} == {"Mill 1", "Lathe 1"}

    async def test_filters_by_fabrication_method_id(self):
        result = await self.use_case.execute(ProductionMachineFilterDto(fabrication_method_id=2))
        assert result.total == 1
        assert result.items[0].internal_name == "Lathe 1"

    async def test_filters_by_id(self):
        result = await self.use_case.execute(ProductionMachineFilterDto(id=1))
        assert result.total == 1
        assert result.items[0].id == 1
