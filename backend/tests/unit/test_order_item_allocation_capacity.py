"""
An order item's capacity is shared by both allocation families: a bought
item demand and a source item demand sourced from the same bought item can
draw on the same bought line, so every allocation writer counts what the
other family holds on it. The writers lock the line before the demand, and
read the line's allocated total only after both locks. In-memory fakes, no
database.
"""

import pytest

from src.modules.fulfillment.application.dto.allocation_dto import AutoAllocateCommand
from src.modules.fulfillment.application.dto.allocation_dto import CreateAllocationCommand
from src.modules.fulfillment.application.dto.allocation_dto import UpdateAllocationCommand
from src.modules.fulfillment.application.dto.production_lot_dto import CreateLotCommand
from src.modules.fulfillment.application.dto.production_lot_dto import LotDemandAllocationInput
from src.modules.fulfillment.application.dto.source_item_allocation_dto import (
    AutoAllocateSourceItemDemandCommand,
)
from src.modules.fulfillment.application.dto.source_item_allocation_dto import (
    CreateSourceItemAllocationCommand,
)
from src.modules.fulfillment.application.dto.source_item_allocation_dto import (
    UpdateSourceItemAllocationCommand,
)
from src.modules.fulfillment.application.services.allocation_fill import LineFillRepos
from src.modules.fulfillment.application.use_cases.bought_item_demand.auto_allocate import (
    AutoAllocate,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.create_allocation import (
    CreateAllocation,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.create_allocation import (
    UpdateAllocation,
)
from src.modules.fulfillment.application.use_cases.production_lot.create_lot import CreateLot
from src.modules.fulfillment.application.use_cases.source_item_allocation.auto_allocate import (
    AutoAllocateSourceItemDemand,
)
from src.modules.fulfillment.application.use_cases.source_item_allocation.create_allocation import (
    CreateSourceItemAllocation,
)
from src.modules.fulfillment.application.use_cases.source_item_allocation.create_allocation import (
    UpdateSourceItemAllocation,
)
from src.modules.fulfillment.domain.entities.bought_item_allocation import (
    BoughtItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.source_item_allocation import (
    SourceItemDemandAllocation,
)
from src.modules.fulfillment.domain.errors import AllocationOverflowError
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.lifecycle.fake_demand_reconciler import demand_reconciler
from tests.unit.lifecycle.fake_demand_reconciler import demand_reconciler_harness
from tests.unit.production_lot._helpers import make_demand as make_made_demand
from tests.unit.production_lot._helpers import make_made_item
from tests.unit.production_lot.fakes import FakeAdminSettingsRepository
from tests.unit.production_lot.fakes import FakeBoughtItemAllocationRepository
from tests.unit.production_lot.fakes import FakeEventBus
from tests.unit.production_lot.fakes import FakeInspectionMethodRepository
from tests.unit.production_lot.fakes import FakeMadeItemAllocationRepository
from tests.unit.production_lot.fakes import FakeMadeItemDemandRepository
from tests.unit.production_lot.fakes import FakeMadeItemRepository
from tests.unit.production_lot.fakes import FakeProductionLotRepository
from tests.unit.production_lot.fakes import FakeProductionMachineRepository
from tests.unit.production_lot.fakes import FakeProductionOrderRepository
from tests.unit.production_lot.fakes import FakeProjectRepository
from tests.unit.production_lot.fakes import FakeSourceItemAllocationRepository
from tests.unit.production_lot.fakes import FakeSourceItemDemandRepository
from tests.unit.production_lot.fakes import FakeUnitOfWork as FakeLotUnitOfWork
from tests.unit.test_bought_item_allocation_use_cases import (
    FakeAllocationRepository as BoughtAllocations,
)
from tests.unit.test_bought_item_allocation_use_cases import FakeDemandRepository as BoughtDemands
from tests.unit.test_bought_item_allocation_use_cases import FakeUnitOfWork
from tests.unit.test_bought_item_allocation_use_cases import make_demand as make_bought_demand
from tests.unit.test_bought_item_allocation_use_cases import make_order_item as make_bought_line
from tests.unit.test_source_item_allocation_use_cases import (
    FakeAllocationRepository as SourceAllocations,
)
from tests.unit.test_source_item_allocation_use_cases import FakeDemandRepository as SourceDemands
from tests.unit.test_source_item_allocation_use_cases import FakeOrderItemRepository as Lines
from tests.unit.test_source_item_allocation_use_cases import make_demand as make_source_demand

ALLOCATOR = make_user(permissions=[Permission.WRITE_ALLOCATIONS])

BOUGHT_DEMAND_ID = 1
SOURCE_DEMAND_ID = 2


class Ledger:
    """Both allocation tables of one test plus a log of the reads that
    matter for the lock order. Either family's repository answers what is
    allocated on a line from the two tables together, like the real query."""

    def __init__(self) -> None:
        self.log: list[tuple[str, int]] = []
        self.bought = LedgerBoughtAllocations(self)
        self.source = LedgerSourceAllocations(self)

    def allocated_on(self, order_item_id: int) -> float:
        rows = [*self.bought._allocations, *self.source._allocations]
        return sum(a.quantity for a in rows if a.order_item_id == order_item_id)

    def bought_on(self, order_item_id: int) -> float:
        return sum(a.quantity for a in self.bought._allocations if a.order_item_id == order_item_id)

    def source_on(self, order_item_id: int) -> float:
        return sum(a.quantity for a in self.source._allocations if a.order_item_id == order_item_id)


class LedgerBoughtAllocations(BoughtAllocations):
    def __init__(self, ledger: Ledger) -> None:
        super().__init__()
        self._ledger = ledger

    async def get_allocated_quantity_for_order_item(self, order_item_id: int) -> float:
        self._ledger.log.append(("capacity", order_item_id))
        return self._ledger.allocated_on(order_item_id)


class LedgerSourceAllocations(SourceAllocations):
    def __init__(self, ledger: Ledger) -> None:
        super().__init__()
        self._ledger = ledger

    async def get_allocated_quantity_for_order_item(self, order_item_id: int) -> float:
        self._ledger.log.append(("capacity", order_item_id))
        return self._ledger.allocated_on(order_item_id)


class LoggedLines(Lines):
    def __init__(self, items: list[OrderItem], log: list[tuple[str, int]]) -> None:
        super().__init__(items)
        self._log = log

    async def get_by_id(self, id: int) -> OrderItem | None:
        self._log.append(("read line", id))
        return await super().get_by_id(id)

    async def get_by_id_for_update(self, id: int) -> OrderItem | None:
        self._log.append(("lock line", id))
        return await super().get_by_id_for_update(id)

    async def get_by_ids(self, ids: list[int], *, refresh: bool = False) -> list[OrderItem]:
        # A refreshed batch read is how a use case reads lines it locked
        # through the lock plan, so it counts as their locked read.
        if refresh:
            self._log.extend(("lock line", id) for id in sorted(ids))
        return await super().get_by_ids(ids)


class LoggedBoughtDemands(BoughtDemands):
    def __init__(self, demands, log: list[tuple[str, int]]) -> None:
        super().__init__(demands)
        self._log = log

    async def get_by_id(self, id: int):
        self._log.append(("read demand", id))
        return await super().get_by_id(id)

    async def get_by_id_for_update(self, id: int):
        self._log.append(("lock demand", id))
        return await super().get_by_id_for_update(id)


class LoggedSourceDemands(SourceDemands):
    def __init__(self, demands, log: list[tuple[str, int]]) -> None:
        super().__init__(demands)
        self._log = log

    async def get_by_id(self, id: int):
        self._log.append(("read demand", id))
        return await super().get_by_id(id)

    async def get_by_id_for_update(self, id: int):
        self._log.append(("lock demand", id))
        return await super().get_by_id_for_update(id)


class World:
    """One bought demand and one source demand sourced from the same bought
    item, both of 10, and bought lines of that item."""

    def __init__(self, *lines: OrderItem) -> None:
        self.ledger = Ledger()
        self.lines = LoggedLines(list(lines), self.ledger.log)
        self.bought_demands = LoggedBoughtDemands(
            [make_bought_demand(id=BOUGHT_DEMAND_ID, quantity=10.0, item_id=1)], self.ledger.log
        )
        self.source_demands = LoggedSourceDemands(
            [
                make_source_demand(
                    id=SOURCE_DEMAND_ID, quantity=10.0, bought_item_id=1, source_item_id=None
                )
            ],
            self.ledger.log,
        )
        self.uow = FakeUnitOfWork()

    def hold_bought(self, order_item_id: int, quantity: float) -> None:
        self.ledger.bought._allocations.append(
            BoughtItemDemandAllocation(
                demand_item_id=BOUGHT_DEMAND_ID, order_item_id=order_item_id, quantity=quantity
            )
        )

    def hold_source(self, order_item_id: int, quantity: float) -> None:
        self.ledger.source._allocations.append(
            SourceItemDemandAllocation(
                demand_item_id=SOURCE_DEMAND_ID, order_item_id=order_item_id, quantity=quantity
            )
        )

    def create_bought(self) -> CreateAllocation:
        return CreateAllocation(
            self.ledger.bought,
            self.bought_demands,
            self.lines,
            uow=self.uow,
            reconciler=demand_reconciler(
                bought_allocations=self.ledger.bought,
                bought_demands=self.bought_demands,
                order_items=self.lines,
            ),
            fill_repos=LineFillRepos(
                bought=self.ledger.bought, source=FakeSourceItemAllocationRepository()
            ),
        )

    def update_bought(self) -> UpdateAllocation:
        return UpdateAllocation(
            self.ledger.bought,
            self.bought_demands,
            self.lines,
            uow=self.uow,
            reconciler=demand_reconciler(
                bought_allocations=self.ledger.bought,
                bought_demands=self.bought_demands,
                order_items=self.lines,
            ),
            fill_repos=LineFillRepos(
                bought=self.ledger.bought, source=FakeSourceItemAllocationRepository()
            ),
        )

    def auto_bought(self) -> AutoAllocate:
        return AutoAllocate(
            self.bought_demands,
            self.lines,
            self.ledger.bought,
            uow=self.uow,
            reconciler=demand_reconciler(
                bought_demands=self.bought_demands,
                order_items=self.lines,
                bought_allocations=self.ledger.bought,
            ),
            project_repo=FakeProjectRepository(),
            fill_repos=LineFillRepos(
                bought=self.ledger.bought, source=FakeSourceItemAllocationRepository()
            ),
        )

    def create_source(self) -> CreateSourceItemAllocation:
        return CreateSourceItemAllocation(
            self.ledger.source,
            self.source_demands,
            self.lines,
            uow=self.uow,
            reconciler=demand_reconciler(
                source_allocations=self.ledger.source,
                source_demands=self.source_demands,
                order_items=self.lines,
            ),
            fill_repos=LineFillRepos(
                bought=FakeBoughtItemAllocationRepository(), source=self.ledger.source
            ),
        )

    def update_source(self) -> UpdateSourceItemAllocation:
        return UpdateSourceItemAllocation(
            self.ledger.source,
            self.source_demands,
            self.lines,
            uow=self.uow,
            reconciler=demand_reconciler(
                source_allocations=self.ledger.source,
                source_demands=self.source_demands,
                order_items=self.lines,
            ),
            fill_repos=LineFillRepos(
                bought=FakeBoughtItemAllocationRepository(), source=self.ledger.source
            ),
        )

    def auto_source(self) -> AutoAllocateSourceItemDemand:
        return AutoAllocateSourceItemDemand(
            self.source_demands,
            self.lines,
            self.ledger.source,
            uow=self.uow,
            reconciler=demand_reconciler(
                source_demands=self.source_demands,
                order_items=self.lines,
                source_allocations=self.ledger.source,
            ),
            project_repo=FakeProjectRepository(),
            fill_repos=LineFillRepos(
                bought=FakeBoughtItemAllocationRepository(), source=self.ledger.source
            ),
        )


def line(id: int, quantity: float = 10.0) -> OrderItem:
    return make_bought_line(id=id, quantity=quantity, bought_item_id=1)


# ── Create ───────────────────────────────────────────────────────────


class TestCreateCountsBothFamilies:
    async def test_a_source_demand_cannot_take_a_line_a_bought_demand_filled(self):
        world = World(line(1))
        world.hold_bought(1, 10.0)

        with pytest.raises(AllocationOverflowError):
            await world.create_source().execute(
                ALLOCATOR,
                CreateSourceItemAllocationCommand(
                    demand_item_id=SOURCE_DEMAND_ID, order_item_id=1, quantity=1.0
                ),
            )

        assert world.ledger.source_on(1) == 0.0
        assert world.uow.committed is False

    async def test_a_bought_demand_cannot_take_a_line_a_source_demand_filled(self):
        world = World(line(1))
        world.hold_source(1, 10.0)

        with pytest.raises(AllocationOverflowError):
            await world.create_bought().execute(
                ALLOCATOR,
                CreateAllocationCommand(
                    demand_item_id=BOUGHT_DEMAND_ID, order_item_id=1, quantity=1.0
                ),
            )

        assert world.ledger.bought_on(1) == 0.0
        assert world.uow.committed is False

    async def test_what_the_other_family_left_stays_allocatable(self):
        world = World(line(1))
        world.hold_bought(1, 6.0)

        with pytest.raises(AllocationOverflowError):
            await world.create_source().execute(
                ALLOCATOR,
                CreateSourceItemAllocationCommand(
                    demand_item_id=SOURCE_DEMAND_ID, order_item_id=1, quantity=5.0
                ),
            )
        await world.create_source().execute(
            ALLOCATOR,
            CreateSourceItemAllocationCommand(
                demand_item_id=SOURCE_DEMAND_ID, order_item_id=1, quantity=4.0
            ),
        )

        assert world.ledger.allocated_on(1) == 10.0


# ── Update ───────────────────────────────────────────────────────────


class TestUpdateCountsBothFamilies:
    async def test_a_bought_allocation_cannot_grow_into_what_a_source_demand_holds(self):
        world = World(line(1))
        world.hold_bought(1, 4.0)
        world.hold_source(1, 6.0)

        with pytest.raises(AllocationOverflowError):
            await world.update_bought().execute(
                ALLOCATOR, BOUGHT_DEMAND_ID, 1, UpdateAllocationCommand(quantity=5.0)
            )
        assert world.ledger.bought_on(1) == 4.0

        await world.update_bought().execute(
            ALLOCATOR, BOUGHT_DEMAND_ID, 1, UpdateAllocationCommand(quantity=3.0)
        )
        assert world.ledger.bought_on(1) == 3.0

    async def test_a_source_allocation_cannot_grow_into_what_a_bought_demand_holds(self):
        world = World(line(1))
        world.hold_bought(1, 4.0)
        world.hold_source(1, 6.0)

        with pytest.raises(AllocationOverflowError):
            await world.update_source().execute(
                ALLOCATOR, SOURCE_DEMAND_ID, 1, UpdateSourceItemAllocationCommand(quantity=7.0)
            )

        assert world.ledger.source_on(1) == 6.0


# ── Auto-allocate ────────────────────────────────────────────────────


class TestAutoAllocateCountsBothFamilies:
    async def test_bought_skips_a_line_a_source_demand_filled(self):
        world = World(line(1), line(2))
        world.hold_source(1, 10.0)

        result = await world.auto_bought().execute(
            ALLOCATOR, AutoAllocateCommand(demand_item_id=BOUGHT_DEMAND_ID)
        )

        assert result.total_newly_allocated == 10.0
        assert world.ledger.bought_on(1) == 0.0
        assert world.ledger.bought_on(2) == 10.0

    async def test_bought_takes_only_what_a_shared_line_has_left(self):
        world = World(line(1))
        world.hold_source(1, 6.0)

        result = await world.auto_bought().execute(
            ALLOCATOR, AutoAllocateCommand(demand_item_id=BOUGHT_DEMAND_ID)
        )

        assert result.total_newly_allocated == 4.0
        assert result.remaining_unallocated == 6.0
        assert world.ledger.allocated_on(1) == 10.0

    async def test_source_skips_a_line_a_bought_demand_filled(self):
        world = World(line(1), line(2))
        world.hold_bought(1, 10.0)
        world.hold_bought(2, 3.0)

        result = await world.auto_source().execute(
            ALLOCATOR, AutoAllocateSourceItemDemandCommand(demand_item_id=SOURCE_DEMAND_ID)
        )

        assert result.total_newly_allocated == 7.0
        assert world.ledger.source_on(1) == 0.0
        assert world.ledger.source_on(2) == 7.0


# ── Lock order ───────────────────────────────────────────────────────


def _assert_line_then_demand_then_capacity(log: list[tuple[str, int]], demand_id: int) -> None:
    line_reads = [entry for entry in log if entry in (("read line", 1), ("lock line", 1))]
    # The line's first read is the locked one.
    assert line_reads[0] == ("lock line", 1)
    lock_line = log.index(("lock line", 1))
    lock_demand = log.index(("lock demand", demand_id))
    capacity = log.index(("capacity", 1))
    assert lock_line < lock_demand < capacity


class TestManualWritersLockTheLineFirst:
    async def test_bought_create(self):
        world = World(line(1))

        await world.create_bought().execute(
            ALLOCATOR,
            CreateAllocationCommand(demand_item_id=BOUGHT_DEMAND_ID, order_item_id=1, quantity=2.0),
        )

        _assert_line_then_demand_then_capacity(world.ledger.log, BOUGHT_DEMAND_ID)

    async def test_bought_update(self):
        world = World(line(1))
        world.hold_bought(1, 2.0)

        await world.update_bought().execute(
            ALLOCATOR, BOUGHT_DEMAND_ID, 1, UpdateAllocationCommand(quantity=3.0)
        )

        _assert_line_then_demand_then_capacity(world.ledger.log, BOUGHT_DEMAND_ID)

    async def test_source_create(self):
        world = World(line(1))

        await world.create_source().execute(
            ALLOCATOR,
            CreateSourceItemAllocationCommand(
                demand_item_id=SOURCE_DEMAND_ID, order_item_id=1, quantity=2.0
            ),
        )

        _assert_line_then_demand_then_capacity(world.ledger.log, SOURCE_DEMAND_ID)

    async def test_source_update(self):
        world = World(line(1))
        world.hold_source(1, 2.0)

        await world.update_source().execute(
            ALLOCATOR, SOURCE_DEMAND_ID, 1, UpdateSourceItemAllocationCommand(quantity=3.0)
        )

        _assert_line_then_demand_then_capacity(world.ledger.log, SOURCE_DEMAND_ID)


class TestAutoAllocateLocksLinesInAscendingIdBeforeTheDemand:
    @staticmethod
    def _assert_order(log: list[tuple[str, int]], demand_id: int) -> None:
        assert log[:4] == [
            ("read demand", demand_id),
            ("lock line", 1),
            ("lock line", 2),
            ("lock demand", demand_id),
        ]
        capacity_reads = [i for i, entry in enumerate(log) if entry[0] == "capacity"]
        assert capacity_reads
        assert min(capacity_reads) > log.index(("lock demand", demand_id))

    async def test_bought(self):
        world = World(line(2), line(1))

        await world.auto_bought().execute(
            ALLOCATOR, AutoAllocateCommand(demand_item_id=BOUGHT_DEMAND_ID)
        )

        self._assert_order(world.ledger.log, BOUGHT_DEMAND_ID)

    async def test_source(self):
        world = World(line(2), line(1))

        await world.auto_source().execute(
            ALLOCATOR, AutoAllocateSourceItemDemandCommand(demand_item_id=SOURCE_DEMAND_ID)
        )

        self._assert_order(world.ledger.log, SOURCE_DEMAND_ID)


class TestLotLinkingLocksDemandsInAscendingId:
    async def test_demands_are_locked_in_ascending_id(self):
        demands = FakeMadeItemDemandRepository(
            [make_made_demand(id=1, quantity=2.0), make_made_demand(id=2, quantity=3.0)]
        )
        lots = FakeProductionLotRepository()
        orders = FakeProductionOrderRepository()
        harness = demand_reconciler_harness(
            made_demands=demands, lots=lots, production_orders=orders
        )
        use_case = CreateLot(
            lot_repo=lots,
            made_item_repo=FakeMadeItemRepository([make_made_item(processes=[])]),
            demand_repo=demands,
            allocation_repo=FakeMadeItemAllocationRepository(),
            settings_repo=FakeAdminSettingsRepository(),
            source_item_demand_repo=FakeSourceItemDemandRepository(),
            order_repo=orders,
            inspection_method_repo=FakeInspectionMethodRepository(),
            machine_repo=FakeProductionMachineRepository(),
            uow=FakeLotUnitOfWork(),
            event_bus=FakeEventBus(),
            reconciler=harness.reconciler,
        )

        await use_case.execute(
            make_user(permissions=[Permission.WRITE_LOTS]),
            CreateLotCommand(
                made_item_id=1,
                project_id=1,
                quantity=5.0,
                demand_allocations=[
                    LotDemandAllocationInput(demand_item_id=2, quantity=3.0),
                    LotDemandAllocationInput(demand_item_id=1, quantity=2.0),
                ],
            ),
        )

        # Both through the request's lock plan, in one ascending acquisition.
        demand_locks = [
            ids
            for aggregate, ids in harness.lock_log
            if aggregate is LifecycleAggregate.MADE_DEMANDS
        ]
        assert demand_locks == [(1, 2)]
