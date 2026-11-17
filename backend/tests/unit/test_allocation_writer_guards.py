"""
Guards that every allocation writer of the three demand families applies:
a fulfilled or canceled demand takes no new or changed allocation, a
fulfilled one also keeps the allocations it has, and a canceled one may
still give them up, so the line or stock they hold is freed. An update or
a top-up of an allocation changes its quantity only, and fulfilling a made
demand from stock counts what its lots have completed. In-memory fakes, no
database.
"""

import copy
from datetime import UTC
from datetime import datetime
from typing import Any

import pytest

from src.modules.catalogue.domain.value_objects.bought_item_status import AllocationSource
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemAllocationSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.application.dto.allocation_dto import AutoAllocateCommand
from src.modules.fulfillment.application.dto.allocation_dto import CreateAllocationCommand
from src.modules.fulfillment.application.dto.allocation_dto import UpdateAllocationCommand
from src.modules.fulfillment.application.dto.allocation_dto import UpdateStockAllocationCommand
from src.modules.fulfillment.application.dto.made_item_allocation_dto import (
    FulfillMadeItemFromStockCommand,
)
from src.modules.fulfillment.application.dto.made_item_allocation_dto import (
    UpdateMadeItemStockAllocationCommand,
)
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
from src.modules.fulfillment.application.dto.source_item_allocation_dto import (
    UpdateSourceItemStockAllocationCommand,
)
from src.modules.fulfillment.application.services.allocation_fill import LineFillRepos
from src.modules.fulfillment.application.use_cases.bought_item_demand.auto_allocate import (
    AutoAllocate,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.create_allocation import (
    CreateAllocation,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.create_allocation import (
    DeleteAllocation,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.create_allocation import (
    DeleteStockAllocation,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.create_allocation import (
    UpdateAllocation,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.create_allocation import (
    UpdateStockAllocation,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.fulfill_from_stock import (
    FulfillDemandFromStock as FulfillMadeDemandFromStock,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.stock_allocation import (
    DeleteStockAllocation as DeleteMadeStockAllocation,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.stock_allocation import (
    UpdateStockAllocation as UpdateMadeStockAllocation,
)
from src.modules.fulfillment.application.use_cases.production_lot.create_lot import CreateLot
from src.modules.fulfillment.application.use_cases.source_item_allocation.auto_allocate import (
    AutoAllocateSourceItemDemand,
)
from src.modules.fulfillment.application.use_cases.source_item_allocation.create_allocation import (
    CreateSourceItemAllocation,
)
from src.modules.fulfillment.application.use_cases.source_item_allocation.create_allocation import (
    DeleteSourceItemAllocation,
)
from src.modules.fulfillment.application.use_cases.source_item_allocation.create_allocation import (
    DeleteSourceItemStockAllocation,
)
from src.modules.fulfillment.application.use_cases.source_item_allocation.create_allocation import (
    UpdateSourceItemAllocation,
)
from src.modules.fulfillment.application.use_cases.source_item_allocation.create_allocation import (
    UpdateSourceItemStockAllocation,
)
from src.modules.fulfillment.domain.entities.bought_item_allocation import (
    BoughtItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.made_item_allocation import MadeItemDemandAllocation
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.source_item_allocation import (
    SourceItemDemandAllocation,
)
from src.modules.fulfillment.domain.errors import DemandItemAlreadyCanceledError
from src.modules.fulfillment.domain.errors import DemandItemAlreadyFulfilledError
from src.modules.fulfillment.domain.errors import SourceItemDemandAlreadyCanceledError
from src.modules.fulfillment.domain.errors import SourceItemDemandAlreadyFulfilledError
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemAllocationSource,
)
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.lifecycle.fake_demand_reconciler import demand_reconciler
from tests.unit.production_lot._helpers import make_demand as make_lot_demand
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
from tests.unit.production_lot.fakes import lot_reconciler
from tests.unit.production_order._helpers import make_order as make_production_order
from tests.unit.production_order.fakes import FakeProductionLotRepository as ProductionLots
from tests.unit.production_order.fakes import FakeProductionOrderRepository as ProductionOrders
from tests.unit.test_bought_item_allocation_use_cases import (
    FakeAllocationRepository as BoughtAllocations,
)
from tests.unit.test_bought_item_allocation_use_cases import FakeDemandRepository as BoughtDemands
from tests.unit.test_bought_item_allocation_use_cases import FakeOrderItemRepository as Lines
from tests.unit.test_bought_item_allocation_use_cases import FakeUnitOfWork
from tests.unit.test_bought_item_allocation_use_cases import make_demand as make_bought_demand
from tests.unit.test_bought_item_allocation_use_cases import make_order_item as make_bought_line
from tests.unit.test_made_item_allocation_use_cases import (
    FakeAllocationRepository as MadeAllocations,
)
from tests.unit.test_made_item_allocation_use_cases import FakeDemandRepository as MadeDemands
from tests.unit.test_made_item_allocation_use_cases import make_demand as make_made_demand
from tests.unit.test_source_item_allocation_use_cases import (
    FakeAllocationRepository as SourceAllocations,
)
from tests.unit.test_source_item_allocation_use_cases import FakeDemandRepository as SourceDemands
from tests.unit.test_source_item_allocation_use_cases import FakeOrderItemRepository as SourceLines
from tests.unit.test_source_item_allocation_use_cases import make_demand as make_source_demand
from tests.unit.test_source_item_allocation_use_cases import make_order_item as make_source_line

ALLOCATOR = make_user(permissions=[Permission.WRITE_ALLOCATIONS])

BOUGHT_TERMINAL = [
    pytest.param(BoughtItemDemandStatus.FULFILLED, DemandItemAlreadyFulfilledError, id="fulfilled"),
    pytest.param(BoughtItemDemandStatus.CANCELED, DemandItemAlreadyCanceledError, id="canceled"),
]
SOURCE_TERMINAL = [
    pytest.param(
        SourceItemDemandStatus.FULFILLED,
        SourceItemDemandAlreadyFulfilledError,
        id="fulfilled",
    ),
    pytest.param(
        SourceItemDemandStatus.CANCELED, SourceItemDemandAlreadyCanceledError, id="canceled"
    ),
]
MADE_TERMINAL = [
    pytest.param(MadeItemDemandStatus.FULFILLED, DemandItemAlreadyFulfilledError, id="fulfilled"),
    pytest.param(MadeItemDemandStatus.CANCELED, DemandItemAlreadyCanceledError, id="canceled"),
]


def _with_intent(demand: Any) -> Any:
    """Gives a seeded terminal demand the intent its status stands for, so
    the derivation keeps the status."""
    if demand.status == "canceled":
        demand.canceled_at = datetime(2026, 1, 2, tzinfo=UTC)
    if demand.status == "fulfilled":
        demand.fulfilled_manually_at = datetime(2026, 1, 2, tzinfo=UTC)
    return demand


class RealisticBoughtAllocations(BoughtAllocations):
    """Saves like SqlAlchemyBoughtItemAllocationRepository.save: an existing
    row takes every field of the incoming allocation, not only its
    quantity, so a dropped field would show."""

    async def save(self, allocation: BoughtItemDemandAllocation) -> BoughtItemDemandAllocation:
        for i, existing in enumerate(self._allocations):
            if (
                existing.demand_item_id == allocation.demand_item_id
                and existing.order_item_id == allocation.order_item_id
            ):
                self._allocations[i] = copy.copy(allocation)
                return allocation
        self._allocations.append(copy.copy(allocation))
        return allocation


class RealisticSourceAllocations(SourceAllocations):
    """The source twin of RealisticBoughtAllocations."""

    async def save(self, allocation: SourceItemDemandAllocation) -> SourceItemDemandAllocation:
        for i, existing in enumerate(self._allocations):
            if (
                existing.demand_item_id == allocation.demand_item_id
                and existing.order_item_id == allocation.order_item_id
            ):
                self._allocations[i] = copy.copy(allocation)
                return allocation
        self._allocations.append(copy.copy(allocation))
        return allocation


def _bought_order_allocation(quantity: float = 2.0) -> BoughtItemDemandAllocation:
    return BoughtItemDemandAllocation(demand_item_id=1, order_item_id=1, quantity=quantity)


def _bought_stock_allocation(quantity: float = 2.0) -> BoughtItemDemandAllocation:
    return BoughtItemDemandAllocation(
        demand_item_id=1, order_item_id=None, quantity=quantity, source=AllocationSource.STOCK
    )


def _source_order_allocation(quantity: float = 2.0) -> SourceItemDemandAllocation:
    return SourceItemDemandAllocation(demand_item_id=1, order_item_id=1, quantity=quantity)


def _source_stock_allocation(quantity: float = 2.0) -> SourceItemDemandAllocation:
    return SourceItemDemandAllocation(
        demand_item_id=1,
        order_item_id=None,
        quantity=quantity,
        source=SourceItemAllocationSource.STOCK,
    )


# ── Bought item demands ──────────────────────────────────────────────


class TestBoughtWritersOnTerminalDemands:
    def _world(
        self,
        status: BoughtItemDemandStatus,
        allocations: list[BoughtItemDemandAllocation] | None = None,
    ) -> tuple[BoughtDemands, Lines, BoughtAllocations, FakeUnitOfWork]:
        demands = BoughtDemands(
            [_with_intent(make_bought_demand(id=1, quantity=10.0, status=status))]
        )
        lines = Lines([make_bought_line(id=1, quantity=10.0, bought_item_id=1)])
        return demands, lines, BoughtAllocations(list(allocations or [])), FakeUnitOfWork()

    @pytest.mark.parametrize(("status", "error"), BOUGHT_TERMINAL)
    async def test_create_is_refused(self, status: BoughtItemDemandStatus, error: type[Exception]):
        demands, lines, allocations, uow = self._world(status)

        with pytest.raises(error):
            await CreateAllocation(
                allocations,
                demands,
                lines,
                uow=uow,
                reconciler=demand_reconciler(
                    bought_allocations=allocations, bought_demands=demands, order_items=lines
                ),
                fill_repos=LineFillRepos(
                    bought=allocations, source=FakeSourceItemAllocationRepository()
                ),
            ).execute(
                ALLOCATOR, CreateAllocationCommand(demand_item_id=1, order_item_id=1, quantity=2.0)
            )

        assert await allocations.get_by_demand_item_id(1) == []
        assert uow.committed is False

    @pytest.mark.parametrize(("status", "error"), BOUGHT_TERMINAL)
    async def test_update_is_refused(self, status: BoughtItemDemandStatus, error: type[Exception]):
        demands, lines, allocations, uow = self._world(status, [_bought_order_allocation(2.0)])

        with pytest.raises(error):
            await UpdateAllocation(
                allocations,
                demands,
                lines,
                uow=uow,
                reconciler=demand_reconciler(
                    bought_allocations=allocations, bought_demands=demands, order_items=lines
                ),
                fill_repos=LineFillRepos(
                    bought=allocations, source=FakeSourceItemAllocationRepository()
                ),
            ).execute(ALLOCATOR, 1, 1, UpdateAllocationCommand(quantity=3.0))

        assert [a.quantity for a in await allocations.get_by_demand_item_id(1)] == [2.0]
        assert uow.committed is False

    @pytest.mark.parametrize(("status", "error"), BOUGHT_TERMINAL)
    async def test_setting_stock_is_refused(
        self, status: BoughtItemDemandStatus, error: type[Exception]
    ):
        demands, lines, allocations, uow = self._world(status)

        with pytest.raises(error):
            await UpdateStockAllocation(
                allocations,
                demands,
                lines,
                uow=uow,
                reconciler=demand_reconciler(
                    bought_allocations=allocations, bought_demands=demands, order_items=lines
                ),
            ).execute(ALLOCATOR, 1, UpdateStockAllocationCommand(quantity=2.0))

        assert await allocations.get_by_demand_item_id(1) == []
        assert uow.committed is False

    async def test_a_fulfilled_demand_keeps_its_order_allocation(self):
        demands, lines, allocations, uow = self._world(
            BoughtItemDemandStatus.FULFILLED, [_bought_order_allocation()]
        )

        with pytest.raises(DemandItemAlreadyFulfilledError):
            await DeleteAllocation(
                allocations,
                demands,
                lines,
                uow=uow,
                reconciler=demand_reconciler(
                    bought_allocations=allocations, bought_demands=demands, order_items=lines
                ),
                fill_repos=LineFillRepos(
                    bought=allocations, source=FakeSourceItemAllocationRepository()
                ),
            ).execute(ALLOCATOR, 1, 1)

        assert len(await allocations.get_by_demand_item_id(1)) == 1
        assert uow.committed is False

    async def test_a_fulfilled_demand_keeps_its_stock_allocation(self):
        demands, lines, allocations, uow = self._world(
            BoughtItemDemandStatus.FULFILLED, [_bought_stock_allocation()]
        )

        with pytest.raises(DemandItemAlreadyFulfilledError):
            await DeleteStockAllocation(
                allocations,
                demands,
                lines,
                uow=uow,
                reconciler=demand_reconciler(
                    bought_allocations=allocations, bought_demands=demands, order_items=lines
                ),
            ).execute(ALLOCATOR, 1)

        assert len(await allocations.get_by_demand_item_id(1)) == 1
        assert uow.committed is False

    async def test_a_canceled_demand_releases_its_order_allocation(self):
        demands, lines, allocations, uow = self._world(
            BoughtItemDemandStatus.CANCELED, [_bought_order_allocation()]
        )

        await DeleteAllocation(
            allocations,
            demands,
            lines,
            uow=uow,
            reconciler=demand_reconciler(
                bought_allocations=allocations, bought_demands=demands, order_items=lines
            ),
            fill_repos=LineFillRepos(
                bought=allocations, source=FakeSourceItemAllocationRepository()
            ),
        ).execute(ALLOCATOR, 1, 1)

        assert await allocations.get_by_demand_item_id(1) == []
        assert (await demands.get_by_id(1)).status == BoughtItemDemandStatus.CANCELED.value
        assert uow.committed is True
        assert demands.for_update_calls == [1]

    async def test_a_canceled_demand_releases_its_stock_allocation(self):
        demands, lines, allocations, uow = self._world(
            BoughtItemDemandStatus.CANCELED, [_bought_stock_allocation()]
        )

        await DeleteStockAllocation(
            allocations,
            demands,
            lines,
            uow=uow,
            reconciler=demand_reconciler(
                bought_allocations=allocations, bought_demands=demands, order_items=lines
            ),
        ).execute(ALLOCATOR, 1)

        assert await allocations.get_by_demand_item_id(1) == []
        assert (await demands.get_by_id(1)).status == BoughtItemDemandStatus.CANCELED.value
        assert uow.committed is True
        assert demands.for_update_calls == [1]


class TestBoughtAllocationUpdatesKeepTheirFields:
    async def test_update_keeps_the_substitution(self):
        demands = BoughtDemands([make_bought_demand(id=1, quantity=10.0, item_id=1)])
        lines = Lines([make_bought_line(id=1, quantity=10.0, bought_item_id=2)])
        allocations = RealisticBoughtAllocations(
            [
                BoughtItemDemandAllocation(
                    demand_item_id=1,
                    order_item_id=1,
                    quantity=2.0,
                    substitute_item_id=2,
                    substitute_reason="Successor part",
                )
            ]
        )

        result = await UpdateAllocation(
            allocations,
            demands,
            lines,
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(
                bought_allocations=allocations, bought_demands=demands, order_items=lines
            ),
            fill_repos=LineFillRepos(
                bought=allocations, source=FakeSourceItemAllocationRepository()
            ),
        ).execute(ALLOCATOR, 1, 1, UpdateAllocationCommand(quantity=5.0))

        assert result.quantity == 5.0
        [stored] = await allocations.get_by_demand_item_id(1)
        assert stored.quantity == 5.0
        assert stored.substitute_item_id == 2
        assert stored.substitute_reason == "Successor part"

    async def test_an_auto_allocate_top_up_keeps_every_other_field(self):
        demands = BoughtDemands([make_bought_demand(id=1, quantity=10.0, item_id=1)])
        lines = Lines([make_bought_line(id=1, quantity=10.0, bought_item_id=1)])
        allocations = RealisticBoughtAllocations(
            [
                BoughtItemDemandAllocation(
                    demand_item_id=1,
                    order_item_id=1,
                    quantity=2.0,
                    substitute_item_id=1,
                    substitute_reason="Noted at creation",
                )
            ]
        )

        result = await AutoAllocate(
            demands,
            lines,
            allocations,
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(
                bought_demands=demands, order_items=lines, bought_allocations=allocations
            ),
            project_repo=FakeProjectRepository(),
            fill_repos=LineFillRepos(
                bought=allocations, source=FakeSourceItemAllocationRepository()
            ),
        ).execute(ALLOCATOR, AutoAllocateCommand(demand_item_id=1))

        assert result.allocations_updated == 1
        [stored] = await allocations.get_by_demand_item_id(1)
        assert stored.quantity == 10.0
        assert stored.substitute_item_id == 1
        assert stored.substitute_reason == "Noted at creation"


class SplitReadDemands(BoughtDemands):
    """A plain read returns a copy of the stored demand, the way a read in
    another session would, and every save is recorded."""

    def __init__(self, demands, *, discovered_status: BoughtItemDemandStatus | None = None):
        super().__init__(demands)
        self.discovered: list[object] = []
        self.saved: list[object] = []
        self._discovered_status = discovered_status

    async def get_by_id(self, id: int):
        stored = await super().get_by_id(id)
        if stored is None:
            return None
        discovered = copy.copy(stored)
        if self._discovered_status is not None:
            discovered.status = self._discovered_status
        self.discovered.append(discovered)
        return discovered

    async def save(self, demand):
        self.saved.append(demand)
        return await super().save(demand)


class _StoredDemands:
    """The reconciler's view of a SplitReadDemands: it reads the stored row,
    as its locked read does, and saves through the recording fake."""

    def __init__(self, demands: SplitReadDemands) -> None:
        self._demands = demands

    async def get_by_id(self, id: int):
        return await BoughtDemands.get_by_id(self._demands, id)

    async def save(self, demand):
        return await self._demands.save(demand)


class TestBoughtAutoAllocateDecidesOnTheLockedDemand:
    async def test_a_demand_fulfilled_after_the_discovery_read_gets_nothing(self):
        demands = SplitReadDemands(
            [make_bought_demand(id=1, status=BoughtItemDemandStatus.FULFILLED)],
            discovered_status=BoughtItemDemandStatus.OPEN,
        )
        lines = Lines([make_bought_line(id=1, quantity=10.0, bought_item_id=1)])
        allocations = BoughtAllocations()

        result = await AutoAllocate(
            demands,
            lines,
            allocations,
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(
                bought_demands=demands, order_items=lines, bought_allocations=allocations
            ),
            project_repo=FakeProjectRepository(),
            fill_repos=LineFillRepos(
                bought=allocations, source=FakeSourceItemAllocationRepository()
            ),
        ).execute(ALLOCATOR, AutoAllocateCommand(demand_item_id=1))

        assert result.total_newly_allocated == 0.0
        assert await allocations.get_by_demand_item_id(1) == []
        assert demands.saved == []

    async def test_only_the_locked_demand_is_saved(self):
        demands = SplitReadDemands([make_bought_demand(id=1, quantity=4.0)])
        lines = Lines([make_bought_line(id=1, quantity=10.0, bought_item_id=1)])
        allocations = BoughtAllocations()

        await AutoAllocate(
            demands,
            lines,
            allocations,
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(
                bought_demands=_StoredDemands(demands),
                order_items=lines,
                bought_allocations=allocations,
            ),
            project_repo=FakeProjectRepository(),
            fill_repos=LineFillRepos(
                bought=allocations, source=FakeSourceItemAllocationRepository()
            ),
        ).execute(ALLOCATOR, AutoAllocateCommand(demand_item_id=1))

        assert demands.saved, "the status change must be saved"
        assert all(
            saved is not discovered for saved in demands.saved for discovered in demands.discovered
        )
        assert demands.saved[-1].status == BoughtItemDemandStatus.ALLOCATED.value


# ── Source item demands ──────────────────────────────────────────────


class TestSourceWritersOnTerminalDemands:
    def _world(
        self,
        status: SourceItemDemandStatus,
        allocations: list[SourceItemDemandAllocation] | None = None,
    ) -> tuple[SourceDemands, SourceLines, SourceAllocations, FakeUnitOfWork]:
        demands = SourceDemands(
            [_with_intent(make_source_demand(id=1, quantity=10.0, status=status))]
        )
        lines = SourceLines([make_source_line(id=1, quantity=10.0, source_item_id=1)])
        return demands, lines, SourceAllocations(list(allocations or [])), FakeUnitOfWork()

    @pytest.mark.parametrize(("status", "error"), SOURCE_TERMINAL)
    async def test_create_is_refused(self, status: SourceItemDemandStatus, error: type[Exception]):
        demands, lines, allocations, uow = self._world(status)

        with pytest.raises(error):
            await CreateSourceItemAllocation(
                allocations,
                demands,
                lines,
                uow=uow,
                reconciler=demand_reconciler(
                    source_allocations=allocations, source_demands=demands, order_items=lines
                ),
                fill_repos=LineFillRepos(
                    bought=FakeBoughtItemAllocationRepository(), source=allocations
                ),
            ).execute(
                ALLOCATOR,
                CreateSourceItemAllocationCommand(demand_item_id=1, order_item_id=1, quantity=2.0),
            )

        assert await allocations.get_by_demand_item_id(1) == []
        assert uow.committed is False

    @pytest.mark.parametrize(("status", "error"), SOURCE_TERMINAL)
    async def test_update_is_refused(self, status: SourceItemDemandStatus, error: type[Exception]):
        demands, lines, allocations, uow = self._world(status, [_source_order_allocation(2.0)])

        with pytest.raises(error):
            await UpdateSourceItemAllocation(
                allocations,
                demands,
                lines,
                uow=uow,
                reconciler=demand_reconciler(
                    source_allocations=allocations, source_demands=demands, order_items=lines
                ),
                fill_repos=LineFillRepos(
                    bought=FakeBoughtItemAllocationRepository(), source=allocations
                ),
            ).execute(ALLOCATOR, 1, 1, UpdateSourceItemAllocationCommand(quantity=3.0))

        assert [a.quantity for a in await allocations.get_by_demand_item_id(1)] == [2.0]
        assert uow.committed is False

    @pytest.mark.parametrize(("status", "error"), SOURCE_TERMINAL)
    async def test_setting_stock_is_refused(
        self, status: SourceItemDemandStatus, error: type[Exception]
    ):
        demands, lines, allocations, uow = self._world(status)

        with pytest.raises(error):
            await UpdateSourceItemStockAllocation(
                allocations,
                demands,
                lines,
                uow=uow,
                reconciler=demand_reconciler(
                    source_allocations=allocations, source_demands=demands, order_items=lines
                ),
            ).execute(ALLOCATOR, 1, UpdateSourceItemStockAllocationCommand(quantity=2.0))

        assert await allocations.get_by_demand_item_id(1) == []
        assert uow.committed is False

    async def test_a_fulfilled_demand_keeps_its_order_allocation(self):
        demands, lines, allocations, uow = self._world(
            SourceItemDemandStatus.FULFILLED, [_source_order_allocation()]
        )

        with pytest.raises(SourceItemDemandAlreadyFulfilledError):
            await DeleteSourceItemAllocation(
                allocations,
                demands,
                lines,
                uow=uow,
                reconciler=demand_reconciler(
                    source_allocations=allocations, source_demands=demands, order_items=lines
                ),
                fill_repos=LineFillRepos(
                    bought=FakeBoughtItemAllocationRepository(), source=allocations
                ),
            ).execute(ALLOCATOR, 1, 1)

        assert len(await allocations.get_by_demand_item_id(1)) == 1
        assert uow.committed is False

    async def test_a_fulfilled_demand_keeps_its_stock_allocation(self):
        demands, lines, allocations, uow = self._world(
            SourceItemDemandStatus.FULFILLED, [_source_stock_allocation()]
        )

        with pytest.raises(SourceItemDemandAlreadyFulfilledError):
            await DeleteSourceItemStockAllocation(
                allocations,
                demands,
                lines,
                uow=uow,
                reconciler=demand_reconciler(
                    source_allocations=allocations, source_demands=demands, order_items=lines
                ),
            ).execute(ALLOCATOR, 1)

        assert len(await allocations.get_by_demand_item_id(1)) == 1
        assert uow.committed is False

    async def test_a_canceled_demand_releases_its_order_allocation(self):
        demands, lines, allocations, uow = self._world(
            SourceItemDemandStatus.CANCELED, [_source_order_allocation()]
        )

        await DeleteSourceItemAllocation(
            allocations,
            demands,
            lines,
            uow=uow,
            reconciler=demand_reconciler(
                source_allocations=allocations, source_demands=demands, order_items=lines
            ),
            fill_repos=LineFillRepos(
                bought=FakeBoughtItemAllocationRepository(), source=allocations
            ),
        ).execute(ALLOCATOR, 1, 1)

        assert await allocations.get_by_demand_item_id(1) == []
        assert (await demands.get_by_id(1)).status == SourceItemDemandStatus.CANCELED.value
        assert uow.committed is True
        assert demands.for_update_calls == [1]

    async def test_a_canceled_demand_releases_its_stock_allocation(self):
        demands, lines, allocations, uow = self._world(
            SourceItemDemandStatus.CANCELED, [_source_stock_allocation()]
        )

        await DeleteSourceItemStockAllocation(
            allocations,
            demands,
            lines,
            uow=uow,
            reconciler=demand_reconciler(
                source_allocations=allocations, source_demands=demands, order_items=lines
            ),
        ).execute(ALLOCATOR, 1)

        assert await allocations.get_by_demand_item_id(1) == []
        assert (await demands.get_by_id(1)).status == SourceItemDemandStatus.CANCELED.value
        assert uow.committed is True
        assert demands.for_update_calls == [1]


class TestSourceAllocationUpdatesKeepTheirFields:
    async def test_an_auto_allocate_top_up_keeps_every_other_field(self):
        demands = SourceDemands([make_source_demand(id=1, quantity=10.0, source_item_id=1)])
        lines = SourceLines([make_source_line(id=1, quantity=10.0, source_item_id=1)])
        allocations = RealisticSourceAllocations(
            [
                SourceItemDemandAllocation(
                    demand_item_id=1,
                    order_item_id=1,
                    quantity=2.0,
                    substitute_source_item_id=1,
                    substitute_reason="Noted at creation",
                )
            ]
        )

        result = await AutoAllocateSourceItemDemand(
            demands,
            lines,
            allocations,
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(
                source_demands=demands, order_items=lines, source_allocations=allocations
            ),
            project_repo=FakeProjectRepository(),
            fill_repos=LineFillRepos(
                bought=FakeBoughtItemAllocationRepository(), source=allocations
            ),
        ).execute(ALLOCATOR, AutoAllocateSourceItemDemandCommand(demand_item_id=1))

        assert result.allocations_updated == 1
        [stored] = await allocations.get_by_demand_item_id(1)
        assert stored.quantity == 10.0
        assert stored.substitute_source_item_id == 1
        assert stored.substitute_reason == "Noted at creation"


# ── Made item demands ────────────────────────────────────────────────


def _made_stock_allocation(quantity: float = 2.0) -> MadeItemDemandAllocation:
    return MadeItemDemandAllocation(
        demand_item_id=1,
        lot_id=None,
        quantity=quantity,
        source=MadeItemAllocationSource.STOCK,
    )


class TestMadeWritersOnTerminalDemands:
    @pytest.mark.parametrize(("status", "error"), MADE_TERMINAL)
    async def test_setting_stock_is_refused(
        self, status: MadeItemDemandStatus, error: type[Exception]
    ):
        demands = MadeDemands([_with_intent(make_made_demand(id=1, quantity=10.0, status=status))])
        allocations = MadeAllocations()
        uow = FakeUnitOfWork()

        with pytest.raises(error):
            await UpdateMadeStockAllocation(
                allocations,
                demands,
                uow=uow,
                reconciler=demand_reconciler(made_allocations=allocations, made_demands=demands),
            ).execute(ALLOCATOR, 1, UpdateMadeItemStockAllocationCommand(quantity=2.0))

        assert await allocations.get_by_demand_item_id(1) == []
        assert uow.committed is False

    async def test_a_fulfilled_demand_keeps_its_stock_allocation(self):
        demands = MadeDemands([make_made_demand(id=1, status=MadeItemDemandStatus.FULFILLED)])
        allocations = MadeAllocations([_made_stock_allocation()])
        uow = FakeUnitOfWork()

        with pytest.raises(DemandItemAlreadyFulfilledError):
            await DeleteMadeStockAllocation(
                allocations,
                demands,
                uow=uow,
                reconciler=demand_reconciler(made_allocations=allocations, made_demands=demands),
            ).execute(ALLOCATOR, 1)

        assert len(await allocations.get_by_demand_item_id(1)) == 1
        assert uow.committed is False

    async def test_a_canceled_demand_releases_its_stock_allocation(self):
        demands = MadeDemands(
            [_with_intent(make_made_demand(id=1, status=MadeItemDemandStatus.CANCELED))]
        )
        allocations = MadeAllocations([_made_stock_allocation()])
        uow = FakeUnitOfWork()

        await DeleteMadeStockAllocation(
            allocations,
            demands,
            uow=uow,
            reconciler=demand_reconciler(made_allocations=allocations, made_demands=demands),
        ).execute(ALLOCATOR, 1)

        assert await allocations.get_by_demand_item_id(1) == []
        assert (await demands.get_by_id(1)).status == MadeItemDemandStatus.CANCELED.value
        assert uow.committed is True
        assert demands.for_update_calls == [1]


class TestLotLinkingOnTerminalDemands:
    @pytest.mark.parametrize(("status", "error"), MADE_TERMINAL)
    async def test_a_lot_cannot_take_a_terminal_demand(
        self, status: MadeItemDemandStatus, error: type[Exception]
    ):
        demands = FakeMadeItemDemandRepository([make_lot_demand(id=1, quantity=5.0, status=status)])
        allocations = FakeMadeItemAllocationRepository()
        uow = FakeLotUnitOfWork()
        lots = FakeProductionLotRepository()
        orders = FakeProductionOrderRepository()
        use_case = CreateLot(
            lot_repo=lots,
            made_item_repo=FakeMadeItemRepository([make_made_item(processes=[])]),
            demand_repo=demands,
            allocation_repo=allocations,
            settings_repo=FakeAdminSettingsRepository(),
            source_item_demand_repo=FakeSourceItemDemandRepository(),
            order_repo=orders,
            inspection_method_repo=FakeInspectionMethodRepository(),
            machine_repo=FakeProductionMachineRepository(),
            uow=uow,
            event_bus=FakeEventBus(),
            reconciler=lot_reconciler(lots, orders),
        )

        with pytest.raises(error):
            await use_case.execute(
                make_user(permissions=[Permission.WRITE_LOTS]),
                CreateLotCommand(
                    made_item_id=1,
                    project_id=1,
                    quantity=5.0,
                    demand_allocations=[LotDemandAllocationInput(demand_item_id=1, quantity=5.0)],
                ),
            )

        assert await allocations.get_by_demand_item_id(1) == []
        assert uow.committed is False


# ── Made fulfil-from-stock counts lot progress ───────────────────────


def _completed_lot(lot_id: int, quantity: float) -> ProductionLot:
    position = LotPosition(
        id=1,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=None,
        changes=[],
        sequence=1,
        kind=LotPositionKind.INTERNAL,
        status=LotPositionStatus.COMPLETED,
        quantity=quantity,
        quantity_completed=quantity,
        note=None,
        creator_id=1,
        lot_id=lot_id,
    )
    return ProductionLot(
        id=lot_id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=None,
        changes=[],
        lot_number=f"LOT-{lot_id}",
        quantity=quantity,
        status=LotStatus.COMPLETED,
        priority=UrgencyClass.NORMAL,
        note=None,
        creator_id=1,
        made_item_id=1,
        project_id=1,
        input_demand_id=None,
        positions=[position],
    )


def _orders_of_lot(*, completed: float, quantity: float) -> ProductionOrders:
    """The production order of the lot's one position, which the derivation
    counts the position's completed pieces from."""
    status = (
        ProductionOrderStatus.COMPLETED
        if completed >= quantity
        else ProductionOrderStatus.IN_PROGRESS
    )
    return ProductionOrders(
        [
            make_production_order(
                id=1,
                lot_position_id=1,
                status=status,
                quantity=quantity,
                quantity_completed=completed,
            )
        ]
    )


class TestMadeFulfilFromStockCountsLotProgress:
    async def test_lot_completions_plus_stock_fulfil_the_demand(self):
        """A demand of 10, covered 6 by a completed lot: fulfilling the
        other 4 from stock fulfils it, where counting the lot as nothing
        left it ORDERED."""
        demands = MadeDemands(
            [make_made_demand(id=1, quantity=10.0, status=MadeItemDemandStatus.ORDERED)]
        )
        allocations = MadeAllocations(
            [
                MadeItemDemandAllocation(
                    demand_item_id=1,
                    lot_id=7,
                    quantity=6.0,
                    source=MadeItemAllocationSource.LOT,
                )
            ]
        )
        uow = FakeUnitOfWork()
        use_case = FulfillMadeDemandFromStock(
            demands,
            allocations,
            uow=uow,
            reconciler=demand_reconciler(
                made_demands=demands,
                made_allocations=allocations,
                lots=ProductionLots([_completed_lot(7, 6.0)]),
                production_orders=_orders_of_lot(completed=6.0, quantity=6.0),
            ),
        )

        result = await use_case.execute(
            ALLOCATOR, FulfillMadeItemFromStockCommand(demand_item_id=1, quantity=4.0)
        )

        assert result.demand_status_changed_to == MadeItemDemandStatus.FULFILLED.value
        assert (await demands.get_by_id(1)).status == MadeItemDemandStatus.FULFILLED.value
        assert uow.committed is True

    async def test_an_unfinished_lot_leaves_the_demand_open_for_more(self):
        lot = _completed_lot(7, 6.0)
        lot.positions[0].quantity_completed = 3.0
        lot.status = LotStatus.IN_PROGRESS
        demands = MadeDemands(
            [make_made_demand(id=1, quantity=10.0, status=MadeItemDemandStatus.ORDERED)]
        )
        allocations = MadeAllocations(
            [
                MadeItemDemandAllocation(
                    demand_item_id=1,
                    lot_id=7,
                    quantity=6.0,
                    source=MadeItemAllocationSource.LOT,
                )
            ]
        )
        use_case = FulfillMadeDemandFromStock(
            demands,
            allocations,
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(
                made_demands=demands,
                made_allocations=allocations,
                lots=ProductionLots([lot]),
                production_orders=_orders_of_lot(completed=3.0, quantity=6.0),
            ),
        )

        result = await use_case.execute(
            ALLOCATOR, FulfillMadeItemFromStockCommand(demand_item_id=1, quantity=4.0)
        )

        assert result.demand_status_changed_to is None
        assert (await demands.get_by_id(1)).status == MadeItemDemandStatus.ORDERED.value
