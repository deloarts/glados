"""
Check-then-write use cases take their row locks through the request's lock
plan before they read what they check, in the one lock order, and refuse
with ConcurrentModificationError when what an unlocked discovery read found
changed before the locks: an order cancel that would leave a line added
meanwhile live, a material switch whose raw material demand was replaced, a
made demand cancel whose lots changed. No database, no HTTP.
"""

from types import SimpleNamespace
from typing import Any

import pytest

from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.application.dto.allocation_dto import CreateAllocationCommand
from src.modules.fulfillment.application.dto.made_item_allocation_dto import (
    UpdateMadeItemStockAllocationCommand,
)
from src.modules.fulfillment.application.dto.production_lot_dto import (
    SwitchLotMaterialSourceCommand,
)
from src.modules.fulfillment.application.dto.source_item_allocation_dto import (
    CreateSourceItemAllocationCommand,
)
from src.modules.fulfillment.application.services.allocation_fill import LineFillRepos
from src.modules.fulfillment.application.services.lifecycle_loader import AggregateIds
from src.modules.fulfillment.application.services.lot_cascades import lot_work_lock_targets
from src.modules.fulfillment.application.use_cases.bought_item_demand.create_allocation import (
    CreateAllocation,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.delete_demand_item import (
    DeleteDemandItem,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.cancel_demand import (
    CancelMadeItemDemand,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.stock_allocation import (
    UpdateStockAllocation,
)
from src.modules.fulfillment.application.use_cases.order.update_order import CancelOrder
from src.modules.fulfillment.application.use_cases.production_lot.switch_lot_material_source import (
    SwitchLotMaterialSource,
)
from src.modules.fulfillment.application.use_cases.source_item_allocation.create_allocation import (
    CreateSourceItemAllocation,
)
from src.modules.fulfillment.domain.entities.made_item_allocation import MadeItemDemandAllocation
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.platform.domain.exceptions import ConcurrentModificationError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.lifecycle.fake_demand_reconciler import demand_reconciler
from tests.unit.lifecycle.fake_demand_reconciler import demand_reconciler_harness
from tests.unit.lifecycle.fake_reconciler import give_order_facts
from tests.unit.order._helpers import FakeAllocationRepository as OrderAllocations
from tests.unit.order._helpers import FakeEventBus
from tests.unit.order._helpers import FakeOrderItemRepository
from tests.unit.order._helpers import FakeOrderRepository
from tests.unit.order._helpers import make_order
from tests.unit.order._helpers import make_order_item
from tests.unit.production_lot._helpers import make_demand as make_made_demand
from tests.unit.production_lot.fakes import FakeBoughtItemAllocationRepository
from tests.unit.production_lot.fakes import FakeMadeItemAllocationRepository
from tests.unit.production_lot.fakes import FakeMadeItemDemandRepository
from tests.unit.production_lot.fakes import FakeProductionLotRepository
from tests.unit.production_lot.fakes import FakeProjectRepository
from tests.unit.production_lot.fakes import FakeSourceItemAllocationRepository
from tests.unit.production_lot.fakes import FakeSourceItemDemandRepository
from tests.unit.production_lot.fakes import FakeUnitOfWork as FakeLotUnitOfWork
from tests.unit.production_lot.fakes import fake_line_release
from tests.unit.production_order._helpers import make_lot
from tests.unit.test_bought_item_allocation_use_cases import (
    FakeAllocationRepository as BoughtAllocations,
)
from tests.unit.test_bought_item_allocation_use_cases import FakeDemandRepository as BoughtDemands
from tests.unit.test_bought_item_allocation_use_cases import FakeOrderItemRepository as BoughtLines
from tests.unit.test_bought_item_allocation_use_cases import make_demand as make_bought_demand
from tests.unit.test_bought_item_allocation_use_cases import make_order_item as make_bought_line
from tests.unit.test_demand_item_use_cases import FakeDemandRepository as DeletableDemands
from tests.unit.test_source_item_allocation_use_cases import (
    FakeAllocationRepository as SourceAllocations,
)
from tests.unit.test_source_item_allocation_use_cases import FakeDemandRepository as SourceDemands
from tests.unit.test_source_item_allocation_use_cases import FakeOrderItemRepository as SourceLines
from tests.unit.test_source_item_allocation_use_cases import make_demand as make_source_demand
from tests.unit.test_source_item_allocation_use_cases import make_order_item as make_source_line

_A = LifecycleAggregate
ALLOCATOR = make_user(permissions=[Permission.WRITE_ALLOCATIONS])


class TestAllocationWritersLockThroughThePlan:
    async def test_a_bought_allocation_locks_its_line_then_its_demand_in_one_acquisition(
        self,
    ) -> None:
        demands = BoughtDemands([make_bought_demand(id=1, quantity=10.0, item_id=1)])
        lines = BoughtLines([make_bought_line(id=3, quantity=10.0, bought_item_id=1)])
        allocations = BoughtAllocations()
        harness = demand_reconciler_harness(
            bought_demands=demands, bought_allocations=allocations, order_items=lines
        )

        await CreateAllocation(
            allocations,
            demands,
            lines,
            uow=FakeUnitOfWork(),
            reconciler=harness.reconciler,
            fill_repos=LineFillRepos(
                bought=allocations, source=FakeSourceItemAllocationRepository()
            ),
        ).execute(
            ALLOCATOR, CreateAllocationCommand(demand_item_id=1, order_item_id=3, quantity=2.0)
        )

        assert harness.lock_log == [(_A.ORDER_ITEMS, (3,)), (_A.BOUGHT_DEMANDS, (1,))]

    async def test_a_source_allocation_locks_its_line_then_its_demand_in_one_acquisition(
        self,
    ) -> None:
        demands = SourceDemands([make_source_demand(id=2, quantity=10.0, source_item_id=1)])
        lines = SourceLines([make_source_line(id=3, quantity=10.0, source_item_id=1)])
        allocations = SourceAllocations()
        harness = demand_reconciler_harness(
            source_demands=demands, source_allocations=allocations, order_items=lines
        )

        await CreateSourceItemAllocation(
            allocations,
            demands,
            lines,
            uow=FakeUnitOfWork(),
            reconciler=harness.reconciler,
            fill_repos=LineFillRepos(
                bought=FakeBoughtItemAllocationRepository(), source=allocations
            ),
        ).execute(
            ALLOCATOR,
            CreateSourceItemAllocationCommand(demand_item_id=2, order_item_id=3, quantity=2.0),
        )

        assert harness.lock_log == [(_A.ORDER_ITEMS, (3,)), (_A.SOURCE_DEMANDS, (2,))]

    async def test_a_made_stock_allocation_locks_its_demand_through_the_plan(self) -> None:
        demands = FakeMadeItemDemandRepository([make_made_demand(id=4, quantity=10.0)])
        allocations = FakeMadeItemAllocationRepository()
        harness = demand_reconciler_harness(made_demands=demands, made_allocations=allocations)

        await UpdateStockAllocation(
            allocations, demands, uow=FakeLotUnitOfWork(), reconciler=harness.reconciler
        ).execute(
            make_user(permissions=[Permission.WRITE_ALLOCATIONS]),
            4,
            UpdateMadeItemStockAllocationCommand(quantity=3.0),
        )

        assert harness.lock_log == [(_A.MADE_DEMANDS, (4,))]


class TestDeleteDemand:
    async def test_the_demand_is_locked_before_its_allocations_are_counted(self) -> None:
        demands = DeletableDemands([make_bought_demand(id=1, quantity=10.0, item_id=1)])
        harness = demand_reconciler_harness(bought_demands=demands)
        allocations = BoughtAllocations()
        log: list[str] = []
        count = allocations.get_by_demand_item_id

        async def counted(demand_item_id: int) -> list[Any]:
            log.append(f"count after {len(harness.lock_log)} lock(s)")
            return await count(demand_item_id)

        allocations.get_by_demand_item_id = counted  # type: ignore[method-assign]

        await DeleteDemandItem(
            demands,
            allocations,
            uow=FakeUnitOfWork(),
            lock_plan=harness.reconciler.lock_plan,
        ).execute(
            make_user(permissions=[Permission.WRITE_DEMAND_ITEMS, Permission.MANAGE_DEMAND_ITEMS]),
            1,
        )

        assert harness.lock_log == [(_A.BOUGHT_DEMANDS, (1,))]
        assert log == ["count after 1 lock(s)"]


class _LinesAddedMeanwhile(FakeOrderItemRepository):
    """Order lines where a line joins the order after the first read of
    them, as a line another request adds before this one's locks."""

    def __init__(self, items: list[Any], added: Any) -> None:
        super().__init__(items)
        self._added = added
        self._reads = 0

    async def get_by_order_id(self, order_id: int) -> list[Any]:
        self._reads += 1
        if self._reads == 2:
            await self.save(self._added)
        return await super().get_by_order_id(order_id)


class TestCancelOrder:
    async def test_a_line_added_between_the_read_and_the_locks_is_refused(self) -> None:
        order = give_order_facts(make_order(id=1, status=OrderStatus.DRAFT))
        orders = FakeOrderRepository([order])
        lines = _LinesAddedMeanwhile(
            [make_order_item(id=1, order_id=1, status=OrderItemStatus.PENDING)],
            make_order_item(id=2, order_id=1, status=OrderItemStatus.PENDING),
        )
        uow = FakeUnitOfWork()
        use_case = CancelOrder(
            orders,
            lines,
            OrderAllocations([]),
            event_bus=FakeEventBus(),
            uow=uow,
            reconciler=demand_reconciler(orders=orders, order_items=lines),
        )

        with pytest.raises(ConcurrentModificationError):
            await use_case.execute(
                make_user(permissions=[Permission.WRITE_ORDERS, Permission.MANAGE_ORDERS]),
                1,
            )

        assert order.canceled_at is None
        assert uow.commits == 0


class _LotRelinkedWhileLocking(FakeProductionLotRepository):
    """A lot whose raw material demand another request replaces while this
    one waits for the lot's lock."""

    def __init__(self, new_demand_id: int) -> None:
        super().__init__()
        self._new_demand_id = new_demand_id

    async def lock_for_update(self, ids: list[int]) -> None:
        for lot_id in ids:
            self._lots[lot_id].input_demand_id = self._new_demand_id
        await super().lock_for_update(ids)


class TestSwitchMaterialSource:
    async def test_a_demand_replaced_between_the_read_and_the_locks_is_refused(self) -> None:
        lots = _LotRelinkedWhileLocking(new_demand_id=8)
        lot = await lots.save(_new_lot(input_demand_id=7))
        demands = FakeSourceItemDemandRepository([])
        uow = FakeLotUnitOfWork()
        use_case = SwitchLotMaterialSource(
            lot_repo=lots,
            bought_item_repo=None,  # type: ignore[arg-type]
            source_item_repo=None,  # type: ignore[arg-type]
            made_item_repo=None,  # type: ignore[arg-type]
            source_item_demand_repo=demands,
            source_item_allocation_repo=(allocations := FakeSourceItemAllocationRepository()),
            settings_repo=None,  # type: ignore[arg-type]
            project_repo=FakeProjectRepository(),
            line_release=fake_line_release(allocations),
            uow=uow,
            reconciler=demand_reconciler(source_demands=demands, lots=lots),
        )

        with pytest.raises(ConcurrentModificationError):
            await use_case.execute(
                make_user(permissions=[Permission.WRITE_LOTS, Permission.MANAGE_LOTS]),
                lot.id,
                SwitchLotMaterialSourceCommand(source_item_id=3, confirm_replace_demand=True),
            )

        assert uow.commits == 0


class _ImpactThatMoves:
    """A cancel impact that finds a lot only on its second reading, as when
    another request links the demand to a lot before this one's locks."""

    def __init__(self) -> None:
        self.readings = 0

    async def collect(self, actor: Any, demand: Any) -> Any:
        self.readings += 1
        lots = [] if self.readings == 1 else [SimpleNamespace(lot_id=5, will_cancel=False)]
        return SimpleNamespace(lots=lots)


class TestCancelMadeDemand:
    async def test_lots_changed_between_the_impact_and_the_locks_are_refused(self) -> None:
        demand = make_made_demand(id=9, quantity=10.0, status=MadeItemDemandStatus.OPEN)
        demands = FakeMadeItemDemandRepository([demand])
        allocations = FakeMadeItemAllocationRepository()
        uow = FakeLotUnitOfWork()
        use_case = CancelMadeItemDemand(
            demand_repo=demands,
            allocation_repo=allocations,
            lot_repo=FakeProductionLotRepository(),
            collector=_ImpactThatMoves(),  # type: ignore[arg-type]
            cancel_lot=None,  # type: ignore[arg-type]
            event_bus=FakeEventBus(),
            uow=uow,
            reconciler=demand_reconciler(made_demands=demands, made_allocations=allocations),
        )

        with pytest.raises(ConcurrentModificationError):
            await use_case.execute(
                make_user(
                    permissions=[Permission.WRITE_DEMAND_ITEMS, Permission.MANAGE_DEMAND_ITEMS]
                ),
                9,
            )

        assert demand.canceled_at is None
        assert uow.commits == 0


class TestLotWorkLockTargets:
    async def test_the_raw_material_demand_and_the_lots_made_demands_join_the_cascade_lock(
        self,
    ) -> None:
        lots = FakeProductionLotRepository()
        lot = await lots.save(_new_lot(input_demand_id=50))
        demands = FakeMadeItemDemandRepository([make_made_demand(id=9)])
        allocations = FakeMadeItemAllocationRepository(
            [MadeItemDemandAllocation(demand_item_id=9, lot_id=lot.id, quantity=10.0)]
        )
        source_demands = FakeSourceItemDemandRepository([])
        harness = demand_reconciler_harness(
            lots=lots,
            made_demands=demands,
            made_allocations=allocations,
            source_demands=source_demands,
        )
        reconciler = harness.reconciler
        await reconciler.lock_plan.acquire(AggregateIds.of({_A.LOTS: [lot.id]}))

        targets = await lot_work_lock_targets(reconciler, lot, _NoOrders(), _NoLines())
        await reconciler.lock_touched(also=targets)

        assert targets.get(_A.SOURCE_DEMANDS) == frozenset({50})
        assert (_A.MADE_DEMANDS, (9,)) in harness.lock_log
        assert (_A.SOURCE_DEMANDS, (50,)) in harness.lock_log


class _NoOrders:
    async def get_by_lot_position_ids(self, ids: list[int], *, refresh: bool = False) -> list:
        return []


class _NoLines:
    async def get_by_lot_position_ids(self, ids: list[int], *, refresh: bool = False) -> list:
        return []


def _new_lot(*, input_demand_id: int) -> Any:
    """A lot for a lot fake to insert, linked to a raw material demand."""
    return make_lot(id=0, input_demand_id=input_demand_id)
