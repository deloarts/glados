"""
Unit tests for made-item allocation use cases (stock allocation CRUD,
fulfill-from-stock, demand summary) and a direct test of the generalized
coverage protocol (allocation_coverage.py) proving it's genuinely generic
across the bought-item (order-item-backed) and made-item (lot-backed)
shapes, not just "happens to compile for one caller". No database, no
HTTP. All dependencies replaced with in-memory fakes.
"""

from datetime import date

import pytest

from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemAllocationSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.application.dto.made_item_allocation_dto import (
    FulfillMadeItemFromStockCommand,
)
from src.modules.fulfillment.application.dto.made_item_allocation_dto import (
    UpdateMadeItemStockAllocationCommand,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.fulfill_from_stock import (
    FulfillDemandFromStock,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.get_allocations import (
    GetDemandSummary,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.stock_allocation import (
    DeleteStockAllocation,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.stock_allocation import (
    UpdateStockAllocation,
)
from src.modules.fulfillment.domain.entities.made_item_allocation import MadeItemDemandAllocation
from src.modules.fulfillment.domain.entities.made_item_demand_item import MadeItemDemandItem
from src.modules.fulfillment.domain.errors import AllocationNotFoundError
from src.modules.fulfillment.domain.errors import AllocationOverflowError
from src.modules.fulfillment.domain.errors import DemandItemNotFoundError
from src.modules.fulfillment.domain.services.allocation_coverage import CoverageInfo
from src.modules.fulfillment.domain.services.allocation_coverage import compute_coverage_totals
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    MadeItemDemandFilterDto,
)
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.lifecycle.fake_demand_reconciler import demand_reconciler

# ── Helpers ───────────────────────────────────────────────────────────


def make_demand(
    id: int = 1,
    quantity: float = 10.0,
    status: MadeItemDemandStatus = MadeItemDemandStatus.OPEN,
) -> MadeItemDemandItem:
    return MadeItemDemandItem(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        status=status,
        quantity=quantity,
        unit="pcs",
        items_per_unit=1.0,
        high_priority=False,
        notify_on_delivery=False,
        note=None,
        desired_delivery_date=None,
        creator_id=1,
        made_item_id=1,
        project_id=1,
    )


class FakeDemandRepository:
    def __init__(self, demands: list[MadeItemDemandItem] | None = None):
        self._demands: dict[int, MadeItemDemandItem] = {d.id: d for d in (demands or [])}
        self.for_update_calls: list[int] = []

    async def get_by_id(self, id: int) -> MadeItemDemandItem | None:
        return self._demands.get(id)

    async def get_by_id_for_update(self, id: int) -> MadeItemDemandItem | None:
        self.for_update_calls.append(id)
        return self._demands.get(id)

    async def get_by_ids(self, ids: list[int]) -> list[MadeItemDemandItem]:
        raise NotImplementedError

    async def get_by_project_id(self, project_id: int) -> list[MadeItemDemandItem]:
        raise NotImplementedError

    async def get_pipeline(self, terminal_since: date) -> list[MadeItemDemandItem]:
        raise NotImplementedError

    async def get_multi(
        self, filters: MadeItemDemandFilterDto
    ) -> tuple[int, list[MadeItemDemandItem]]:
        raise NotImplementedError

    async def save(self, demand: MadeItemDemandItem) -> MadeItemDemandItem:
        self._demands[demand.id] = demand
        return demand

    async def delete(self, demand: MadeItemDemandItem) -> None:
        raise NotImplementedError


class FakeAllocationRepository:
    def __init__(self, allocations: list[MadeItemDemandAllocation] | None = None):
        self._allocations: list[MadeItemDemandAllocation] = list(allocations or [])

    async def get_by_demand_item_id(self, demand_item_id: int) -> list[MadeItemDemandAllocation]:
        return [a for a in self._allocations if a.demand_item_id == demand_item_id]

    async def get_by_demand_item_ids(
        self, demand_item_ids: list[int]
    ) -> list[MadeItemDemandAllocation]:
        raise NotImplementedError

    async def get_by_lot_id(self, lot_id: int) -> list[MadeItemDemandAllocation]:
        return [a for a in self._allocations if a.lot_id == lot_id]

    async def get_by_lot_ids(self, lot_ids: list[int]) -> list:
        return [a for lot_id in lot_ids for a in await self.get_by_lot_id(lot_id)]

    async def get_allocated_quantity(self, demand_item_id: int) -> float:
        return sum(a.quantity for a in await self.get_by_demand_item_id(demand_item_id))

    async def save(self, allocation: MadeItemDemandAllocation) -> MadeItemDemandAllocation:
        existing = next(
            (
                a
                for a in self._allocations
                if a.demand_item_id == allocation.demand_item_id and a.lot_id == allocation.lot_id
            ),
            None,
        )
        if existing:
            existing.quantity = allocation.quantity
            existing.source = allocation.source
        else:
            self._allocations.append(allocation)
        return allocation

    async def delete(self, allocation: MadeItemDemandAllocation) -> None:
        self._allocations = [
            a
            for a in self._allocations
            if not (a.demand_item_id == allocation.demand_item_id and a.lot_id == allocation.lot_id)
        ]


class FakeLotRepository:
    """No lots created in these tests, always empty, exercised for real
    by tests/unit/production_lot/. Implements the full protocol
    (unused methods raise) so it satisfies IProductionLotRepository's
    structural typing."""

    async def get_by_id(self, id: int):
        raise NotImplementedError

    async def get_by_ids(self, ids: list[int]) -> list:
        return []

    async def get_multi(self, filters):
        raise NotImplementedError

    async def save(self, lot):
        raise NotImplementedError

    async def next_lot_number(self, template: str) -> str:
        raise NotImplementedError

    async def get_steps(self, lot_id: int) -> list:
        raise NotImplementedError

    async def get_step_by_id(self, step_id: int):
        raise NotImplementedError

    async def save_step(self, step):
        raise NotImplementedError

    async def delete_step(self, step) -> None:
        raise NotImplementedError

    async def reorder_steps(self, lot_id: int, ordered_step_ids: list[int]) -> list:
        raise NotImplementedError

    async def get_positions(self, lot_id: int) -> list:
        raise NotImplementedError

    async def get_position_by_id(self, position_id: int):
        raise NotImplementedError

    async def get_positions_by_ids(self, position_ids: list[int]) -> list:
        positions = [await self.get_position_by_id(i) for i in position_ids]
        return [p for p in positions if p is not None]

    async def save_position(self, position):
        raise NotImplementedError

    async def delete_position(self, position) -> None:
        raise NotImplementedError


class FakeUnitOfWork:
    def __init__(self):
        self.committed = False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        pass


# ── UpdateStockAllocation / DeleteStockAllocation ──────────────────────


class TestStockAllocation:
    def setup_method(self):
        self.demand = make_demand(id=1, quantity=10.0)
        self.demand_repo = FakeDemandRepository([self.demand])
        self.allocation_repo = FakeAllocationRepository()
        self.lot_repo = FakeLotRepository()
        self.actor = make_user(permissions=[Permission.WRITE_ALLOCATIONS])
        self.update_use_case = UpdateStockAllocation(
            self.allocation_repo,
            self.demand_repo,
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(
                made_allocations=self.allocation_repo, made_demands=self.demand_repo
            ),
        )
        self.delete_use_case = DeleteStockAllocation(
            self.allocation_repo,
            self.demand_repo,
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(
                made_allocations=self.allocation_repo, made_demands=self.demand_repo
            ),
        )

    async def test_sets_stock_allocation_and_updates_status(self):
        result = await self.update_use_case.execute(
            actor=self.actor,
            demand_item_id=1,
            cmd=UpdateMadeItemStockAllocationCommand(quantity=4.0),
        )
        assert result.quantity == 4.0
        assert result.source == "stock"
        assert (await self.demand_repo.get_by_id(1)).status == "allocated"

    async def test_reads_the_demand_with_a_row_lock(self):
        """Two concurrent stock-allocation writes against the same
        demand must not both read the pre-write lot_only_allocated total,
        see IMadeItemDemandItemRepository.get_by_id_for_update."""
        await self.update_use_case.execute(
            actor=self.actor,
            demand_item_id=1,
            cmd=UpdateMadeItemStockAllocationCommand(quantity=4.0),
        )
        assert self.demand_repo.for_update_calls == [1]

    async def test_full_stock_allocation_fulfills_demand(self):
        await self.update_use_case.execute(
            actor=self.actor,
            demand_item_id=1,
            cmd=UpdateMadeItemStockAllocationCommand(quantity=10.0),
        )
        assert (await self.demand_repo.get_by_id(1)).status == "fulfilled"

    async def test_overallocation_raises(self):
        with pytest.raises(AllocationOverflowError):
            await self.update_use_case.execute(
                actor=self.actor,
                demand_item_id=1,
                cmd=UpdateMadeItemStockAllocationCommand(quantity=11.0),
            )

    async def test_unprivileged_cannot_allocate(self):
        actor = make_user(permissions=[])
        with pytest.raises(Exception):  # InsufficientPermissionsError  # noqa: B017
            await self.update_use_case.execute(
                actor=actor,
                demand_item_id=1,
                cmd=UpdateMadeItemStockAllocationCommand(quantity=1.0),
            )

    async def test_demand_not_found_raises(self):
        with pytest.raises(DemandItemNotFoundError):
            await self.update_use_case.execute(
                actor=self.actor,
                demand_item_id=999,
                cmd=UpdateMadeItemStockAllocationCommand(quantity=1.0),
            )

    async def test_delete_removes_stock_allocation(self):
        await self.update_use_case.execute(
            actor=self.actor,
            demand_item_id=1,
            cmd=UpdateMadeItemStockAllocationCommand(quantity=4.0),
        )
        await self.delete_use_case.execute(actor=self.actor, demand_item_id=1)
        assert await self.allocation_repo.get_by_demand_item_id(1) == []
        assert (await self.demand_repo.get_by_id(1)).status == "open"

    async def test_delete_without_existing_raises(self):
        with pytest.raises(AllocationNotFoundError):
            await self.delete_use_case.execute(actor=self.actor, demand_item_id=1)


# ── FulfillDemandFromStock ──────────────────────────────────────────────


class TestFulfillDemandFromStock:
    def setup_method(self):
        self.demand = make_demand(id=1, quantity=10.0)
        self.demand_repo = FakeDemandRepository([self.demand])
        self.allocation_repo = FakeAllocationRepository()
        self.actor = make_user(permissions=[Permission.WRITE_ALLOCATIONS])
        self.uow = FakeUnitOfWork()
        self.use_case = FulfillDemandFromStock(
            self.demand_repo,
            self.allocation_repo,
            uow=self.uow,
            reconciler=demand_reconciler(
                made_demands=self.demand_repo, made_allocations=self.allocation_repo
            ),
        )

    async def test_tops_up_stock_allocation(self):
        result = await self.use_case.execute(
            actor=self.actor, cmd=FulfillMadeItemFromStockCommand(demand_item_id=1, quantity=3.0)
        )
        assert result.total_fulfilled_from_stock == 3.0
        assert result.demand_status_changed_to == "allocated"
        assert self.uow.committed is True

        result2 = await self.use_case.execute(
            actor=self.actor, cmd=FulfillMadeItemFromStockCommand(demand_item_id=1, quantity=2.0)
        )
        assert result2.total_fulfilled_from_stock == 5.0

    async def test_reads_the_demand_with_a_row_lock(self):
        """See TestStockAllocation's identical test."""
        await self.use_case.execute(
            actor=self.actor, cmd=FulfillMadeItemFromStockCommand(demand_item_id=1, quantity=3.0)
        )
        assert self.demand_repo.for_update_calls == [1]

    async def test_fulfilling_full_quantity_marks_fulfilled(self):
        result = await self.use_case.execute(
            actor=self.actor, cmd=FulfillMadeItemFromStockCommand(demand_item_id=1, quantity=10.0)
        )
        assert result.demand_status_changed_to == "fulfilled"

    async def test_overallocation_raises(self):
        with pytest.raises(AllocationOverflowError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=FulfillMadeItemFromStockCommand(demand_item_id=1, quantity=11.0),
            )

    async def test_demand_not_found_raises(self):
        with pytest.raises(DemandItemNotFoundError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=FulfillMadeItemFromStockCommand(demand_item_id=999, quantity=1.0),
            )


# ── GetDemandSummary ──────────────────────────────────────────────────


class TestGetDemandSummary:
    def setup_method(self):
        self.demand = make_demand(id=1, quantity=10.0)
        self.demand_repo = FakeDemandRepository([self.demand])
        self.allocation_repo = FakeAllocationRepository(
            [
                MadeItemDemandAllocation(
                    demand_item_id=1,
                    lot_id=None,
                    quantity=4.0,
                    source=MadeItemAllocationSource.STOCK,
                )
            ]
        )
        self.use_case = GetDemandSummary(
            self.demand_repo, self.allocation_repo, FakeLotRepository()
        )

    async def test_summary_reflects_stock_allocation(self):
        summary = await self.use_case.execute(demand_item_id=1)
        assert summary.total == 10.0
        assert summary.fulfilled_from_stock == 4.0
        assert summary.remaining == 6.0
        # LOT-sourced coverage isn't implemented yet, so it's always empty here.
        assert summary.lot_ids == []
        assert summary.ordered == 0.0

    async def test_not_found_raises(self):
        with pytest.raises(DemandItemNotFoundError):
            await self.use_case.execute(demand_item_id=999)


# ── Coverage protocol generalization ────────────────────────────────────


class _FixedCoverageSource:
    """Minimal AllocationCoverageSource fake for testing the generic function directly."""

    def __init__(self, coverage: dict[int, CoverageInfo]):
        self._coverage = coverage

    def coverage_for(self, ref_id: int) -> CoverageInfo | None:
        return self._coverage.get(ref_id)


class _Alloc:
    """Minimal allocation-like object satisfying the _AllocationLike protocol."""

    def __init__(self, quantity: float, source: str, coverage_ref_id: int | None):
        self.demand_item_id = 1
        self.quantity = quantity
        self.source = source
        self._coverage_ref_id = coverage_ref_id

    @property
    def coverage_ref_id(self) -> int | None:
        return self._coverage_ref_id


class TestComputeCoverageTotals:
    """
    Proves compute_coverage_totals is genuinely generic: the same pure
    function produces correct totals for a bought-item-shaped source (order
    items keyed by order_item_id, "order" vs "stock") and a made-item-shaped
    source (lots keyed by lot_id, "lot" vs "stock") without any special-casing.
    """

    def test_bought_shaped_source(self):
        allocations = [
            _Alloc(quantity=5.0, source="order", coverage_ref_id=100),
            _Alloc(quantity=3.0, source="stock", coverage_ref_id=None),
        ]
        coverage = _FixedCoverageSource({100: CoverageInfo(is_placed=True, arrived=2.5)})

        allocated, ordered, delivered, fulfilled_from_stock = compute_coverage_totals(
            allocations, coverage, stock_source_value="stock", rank=0, fill={}
        )
        assert allocated == 5.0
        assert ordered == 5.0
        assert delivered == 2.5
        assert fulfilled_from_stock == 3.0

    def test_made_item_shaped_source(self):
        allocations = [
            _Alloc(quantity=8.0, source="lot", coverage_ref_id=7),
            _Alloc(quantity=2.0, source="stock", coverage_ref_id=None),
        ]
        # No real lot coverage implementation exists yet, so this uses an empty coverage source.
        coverage = _FixedCoverageSource({})

        allocated, ordered, delivered, fulfilled_from_stock = compute_coverage_totals(
            allocations, coverage, stock_source_value="stock", rank=0, fill={}
        )
        assert allocated == 8.0
        assert ordered == 0.0
        assert delivered == 0.0
        assert fulfilled_from_stock == 2.0

    def test_unplaced_coverage_contributes_nothing_to_ordered_or_delivered(self):
        allocations = [_Alloc(quantity=6.0, source="lot", coverage_ref_id=1)]
        coverage = _FixedCoverageSource({1: CoverageInfo(is_placed=False, arrived=0.0)})

        allocated, ordered, delivered, fulfilled_from_stock = compute_coverage_totals(
            allocations, coverage, stock_source_value="stock", rank=0, fill={}
        )
        assert allocated == 6.0
        assert ordered == 0.0
        assert delivered == 0.0
        assert fulfilled_from_stock == 0.0
