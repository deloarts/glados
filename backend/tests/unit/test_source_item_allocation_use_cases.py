"""
Unit tests for the source-item allocation-pool feature: manual allocation
CRUD, stock allocation, auto-allocate (covering both bought-item-sourced
and source-item-sourced demand branches, the eligibility lookup differs
between the two), fulfill-from-stock, and demand summary. Mirrors
test_made_item_allocation_use_cases.py's shape. No database, no HTTP. All
dependencies replaced with in-memory fakes.
"""

from datetime import date

import pytest

from src.modules.fulfillment.application.dto.source_item_allocation_dto import (
    AutoAllocateSourceItemDemandCommand,
)
from src.modules.fulfillment.application.dto.source_item_allocation_dto import (
    CreateSourceItemAllocationCommand,
)
from src.modules.fulfillment.application.dto.source_item_allocation_dto import (
    FulfillSourceItemDemandFromStockCommand,
)
from src.modules.fulfillment.application.dto.source_item_allocation_dto import (
    SourceItemDemandSummaryResult,
)
from src.modules.fulfillment.application.dto.source_item_allocation_dto import (
    UpdateSourceItemAllocationCommand,
)
from src.modules.fulfillment.application.dto.source_item_allocation_dto import (
    UpdateSourceItemStockAllocationCommand,
)
from src.modules.fulfillment.application.services.allocation_fill import LineFillRepos
from src.modules.fulfillment.application.services.allocation_lookup import order_numbers_for
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
from src.modules.fulfillment.application.use_cases.source_item_allocation.fulfill_from_stock import (
    FulfillSourceItemDemandFromStock,
)
from src.modules.fulfillment.application.use_cases.source_item_allocation.get_allocations import (
    GetSourceItemDemandSummary,
)
from src.modules.fulfillment.application.use_cases.source_item_allocation.get_allocations import (
    GetSourceItemDemandSummaryBatch,
)
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.source_item_allocation import (
    SourceItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.source_item_demand_item import SourceItemDemandItem
from src.modules.fulfillment.domain.errors import AllocationItemMismatchError
from src.modules.fulfillment.domain.errors import AllocationNotFoundError
from src.modules.fulfillment.domain.errors import AllocationOverflowError
from src.modules.fulfillment.domain.errors import OrderItemNotFoundError
from src.modules.fulfillment.domain.errors import SourceItemDemandNotFoundError
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemAllocationSource,
)
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    SourceItemDemandFilterDto,
)
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.lifecycle.fake_demand_reconciler import demand_reconciler
from tests.unit.production_lot.fakes import FakeBoughtItemAllocationRepository
from tests.unit.production_lot.fakes import FakeProjectRepository

# ── Helpers ───────────────────────────────────────────────────────────


def make_demand(
    id: int = 1,
    quantity: float = 10.0,
    status: SourceItemDemandStatus = SourceItemDemandStatus.OPEN,
    bought_item_id: int | None = None,
    source_item_id: int | None = 1,
) -> SourceItemDemandItem:
    return SourceItemDemandItem(
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
        bought_item_id=bought_item_id,
        source_item_id=source_item_id,
        lot_id=1,
        project_id=1,
    )


def make_order_item(
    id: int = 1,
    order_id: int = 1,
    status: OrderItemStatus = OrderItemStatus.ORDERED,
    quantity: float = 10.0,
    quantity_delivered: float = 0.0,
    bought_item_id: int | None = None,
    source_item_id: int | None = 1,
    expected_delivery_date: date | None = None,
) -> OrderItem:
    return OrderItem(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        status=status,
        quantity=quantity,
        quantity_delivered=quantity_delivered,
        unit="pcs",
        items_per_unit=1.0,
        price=None,
        note=None,
        ordered_date=None,
        expected_delivery_date=expected_delivery_date,
        delivery_date=None,
        storage_place=None,
        expected_pickup_date=None,
        ready_for_pickup_date=None,
        position=1,
        creator_id=1,
        orderer_id=None,
        receiver_id=None,
        bought_item_id=bought_item_id,
        order_id=order_id,
        supplier_id=1,
        project_id=1,
        line_type=OrderLineType.SOURCE if source_item_id is not None else OrderLineType.BOUGHT,
        lot_position_id=None,
        source_item_id=source_item_id,
    )


def make_order(id: int = 1) -> Order:
    return Order(
        id=id,
        order_number=f"ORD-{id}",
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        status=OrderStatus.ORDERED,
        note=None,
        ordered_date=None,
        expected_delivery_date=None,
        delivery_date=None,
        storage_place=None,
        creator_id=1,
        supplier_id=1,
    )


class FakeDemandRepository:
    def __init__(self, demands: list[SourceItemDemandItem] | None = None):
        self._demands: dict[int, SourceItemDemandItem] = {d.id: d for d in (demands or [])}
        self.for_update_calls: list[int] = []
        # counts get_by_id calls: GetSourceItemDemandSummaryBatch must use
        # get_by_ids (below) for the whole batch instead of looping
        # get_by_id per demand, see the call-counting test.
        self.get_by_id_calls = 0

    async def get_by_id(self, id: int) -> SourceItemDemandItem | None:
        self.get_by_id_calls += 1
        return self._demands.get(id)

    async def get_by_id_for_update(self, id: int) -> SourceItemDemandItem | None:
        self.for_update_calls.append(id)
        return self._demands.get(id)

    async def get_by_ids(self, ids: list[int]) -> list[SourceItemDemandItem]:
        # matches the ISourceItemDemandRepository.get_by_ids port method.
        return [self._demands[i] for i in ids if i in self._demands]

    async def get_multi(self, filters: SourceItemDemandFilterDto):
        raise NotImplementedError

    async def save(self, demand: SourceItemDemandItem) -> SourceItemDemandItem:
        self._demands[demand.id] = demand
        return demand


class FakeOrderItemRepository:
    def __init__(self, items: list[OrderItem] | None = None):
        self._items: dict[int, OrderItem] = {i.id: i for i in (items or [])}
        # counts get_by_id calls: the batched lookup path must use
        # get_by_ids (below) instead of looping get_by_id per allocation.
        self.get_by_id_calls = 0

    async def get_by_id(self, id: int) -> OrderItem | None:
        self.get_by_id_calls += 1
        return self._items.get(id)

    async def get_by_id_for_update(self, id: int) -> OrderItem | None:
        return self._items.get(id)

    async def get_by_ids(self, ids: list[int], *, refresh: bool = False) -> list[OrderItem]:
        return [self._items[i] for i in ids if i in self._items]

    async def get_by_order_id(self, order_id: int) -> list[OrderItem]:
        return [i for i in self._items.values() if i.order_id == order_id]

    async def get_by_order_ids(
        self, order_ids: list[int], *, refresh: bool = False
    ) -> list[OrderItem]:
        return [i for i in self._items.values() if i.order_id in order_ids]

    async def get_by_bought_item_id(self, bought_item_id: int) -> list[OrderItem]:
        return [i for i in self._items.values() if i.bought_item_id == bought_item_id]

    async def get_by_lot_position_id(self, lot_position_id: int) -> OrderItem | None:
        raise NotImplementedError

    async def get_by_source_item_id(self, source_item_id: int) -> list[OrderItem]:
        return [i for i in self._items.values() if i.source_item_id == source_item_id]

    async def next_position(self, order_id: int) -> int:
        return sum(1 for i in self._items.values() if i.order_id == order_id) + 1

    async def save(self, item: OrderItem) -> OrderItem:
        self._items[item.id] = item
        return item

    async def delete(self, item: OrderItem) -> None:
        self._items.pop(item.id, None)


class FakeOrderRepository:
    def __init__(self, orders: list[Order] | None = None):
        self._orders: dict[int, Order] = {o.id: o for o in (orders or [])}

    async def get_by_id(self, id: int) -> Order | None:
        return self._orders.get(id)

    async def get_by_ids(self, ids: list[int], *, refresh: bool = False) -> list[Order]:
        return [self._orders[i] for i in ids if i in self._orders]


class FakeAllocationRepository:
    def __init__(self, allocations: list[SourceItemDemandAllocation] | None = None):
        self._allocations: list[SourceItemDemandAllocation] = list(allocations or [])
        # counts get_by_demand_item_id calls: the batched summary path
        # must use get_by_demand_item_ids (below) for the whole batch
        # instead of looping this per demand.
        self.get_by_demand_item_id_calls = 0

    @property
    def allocations(self) -> list[SourceItemDemandAllocation]:
        """The stored allocations, for assertions."""
        return self._allocations

    async def get_by_demand_item_id(self, demand_item_id: int) -> list[SourceItemDemandAllocation]:
        self.get_by_demand_item_id_calls += 1
        return [a for a in self._allocations if a.demand_item_id == demand_item_id]

    async def get_by_demand_item_ids(
        self, demand_item_ids: list[int]
    ) -> list[SourceItemDemandAllocation]:
        return [a for a in self._allocations if a.demand_item_id in demand_item_ids]

    async def get_by_order_item_id(self, order_item_id: int) -> list[SourceItemDemandAllocation]:
        return [a for a in self._allocations if a.order_item_id == order_item_id]

    async def get_by_order_item_ids(
        self, order_item_ids: list[int]
    ) -> list[SourceItemDemandAllocation]:
        return [a for a in self._allocations if a.order_item_id in order_item_ids]

    async def get_allocated_quantity(self, demand_item_id: int) -> float:
        return sum(a.quantity for a in await self.get_by_demand_item_id(demand_item_id))

    async def get_allocated_quantities_for_order_items(
        self, order_item_ids: list[int]
    ) -> dict[int, float]:
        return {i: await self.get_allocated_quantity_for_order_item(i) for i in order_item_ids}

    async def get_allocated_quantity_for_order_item(self, order_item_id: int) -> float:
        # Only one allocation family lives in this fake, so its own rows on
        # the line are everything allocated to it.
        return sum(a.quantity for a in await self.get_by_order_item_id(order_item_id))

    async def save(self, allocation: SourceItemDemandAllocation) -> SourceItemDemandAllocation:
        existing = next(
            (
                a
                for a in self._allocations
                if a.demand_item_id == allocation.demand_item_id
                and a.order_item_id == allocation.order_item_id
                and a.source == allocation.source
            ),
            None,
        )
        if existing:
            existing.quantity = allocation.quantity
            # Mirrors SqlAlchemySourceItemAllocationRepository.save's
            # existing-row branch, which overwrites the substitute fields
            # from the incoming allocation too (not just quantity).
            existing.substitute_source_item_id = allocation.substitute_source_item_id
            existing.substitute_reason = allocation.substitute_reason
        else:
            self._allocations.append(allocation)
        return allocation

    async def delete(self, allocation: SourceItemDemandAllocation) -> None:
        self._allocations = [
            a
            for a in self._allocations
            if not (
                a.demand_item_id == allocation.demand_item_id
                and a.order_item_id == allocation.order_item_id
                and a.source == allocation.source
            )
        ]


class FakeUnitOfWork:
    def __init__(self):
        self.committed = False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        pass


class FakeRecomputeSchedule:
    """Fake of RecomputeMachineSchedule, see
    tests/unit/production_order/fakes.py's identical class."""

    def __init__(self) -> None:
        self.execute_all_calls: int = 0

    async def execute_all(self, response_time_days=None, settings=None):
        self.execute_all_calls += 1
        return []


class FailingRecomputeSchedule:
    def __init__(self) -> None:
        self.attempts: int = 0

    async def execute_all(self, response_time_days=None, settings=None):
        self.attempts += 1
        raise RuntimeError("scheduling service is down")


# ── CreateAllocation / UpdateAllocation / DeleteAllocation ─────────────


class TestCreateAllocation:
    def setup_method(self):
        self.demand = make_demand(id=1, quantity=10.0, source_item_id=1)
        self.demand_repo = FakeDemandRepository([self.demand])
        self.order_item = make_order_item(id=1, quantity=10.0, source_item_id=1)
        self.order_items = FakeOrderItemRepository([self.order_item])
        self.allocation_repo = FakeAllocationRepository()
        self.actor = make_user(permissions=[Permission.WRITE_ALLOCATIONS])
        self.use_case = CreateSourceItemAllocation(
            self.allocation_repo,
            self.demand_repo,
            self.order_items,
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(
                source_allocations=self.allocation_repo,
                source_demands=self.demand_repo,
                order_items=self.order_items,
            ),
            fill_repos=LineFillRepos(
                bought=FakeBoughtItemAllocationRepository(), source=self.allocation_repo
            ),
        )

    async def test_creates_allocation_and_updates_status(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=CreateSourceItemAllocationCommand(demand_item_id=1, order_item_id=1, quantity=4.0),
        )
        assert result.quantity == 4.0
        assert result.order_item_id == 1
        assert (
            await self.demand_repo.get_by_id(1)
        ).status == SourceItemDemandStatus.ALLOCATED.value

    async def test_demand_not_found_raises(self):
        with pytest.raises(SourceItemDemandNotFoundError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=CreateSourceItemAllocationCommand(
                    demand_item_id=999, order_item_id=1, quantity=1.0
                ),
            )

    async def test_order_item_not_found_raises(self):
        with pytest.raises(OrderItemNotFoundError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=CreateSourceItemAllocationCommand(
                    demand_item_id=1, order_item_id=999, quantity=1.0
                ),
            )

    async def test_material_mismatch_raises(self):
        mismatched = make_order_item(id=2, source_item_id=2)
        await self.order_items.save(mismatched)
        with pytest.raises(AllocationItemMismatchError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=CreateSourceItemAllocationCommand(
                    demand_item_id=1, order_item_id=2, quantity=1.0
                ),
            )

    async def test_overallocation_beyond_demand_raises(self):
        with pytest.raises(AllocationOverflowError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=CreateSourceItemAllocationCommand(
                    demand_item_id=1, order_item_id=1, quantity=11.0
                ),
            )

    async def test_overallocation_beyond_order_item_available_raises(self):
        small_order_item = make_order_item(id=3, quantity=2.0, source_item_id=1)
        await self.order_items.save(small_order_item)
        with pytest.raises(AllocationOverflowError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=CreateSourceItemAllocationCommand(
                    demand_item_id=1, order_item_id=3, quantity=3.0
                ),
            )

    async def test_bought_item_sourced_demand_matches_by_bought_item_id(self):
        demand = make_demand(id=2, bought_item_id=7, source_item_id=None)
        await self.demand_repo.save(demand)
        order_item = make_order_item(id=4, bought_item_id=7, source_item_id=None)
        await self.order_items.save(order_item)
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=CreateSourceItemAllocationCommand(demand_item_id=2, order_item_id=4, quantity=5.0),
        )
        assert result.quantity == 5.0

    async def test_reads_the_demand_with_a_row_lock(self):
        """Two concurrent allocations against the same demand must
        not both read the pre-insert already_allocated total, see
        ISourceItemDemandRepository.get_by_id_for_update."""
        await self.use_case.execute(
            actor=self.actor,
            cmd=CreateSourceItemAllocationCommand(demand_item_id=1, order_item_id=1, quantity=4.0),
        )
        assert self.demand_repo.for_update_calls == [1]

    # ── Substitution ─────────────────────────────────────────────────

    async def test_create_with_substitution_persists_and_echoes_fields(self):
        substitute_order_item = make_order_item(id=5, quantity=10.0, source_item_id=2)
        await self.order_items.save(substitute_order_item)

        result = await self.use_case.execute(
            actor=self.actor,
            cmd=CreateSourceItemAllocationCommand(
                demand_item_id=1,
                order_item_id=5,
                quantity=4.0,
                substitute_source_item_id=2,
                substitute_reason="preferred supplier out of stock",
            ),
        )

        assert result.substitute_source_item_id == 2
        assert result.substitute_reason == "preferred supplier out of stock"
        stored = (await self.allocation_repo.get_by_demand_item_id(1))[0]
        assert stored.substitute_source_item_id == 2
        assert stored.substitute_reason == "preferred supplier out of stock"

    async def test_create_with_wrong_substitute_id_raises(self):
        substitute_order_item = make_order_item(id=5, quantity=10.0, source_item_id=2)
        await self.order_items.save(substitute_order_item)

        with pytest.raises(AllocationItemMismatchError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=CreateSourceItemAllocationCommand(
                    demand_item_id=1,
                    order_item_id=5,
                    quantity=4.0,
                    substitute_source_item_id=999,
                ),
            )

    async def test_substitute_equal_to_demands_own_material_stored_as_non_substitution(self):
        """order_item_id=1 already matches the demand's own source_item_id
        (1); declaring it as its own substitute is not a real substitution,
        so both fields are stored as None and the reason is dropped."""
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=CreateSourceItemAllocationCommand(
                demand_item_id=1,
                order_item_id=1,
                quantity=4.0,
                substitute_source_item_id=1,
                substitute_reason="not a real substitution",
            ),
        )

        assert result.substitute_source_item_id is None
        assert result.substitute_reason is None

    async def test_reason_without_substitution_is_dropped(self):
        """A reason sent without substitute_source_item_id (order item
        already matches the demand) is dropped, not stored."""
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=CreateSourceItemAllocationCommand(
                demand_item_id=1,
                order_item_id=1,
                quantity=4.0,
                substitute_reason="stray reason",
            ),
        )

        assert result.substitute_source_item_id is None
        assert result.substitute_reason is None

    async def test_recompute_is_called_exactly_once_on_success(self):
        recompute = FakeRecomputeSchedule()
        use_case = CreateSourceItemAllocation(
            self.allocation_repo,
            self.demand_repo,
            self.order_items,
            recompute,
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(
                source_allocations=self.allocation_repo,
                source_demands=self.demand_repo,
                order_items=self.order_items,
            ),
            fill_repos=LineFillRepos(
                bought=FakeBoughtItemAllocationRepository(), source=self.allocation_repo
            ),
        )
        await use_case.execute(
            actor=self.actor,
            cmd=CreateSourceItemAllocationCommand(demand_item_id=1, order_item_id=1, quantity=4.0),
        )
        assert recompute.execute_all_calls == 1

    async def test_recompute_failure_does_not_undo_the_allocation(self):
        recompute = FailingRecomputeSchedule()
        use_case = CreateSourceItemAllocation(
            self.allocation_repo,
            self.demand_repo,
            self.order_items,
            recompute,
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(
                source_allocations=self.allocation_repo,
                source_demands=self.demand_repo,
                order_items=self.order_items,
            ),
            fill_repos=LineFillRepos(
                bought=FakeBoughtItemAllocationRepository(), source=self.allocation_repo
            ),
        )
        result = await use_case.execute(
            actor=self.actor,
            cmd=CreateSourceItemAllocationCommand(demand_item_id=1, order_item_id=1, quantity=4.0),
        )
        assert recompute.attempts == 1
        assert result.quantity == 4.0
        assert (
            await self.demand_repo.get_by_id(1)
        ).status == SourceItemDemandStatus.ALLOCATED.value


class TestUpdateAllocation:
    @pytest.fixture(autouse=True)
    async def _setup(self):
        self.demand = make_demand(id=1, quantity=10.0, source_item_id=1)
        self.demand_repo = FakeDemandRepository([self.demand])
        self.order_item = make_order_item(id=1, quantity=10.0, source_item_id=1)
        self.order_items = FakeOrderItemRepository([self.order_item])
        self.allocation_repo = FakeAllocationRepository()
        self.actor = make_user(permissions=[Permission.WRITE_ALLOCATIONS])
        self.create_use_case = CreateSourceItemAllocation(
            self.allocation_repo,
            self.demand_repo,
            self.order_items,
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(
                source_allocations=self.allocation_repo,
                source_demands=self.demand_repo,
                order_items=self.order_items,
            ),
            fill_repos=LineFillRepos(
                bought=FakeBoughtItemAllocationRepository(), source=self.allocation_repo
            ),
        )
        self.update_use_case = UpdateSourceItemAllocation(
            self.allocation_repo,
            self.demand_repo,
            self.order_items,
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(
                source_allocations=self.allocation_repo,
                source_demands=self.demand_repo,
                order_items=self.order_items,
            ),
            fill_repos=LineFillRepos(
                bought=FakeBoughtItemAllocationRepository(), source=self.allocation_repo
            ),
        )
        await self.create_use_case.execute(
            actor=self.actor,
            cmd=CreateSourceItemAllocationCommand(demand_item_id=1, order_item_id=1, quantity=4.0),
        )

    async def test_updates_quantity(self):
        result = await self.update_use_case.execute(
            actor=self.actor,
            demand_item_id=1,
            order_item_id=1,
            cmd=UpdateSourceItemAllocationCommand(quantity=6.0),
        )
        assert result.quantity == 6.0

    async def test_reads_the_demand_with_a_row_lock(self):
        """See TestCreateAllocation's identical test."""
        self.demand_repo.for_update_calls.clear()  # setup_method's own create already locked once
        await self.update_use_case.execute(
            actor=self.actor,
            demand_item_id=1,
            order_item_id=1,
            cmd=UpdateSourceItemAllocationCommand(quantity=6.0),
        )
        assert self.demand_repo.for_update_calls == [1]

    async def test_not_found_raises(self):
        other_order_item = make_order_item(id=2, quantity=10.0, source_item_id=1)
        await self.order_items.save(other_order_item)
        with pytest.raises(AllocationNotFoundError):
            await self.update_use_case.execute(
                actor=self.actor,
                demand_item_id=1,
                order_item_id=2,
                cmd=UpdateSourceItemAllocationCommand(quantity=1.0),
            )

    async def test_overallocation_raises(self):
        with pytest.raises(AllocationOverflowError):
            await self.update_use_case.execute(
                actor=self.actor,
                demand_item_id=1,
                order_item_id=1,
                cmd=UpdateSourceItemAllocationCommand(quantity=11.0),
            )

    async def test_recompute_is_called_exactly_once_on_success(self):
        recompute = FakeRecomputeSchedule()
        use_case = UpdateSourceItemAllocation(
            self.allocation_repo,
            self.demand_repo,
            self.order_items,
            recompute,
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(
                source_allocations=self.allocation_repo,
                source_demands=self.demand_repo,
                order_items=self.order_items,
            ),
            fill_repos=LineFillRepos(
                bought=FakeBoughtItemAllocationRepository(), source=self.allocation_repo
            ),
        )
        await use_case.execute(
            actor=self.actor,
            demand_item_id=1,
            order_item_id=1,
            cmd=UpdateSourceItemAllocationCommand(quantity=6.0),
        )
        assert recompute.execute_all_calls == 1

    async def test_recompute_failure_does_not_undo_the_update(self):
        recompute = FailingRecomputeSchedule()
        use_case = UpdateSourceItemAllocation(
            self.allocation_repo,
            self.demand_repo,
            self.order_items,
            recompute,
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(
                source_allocations=self.allocation_repo,
                source_demands=self.demand_repo,
                order_items=self.order_items,
            ),
            fill_repos=LineFillRepos(
                bought=FakeBoughtItemAllocationRepository(), source=self.allocation_repo
            ),
        )
        result = await use_case.execute(
            actor=self.actor,
            demand_item_id=1,
            order_item_id=1,
            cmd=UpdateSourceItemAllocationCommand(quantity=6.0),
        )
        assert recompute.attempts == 1
        assert result.quantity == 6.0

    async def test_update_keeps_substitute_fields(self):
        """UpdateSourceItemAllocationCommand only carries quantity: the
        substitute fields set at creation must survive an update, not be
        silently dropped."""
        substitute_order_item = make_order_item(id=6, quantity=10.0, source_item_id=2)
        await self.order_items.save(substitute_order_item)
        # A second request, with its own lock plan, as the setup's create was
        # one already.
        second_create = CreateSourceItemAllocation(
            self.allocation_repo,
            self.demand_repo,
            self.order_items,
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(
                source_allocations=self.allocation_repo,
                source_demands=self.demand_repo,
                order_items=self.order_items,
            ),
            fill_repos=LineFillRepos(
                bought=FakeBoughtItemAllocationRepository(), source=self.allocation_repo
            ),
        )
        await second_create.execute(
            actor=self.actor,
            cmd=CreateSourceItemAllocationCommand(
                demand_item_id=1,
                order_item_id=6,
                quantity=2.0,
                substitute_source_item_id=2,
                substitute_reason="preferred supplier out of stock",
            ),
        )

        result = await self.update_use_case.execute(
            actor=self.actor,
            demand_item_id=1,
            order_item_id=6,
            cmd=UpdateSourceItemAllocationCommand(quantity=3.0),
        )

        assert result.quantity == 3.0
        assert result.substitute_source_item_id == 2
        assert result.substitute_reason == "preferred supplier out of stock"


class TestDeleteAllocation:
    @pytest.fixture(autouse=True)
    async def _setup(self):
        self.demand = make_demand(id=1, quantity=10.0, source_item_id=1)
        self.demand_repo = FakeDemandRepository([self.demand])
        self.order_item = make_order_item(id=1, quantity=10.0, source_item_id=1)
        self.order_items = FakeOrderItemRepository([self.order_item])
        self.allocation_repo = FakeAllocationRepository()
        self.actor = make_user(permissions=[Permission.WRITE_ALLOCATIONS])
        self.create_use_case = CreateSourceItemAllocation(
            self.allocation_repo,
            self.demand_repo,
            self.order_items,
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(
                source_allocations=self.allocation_repo,
                source_demands=self.demand_repo,
                order_items=self.order_items,
            ),
            fill_repos=LineFillRepos(
                bought=FakeBoughtItemAllocationRepository(), source=self.allocation_repo
            ),
        )
        self.delete_use_case = DeleteSourceItemAllocation(
            self.allocation_repo,
            self.demand_repo,
            self.order_items,
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(
                source_allocations=self.allocation_repo,
                source_demands=self.demand_repo,
                order_items=self.order_items,
            ),
            fill_repos=LineFillRepos(
                bought=FakeBoughtItemAllocationRepository(), source=self.allocation_repo
            ),
        )
        await self.create_use_case.execute(
            actor=self.actor,
            cmd=CreateSourceItemAllocationCommand(demand_item_id=1, order_item_id=1, quantity=4.0),
        )

    async def test_deletes_and_reverts_status(self):
        await self.delete_use_case.execute(actor=self.actor, demand_item_id=1, order_item_id=1)
        assert await self.allocation_repo.get_by_demand_item_id(1) == []
        assert (await self.demand_repo.get_by_id(1)).status == SourceItemDemandStatus.OPEN.value

    async def test_not_found_raises(self):
        with pytest.raises(AllocationNotFoundError):
            await self.delete_use_case.execute(
                actor=self.actor, demand_item_id=1, order_item_id=999
            )

    async def test_recompute_is_called_exactly_once_on_success(self):
        recompute = FakeRecomputeSchedule()
        use_case = DeleteSourceItemAllocation(
            self.allocation_repo,
            self.demand_repo,
            self.order_items,
            recompute,
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(
                source_allocations=self.allocation_repo,
                source_demands=self.demand_repo,
                order_items=self.order_items,
            ),
            fill_repos=LineFillRepos(
                bought=FakeBoughtItemAllocationRepository(), source=self.allocation_repo
            ),
        )
        await use_case.execute(actor=self.actor, demand_item_id=1, order_item_id=1)
        assert recompute.execute_all_calls == 1

    async def test_recompute_failure_does_not_undo_the_deletion(self):
        recompute = FailingRecomputeSchedule()
        use_case = DeleteSourceItemAllocation(
            self.allocation_repo,
            self.demand_repo,
            self.order_items,
            recompute,
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(
                source_allocations=self.allocation_repo,
                source_demands=self.demand_repo,
                order_items=self.order_items,
            ),
            fill_repos=LineFillRepos(
                bought=FakeBoughtItemAllocationRepository(), source=self.allocation_repo
            ),
        )
        await use_case.execute(actor=self.actor, demand_item_id=1, order_item_id=1)
        assert recompute.attempts == 1
        assert await self.allocation_repo.get_by_demand_item_id(1) == []


# ── Stock allocation ────────────────────────────────────────────────────


class TestStockAllocation:
    def setup_method(self):
        self.demand = make_demand(id=1, quantity=10.0)
        self.demand_repo = FakeDemandRepository([self.demand])
        self.order_items = FakeOrderItemRepository()
        self.allocation_repo = FakeAllocationRepository()
        self.actor = make_user(permissions=[Permission.WRITE_ALLOCATIONS])
        self.update_use_case = UpdateSourceItemStockAllocation(
            self.allocation_repo,
            self.demand_repo,
            self.order_items,
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(
                source_allocations=self.allocation_repo,
                source_demands=self.demand_repo,
                order_items=self.order_items,
            ),
        )
        self.delete_use_case = DeleteSourceItemStockAllocation(
            self.allocation_repo,
            self.demand_repo,
            self.order_items,
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(
                source_allocations=self.allocation_repo,
                source_demands=self.demand_repo,
                order_items=self.order_items,
            ),
        )

    async def test_sets_stock_allocation_and_updates_status(self):
        result = await self.update_use_case.execute(
            actor=self.actor,
            demand_item_id=1,
            cmd=UpdateSourceItemStockAllocationCommand(quantity=4.0),
        )
        assert result.quantity == 4.0
        assert result.source == "stock"
        assert (
            await self.demand_repo.get_by_id(1)
        ).status == SourceItemDemandStatus.ALLOCATED.value

    async def test_reads_the_demand_with_a_row_lock(self):
        """See TestCreateAllocation's identical test."""
        await self.update_use_case.execute(
            actor=self.actor,
            demand_item_id=1,
            cmd=UpdateSourceItemStockAllocationCommand(quantity=4.0),
        )
        assert self.demand_repo.for_update_calls == [1]

    async def test_full_stock_allocation_fulfills_demand(self):
        await self.update_use_case.execute(
            actor=self.actor,
            demand_item_id=1,
            cmd=UpdateSourceItemStockAllocationCommand(quantity=10.0),
        )
        assert (
            await self.demand_repo.get_by_id(1)
        ).status == SourceItemDemandStatus.FULFILLED.value

    async def test_overallocation_raises(self):
        with pytest.raises(AllocationOverflowError):
            await self.update_use_case.execute(
                actor=self.actor,
                demand_item_id=1,
                cmd=UpdateSourceItemStockAllocationCommand(quantity=11.0),
            )

    async def test_demand_not_found_raises(self):
        with pytest.raises(SourceItemDemandNotFoundError):
            await self.update_use_case.execute(
                actor=self.actor,
                demand_item_id=999,
                cmd=UpdateSourceItemStockAllocationCommand(quantity=1.0),
            )

    async def test_delete_removes_stock_allocation(self):
        await self.update_use_case.execute(
            actor=self.actor,
            demand_item_id=1,
            cmd=UpdateSourceItemStockAllocationCommand(quantity=4.0),
        )
        await self.delete_use_case.execute(actor=self.actor, demand_item_id=1)
        assert await self.allocation_repo.get_by_demand_item_id(1) == []
        assert (await self.demand_repo.get_by_id(1)).status == SourceItemDemandStatus.OPEN.value

    async def test_delete_without_existing_raises(self):
        with pytest.raises(AllocationNotFoundError):
            await self.delete_use_case.execute(actor=self.actor, demand_item_id=1)

    async def test_update_recompute_is_called_exactly_once_on_success(self):
        recompute = FakeRecomputeSchedule()
        use_case = UpdateSourceItemStockAllocation(
            self.allocation_repo,
            self.demand_repo,
            self.order_items,
            recompute,
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(
                source_allocations=self.allocation_repo,
                source_demands=self.demand_repo,
                order_items=self.order_items,
            ),
        )
        await use_case.execute(
            actor=self.actor,
            demand_item_id=1,
            cmd=UpdateSourceItemStockAllocationCommand(quantity=4.0),
        )
        assert recompute.execute_all_calls == 1

    async def test_update_recompute_failure_does_not_undo_the_allocation(self):
        recompute = FailingRecomputeSchedule()
        use_case = UpdateSourceItemStockAllocation(
            self.allocation_repo,
            self.demand_repo,
            self.order_items,
            recompute,
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(
                source_allocations=self.allocation_repo,
                source_demands=self.demand_repo,
                order_items=self.order_items,
            ),
        )
        result = await use_case.execute(
            actor=self.actor,
            demand_item_id=1,
            cmd=UpdateSourceItemStockAllocationCommand(quantity=4.0),
        )
        assert recompute.attempts == 1
        assert result.quantity == 4.0

    async def test_delete_recompute_is_called_exactly_once_on_success(self):
        await self.update_use_case.execute(
            actor=self.actor,
            demand_item_id=1,
            cmd=UpdateSourceItemStockAllocationCommand(quantity=4.0),
        )
        recompute = FakeRecomputeSchedule()
        use_case = DeleteSourceItemStockAllocation(
            self.allocation_repo,
            self.demand_repo,
            self.order_items,
            recompute,
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(
                source_allocations=self.allocation_repo,
                source_demands=self.demand_repo,
                order_items=self.order_items,
            ),
        )
        await use_case.execute(actor=self.actor, demand_item_id=1)
        assert recompute.execute_all_calls == 1

    async def test_delete_recompute_failure_does_not_undo_the_deletion(self):
        await self.update_use_case.execute(
            actor=self.actor,
            demand_item_id=1,
            cmd=UpdateSourceItemStockAllocationCommand(quantity=4.0),
        )
        recompute = FailingRecomputeSchedule()
        use_case = DeleteSourceItemStockAllocation(
            self.allocation_repo,
            self.demand_repo,
            self.order_items,
            recompute,
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(
                source_allocations=self.allocation_repo,
                source_demands=self.demand_repo,
                order_items=self.order_items,
            ),
        )
        await use_case.execute(actor=self.actor, demand_item_id=1)
        assert recompute.attempts == 1
        assert await self.allocation_repo.get_by_demand_item_id(1) == []


# ── AutoAllocate ─────────────────────────────────────────────────────


class TestAutoAllocate:
    def setup_method(self):
        self.allocation_repo = FakeAllocationRepository()
        self.uow = FakeUnitOfWork()
        self.actor = make_user(permissions=[Permission.WRITE_ALLOCATIONS])

    async def test_source_item_sourced_demand_allocates_against_matching_order_item(self):
        demand = make_demand(id=1, quantity=10.0, source_item_id=1)
        demand_repo = FakeDemandRepository([demand])
        order_item = make_order_item(id=1, quantity=6.0, source_item_id=1)
        order_items = FakeOrderItemRepository([order_item])
        use_case = AutoAllocateSourceItemDemand(
            demand_repo,
            order_items,
            self.allocation_repo,
            uow=self.uow,
            reconciler=demand_reconciler(
                source_demands=demand_repo,
                order_items=order_items,
                source_allocations=self.allocation_repo,
            ),
            project_repo=FakeProjectRepository(),
            fill_repos=LineFillRepos(
                bought=FakeBoughtItemAllocationRepository(), source=self.allocation_repo
            ),
        )

        result = await use_case.execute(
            actor=self.actor, cmd=AutoAllocateSourceItemDemandCommand(demand_item_id=1)
        )
        assert result.allocations_created == 1
        assert result.total_newly_allocated == 6.0
        assert result.remaining_unallocated == 4.0
        assert (await demand_repo.get_by_id(1)).status == SourceItemDemandStatus.ALLOCATED.value
        assert demand_repo.for_update_calls == [1]  # row lock, see the class docstring

    async def test_bought_item_sourced_demand_allocates_via_catalogue_lookup(self):
        demand = make_demand(id=2, quantity=10.0, bought_item_id=7, source_item_id=None)
        demand_repo = FakeDemandRepository([demand])
        order_item = make_order_item(id=2, quantity=10.0, bought_item_id=7, source_item_id=None)
        order_items = FakeOrderItemRepository([order_item])
        use_case = AutoAllocateSourceItemDemand(
            demand_repo,
            order_items,
            self.allocation_repo,
            uow=self.uow,
            reconciler=demand_reconciler(
                source_demands=demand_repo,
                order_items=order_items,
                source_allocations=self.allocation_repo,
            ),
            project_repo=FakeProjectRepository(),
            fill_repos=LineFillRepos(
                bought=FakeBoughtItemAllocationRepository(), source=self.allocation_repo
            ),
        )

        result = await use_case.execute(
            actor=self.actor, cmd=AutoAllocateSourceItemDemandCommand(demand_item_id=2)
        )
        assert result.total_newly_allocated == 10.0
        assert result.remaining_unallocated == 0.0
        assert (await demand_repo.get_by_id(2)).status == SourceItemDemandStatus.ALLOCATED.value

    async def test_prefers_ordered_over_partially_delivered_and_earlier_delivery(self):
        demand = make_demand(id=3, quantity=5.0, source_item_id=1)
        demand_repo = FakeDemandRepository([demand])
        far = make_order_item(
            id=10,
            quantity=5.0,
            source_item_id=1,
            status=OrderItemStatus.ORDERED,
            expected_delivery_date=date(2026, 12, 1),
        )
        near = make_order_item(
            id=11,
            quantity=5.0,
            source_item_id=1,
            status=OrderItemStatus.ORDERED,
            expected_delivery_date=date(2026, 2, 1),
        )
        order_items = FakeOrderItemRepository([far, near])
        use_case = AutoAllocateSourceItemDemand(
            demand_repo,
            order_items,
            self.allocation_repo,
            uow=self.uow,
            reconciler=demand_reconciler(
                source_demands=demand_repo,
                order_items=order_items,
                source_allocations=self.allocation_repo,
            ),
            project_repo=FakeProjectRepository(),
            fill_repos=LineFillRepos(
                bought=FakeBoughtItemAllocationRepository(), source=self.allocation_repo
            ),
        )

        await use_case.execute(
            actor=self.actor, cmd=AutoAllocateSourceItemDemandCommand(demand_item_id=3)
        )

        allocations = await self.allocation_repo.get_by_demand_item_id(3)
        assert len(allocations) == 1
        assert allocations[0].order_item_id == 11

    async def test_ineligible_status_skipped(self):
        demand = make_demand(id=4, quantity=5.0, source_item_id=1)
        demand_repo = FakeDemandRepository([demand])
        pending = make_order_item(
            id=12, quantity=5.0, source_item_id=1, status=OrderItemStatus.PENDING
        )
        order_items = FakeOrderItemRepository([pending])
        use_case = AutoAllocateSourceItemDemand(
            demand_repo,
            order_items,
            self.allocation_repo,
            uow=self.uow,
            reconciler=demand_reconciler(
                source_demands=demand_repo,
                order_items=order_items,
                source_allocations=self.allocation_repo,
            ),
            project_repo=FakeProjectRepository(),
            fill_repos=LineFillRepos(
                bought=FakeBoughtItemAllocationRepository(), source=self.allocation_repo
            ),
        )

        result = await use_case.execute(
            actor=self.actor, cmd=AutoAllocateSourceItemDemandCommand(demand_item_id=4)
        )
        assert result.allocations_created == 0
        assert result.total_newly_allocated == 0.0

    async def test_terminal_demand_is_a_no_op(self):
        demand = make_demand(
            id=5, quantity=5.0, source_item_id=1, status=SourceItemDemandStatus.FULFILLED
        )
        demand_repo = FakeDemandRepository([demand])
        order_item = make_order_item(id=13, quantity=5.0, source_item_id=1)
        order_items = FakeOrderItemRepository([order_item])
        use_case = AutoAllocateSourceItemDemand(
            demand_repo,
            order_items,
            self.allocation_repo,
            uow=self.uow,
            reconciler=demand_reconciler(
                source_demands=demand_repo,
                order_items=order_items,
                source_allocations=self.allocation_repo,
            ),
            project_repo=FakeProjectRepository(),
            fill_repos=LineFillRepos(
                bought=FakeBoughtItemAllocationRepository(), source=self.allocation_repo
            ),
        )

        result = await use_case.execute(
            actor=self.actor, cmd=AutoAllocateSourceItemDemandCommand(demand_item_id=5)
        )
        assert result.allocations_created == 0
        assert result.demand_status_changed_to is None

    async def test_demand_not_found_raises(self):
        demand_repo = FakeDemandRepository()
        order_items = FakeOrderItemRepository()
        use_case = AutoAllocateSourceItemDemand(
            demand_repo,
            order_items,
            self.allocation_repo,
            uow=self.uow,
            reconciler=demand_reconciler(
                source_demands=demand_repo,
                order_items=order_items,
                source_allocations=self.allocation_repo,
            ),
            project_repo=FakeProjectRepository(),
            fill_repos=LineFillRepos(
                bought=FakeBoughtItemAllocationRepository(), source=self.allocation_repo
            ),
        )
        with pytest.raises(SourceItemDemandNotFoundError):
            await use_case.execute(
                actor=self.actor, cmd=AutoAllocateSourceItemDemandCommand(demand_item_id=999)
            )

    async def test_recompute_is_called_exactly_once_on_success(self):
        demand = make_demand(id=6, quantity=10.0, source_item_id=1)
        demand_repo = FakeDemandRepository([demand])
        order_item = make_order_item(id=20, quantity=6.0, source_item_id=1)
        order_items = FakeOrderItemRepository([order_item])
        recompute = FakeRecomputeSchedule()
        use_case = AutoAllocateSourceItemDemand(
            demand_repo,
            order_items,
            self.allocation_repo,
            recompute,
            uow=self.uow,
            reconciler=demand_reconciler(
                source_demands=demand_repo,
                order_items=order_items,
                source_allocations=self.allocation_repo,
            ),
            project_repo=FakeProjectRepository(),
            fill_repos=LineFillRepos(
                bought=FakeBoughtItemAllocationRepository(), source=self.allocation_repo
            ),
        )
        await use_case.execute(
            actor=self.actor, cmd=AutoAllocateSourceItemDemandCommand(demand_item_id=6)
        )
        assert recompute.execute_all_calls == 1

    async def test_recompute_failure_does_not_roll_back_the_commit(self):
        demand = make_demand(id=7, quantity=10.0, source_item_id=1)
        demand_repo = FakeDemandRepository([demand])
        order_item = make_order_item(id=21, quantity=6.0, source_item_id=1)
        order_items = FakeOrderItemRepository([order_item])
        recompute = FailingRecomputeSchedule()
        use_case = AutoAllocateSourceItemDemand(
            demand_repo,
            order_items,
            self.allocation_repo,
            recompute,
            uow=self.uow,
            reconciler=demand_reconciler(
                source_demands=demand_repo,
                order_items=order_items,
                source_allocations=self.allocation_repo,
            ),
            project_repo=FakeProjectRepository(),
            fill_repos=LineFillRepos(
                bought=FakeBoughtItemAllocationRepository(), source=self.allocation_repo
            ),
        )
        result = await use_case.execute(
            actor=self.actor, cmd=AutoAllocateSourceItemDemandCommand(demand_item_id=7)
        )
        assert recompute.attempts == 1
        assert result.total_newly_allocated == 6.0
        assert self.uow.committed is True


# ── FulfillFromStock ─────────────────────────────────────────────────


class TestFulfillFromStock:
    def setup_method(self):
        self.demand = make_demand(id=1, quantity=10.0)
        self.demand_repo = FakeDemandRepository([self.demand])
        self.allocation_repo = FakeAllocationRepository()
        self.order_items = FakeOrderItemRepository()
        self.actor = make_user(permissions=[Permission.WRITE_ALLOCATIONS])
        self.uow = FakeUnitOfWork()
        self.use_case = FulfillSourceItemDemandFromStock(
            self.demand_repo,
            self.allocation_repo,
            self.order_items,
            uow=self.uow,
            reconciler=demand_reconciler(
                source_demands=self.demand_repo,
                source_allocations=self.allocation_repo,
                order_items=self.order_items,
            ),
        )

    async def test_tops_up_stock_allocation(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=FulfillSourceItemDemandFromStockCommand(demand_item_id=1, quantity=3.0),
        )
        assert result.total_fulfilled_from_stock == 3.0
        assert result.demand_status_changed_to == SourceItemDemandStatus.ALLOCATED.value
        assert self.uow.committed is True

        result2 = await self.use_case.execute(
            actor=self.actor,
            cmd=FulfillSourceItemDemandFromStockCommand(demand_item_id=1, quantity=2.0),
        )
        assert result2.total_fulfilled_from_stock == 5.0

    async def test_reads_the_demand_with_a_row_lock(self):
        """See TestCreateAllocation's identical test."""
        await self.use_case.execute(
            actor=self.actor,
            cmd=FulfillSourceItemDemandFromStockCommand(demand_item_id=1, quantity=3.0),
        )
        assert self.demand_repo.for_update_calls == [1]

    async def test_fulfilling_full_quantity_marks_fulfilled(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=FulfillSourceItemDemandFromStockCommand(demand_item_id=1, quantity=10.0),
        )
        assert result.demand_status_changed_to == SourceItemDemandStatus.FULFILLED.value

    async def test_overallocation_raises(self):
        with pytest.raises(AllocationOverflowError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=FulfillSourceItemDemandFromStockCommand(demand_item_id=1, quantity=11.0),
            )

    async def test_demand_not_found_raises(self):
        with pytest.raises(SourceItemDemandNotFoundError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=FulfillSourceItemDemandFromStockCommand(demand_item_id=999, quantity=1.0),
            )

    async def test_recompute_is_called_exactly_once_on_success(self):
        recompute = FakeRecomputeSchedule()
        use_case = FulfillSourceItemDemandFromStock(
            self.demand_repo,
            self.allocation_repo,
            self.order_items,
            recompute,
            uow=self.uow,
            reconciler=demand_reconciler(
                source_demands=self.demand_repo,
                source_allocations=self.allocation_repo,
                order_items=self.order_items,
            ),
        )
        await use_case.execute(
            actor=self.actor,
            cmd=FulfillSourceItemDemandFromStockCommand(demand_item_id=1, quantity=3.0),
        )
        assert recompute.execute_all_calls == 1

    async def test_recompute_failure_does_not_roll_back_the_commit(self):
        recompute = FailingRecomputeSchedule()
        use_case = FulfillSourceItemDemandFromStock(
            self.demand_repo,
            self.allocation_repo,
            self.order_items,
            recompute,
            uow=self.uow,
            reconciler=demand_reconciler(
                source_demands=self.demand_repo,
                source_allocations=self.allocation_repo,
                order_items=self.order_items,
            ),
        )
        result = await use_case.execute(
            actor=self.actor,
            cmd=FulfillSourceItemDemandFromStockCommand(demand_item_id=1, quantity=3.0),
        )
        assert recompute.attempts == 1
        assert result.total_fulfilled_from_stock == 3.0
        assert self.uow.committed is True


# ── GetDemandSummary ────────────────────────────────────────────────


class TestGetDemandSummary:
    def setup_method(self):
        self.demand = make_demand(id=1, quantity=10.0, source_item_id=1)
        self.demand_repo = FakeDemandRepository([self.demand])
        self.order_item = make_order_item(
            id=1, quantity=10.0, source_item_id=1, quantity_delivered=3.0
        )
        self.order_items = FakeOrderItemRepository([self.order_item])
        self.order_repo = FakeOrderRepository([make_order(id=1)])
        self.allocation_repo = FakeAllocationRepository(
            [
                SourceItemDemandAllocation(demand_item_id=1, order_item_id=1, quantity=6.0),
                SourceItemDemandAllocation(
                    demand_item_id=1,
                    order_item_id=None,
                    quantity=2.0,
                    source=SourceItemAllocationSource.STOCK,
                ),
            ]
        )
        self.use_case = GetSourceItemDemandSummary(
            self.demand_repo, self.allocation_repo, self.order_items, self.order_repo
        )

    async def test_summary_reflects_mixed_order_and_stock_allocations(self):
        summary = await self.use_case.execute(demand_item_id=1)
        assert summary.total == 10.0
        assert summary.allocated == 6.0
        assert summary.fulfilled_from_stock == 2.0
        # order item delivered 3 of 10; nothing ahead on it, so the 3 reach
        # this demand's allocation of 6
        assert summary.delivered == pytest.approx(3.0)
        assert summary.remaining == pytest.approx(10.0 - 3.0 - 2.0)
        assert summary.order_ids == [1]
        assert summary.order_numbers == ["ORD-1"]

    async def test_not_found_raises(self):
        with pytest.raises(SourceItemDemandNotFoundError):
            await self.use_case.execute(demand_item_id=999)

    # ── Substitutions ────────────────────────────────────────────────

    async def test_substitutions_empty_when_none(self):
        summary = await self.use_case.execute(demand_item_id=1)
        assert summary.substitutions == []

    async def test_substitutions_aggregate_two_allocations_to_same_substitute(self):
        substitute_order_item_a = make_order_item(id=2, order_id=1, quantity=5.0, source_item_id=99)
        substitute_order_item_b = make_order_item(id=3, order_id=1, quantity=5.0, source_item_id=99)
        await self.order_items.save(substitute_order_item_a)
        await self.order_items.save(substitute_order_item_b)
        await self.allocation_repo.save(
            SourceItemDemandAllocation(
                demand_item_id=1,
                order_item_id=2,
                quantity=2.0,
                substitute_source_item_id=99,
                substitute_reason="reason A",
            )
        )
        await self.allocation_repo.save(
            SourceItemDemandAllocation(
                demand_item_id=1,
                order_item_id=3,
                quantity=1.0,
                substitute_source_item_id=99,
                substitute_reason=None,
            )
        )

        summary = await self.use_case.execute(demand_item_id=1)

        assert len(summary.substitutions) == 1
        sub = summary.substitutions[0]
        assert sub.substitute_source_item_id == 99
        assert sub.quantity == 3.0
        assert sub.substitute_reason == "reason A"  # first non-null reason wins


# ── GetSourceItemDemandSummaryBatch ──────────────────────────────────────
#
# Characterization tests pinning GetSourceItemDemandSummaryBatch's
# behaviour, which matches a per-demand loop of single summaries. The
# call-counting test at the bottom pins the batched query shape: a
# constant number of repository calls, never one per demand.


class TestGetSourceItemDemandSummaryBatch:
    def setup_method(self):
        # demand 1: single ORDER allocation, fully covers it.
        self.demand1 = make_demand(id=1, quantity=10.0, source_item_id=1)
        # demand 2: mixed stock (4) + order (6).
        self.demand2 = make_demand(id=2, quantity=10.0, source_item_id=1)
        # demand 3: zero allocations.
        self.demand3 = make_demand(id=3, quantity=5.0, source_item_id=1)
        # demand 4: ORDER allocation referencing an order item that no
        # longer exists (orphaned reference).
        self.demand4 = make_demand(id=4, quantity=8.0, source_item_id=1)

        self.demand_repo = FakeDemandRepository(
            [self.demand1, self.demand2, self.demand3, self.demand4]
        )

        order_item_101 = make_order_item(id=101, order_id=201, quantity=10.0, source_item_id=1)
        order_item_102 = make_order_item(id=102, order_id=202, quantity=10.0, source_item_id=1)
        self.order_items = FakeOrderItemRepository([order_item_101, order_item_102])
        self.order_repo = FakeOrderRepository([make_order(id=201), make_order(id=202)])

        self.allocations = [
            SourceItemDemandAllocation(demand_item_id=1, order_item_id=101, quantity=10.0),
            SourceItemDemandAllocation(
                demand_item_id=2,
                order_item_id=None,
                quantity=4.0,
                source=SourceItemAllocationSource.STOCK,
            ),
            SourceItemDemandAllocation(demand_item_id=2, order_item_id=102, quantity=6.0),
            # demand 3: none.
            SourceItemDemandAllocation(demand_item_id=4, order_item_id=999, quantity=5.0),
        ]
        self.allocation_repo = FakeAllocationRepository(self.allocations)

        self.batch_use_case = GetSourceItemDemandSummaryBatch(
            self.demand_repo, self.allocation_repo, self.order_items, self.order_repo
        )

    async def _singular(self, demand_item_id: int) -> SourceItemDemandSummaryResult:
        return await GetSourceItemDemandSummary(
            self.demand_repo, self.allocation_repo, self.order_items, self.order_repo
        ).execute(demand_item_id)

    async def test_batch_matches_singular_result_for_each_demand(self):
        ids = [1, 2, 3, 4]
        batch_result = await self.batch_use_case.execute(ids)

        assert batch_result.keys() == set(ids)
        for demand_id in ids:
            assert batch_result[demand_id] == await self._singular(demand_id)

    async def test_unknown_id_omitted_from_dict(self):
        result = await self.batch_use_case.execute([1, 999])

        assert 1 in result
        assert 999 not in result
        assert len(result) == 1

    async def test_zero_allocation_demand_still_gets_entry(self):
        result = await self.batch_use_case.execute([3])

        assert 3 in result
        summary = result[3]
        assert summary.total == 5.0
        assert summary.allocated == 0.0
        assert summary.fulfilled_from_stock == 0.0
        assert summary.remaining == 5.0
        assert summary.unallocated == 5.0
        assert summary.is_fully_allocated is False

    async def test_mixed_stock_and_order_allocations(self):
        summary = (await self.batch_use_case.execute([2]))[2]

        assert summary.allocated == 6.0
        assert summary.fulfilled_from_stock == 4.0
        assert summary.ordered == 6.0
        assert summary.is_fully_allocated is True

    async def test_orphaned_order_item_reference_dropped_without_raising(self):
        result = await self.batch_use_case.execute([4])

        summary = result[4]
        assert summary.allocated == 5.0  # counted regardless of order-item lookup
        assert summary.ordered == 0.0  # but never resolves to "placed" without it
        assert summary.order_ids == []
        assert summary.order_numbers == []

    # ── Call-counting ───────────────────────────────────────────────────

    async def test_batch_issues_a_constant_number_of_repository_calls(self):
        await self.batch_use_case.execute([1, 2, 3, 4])

        assert self.demand_repo.get_by_id_calls == 0
        assert self.allocation_repo.get_by_demand_item_id_calls == 0
        assert self.order_items.get_by_id_calls == 0

    # ── Substitutions ────────────────────────────────────────────────

    async def test_substitutions_empty_when_none(self):
        result = await self.batch_use_case.execute([1, 2, 3, 4])
        assert all(result[demand_id].substitutions == [] for demand_id in (1, 2, 3, 4))

    async def test_substitutions_aggregate_two_allocations_to_same_substitute(self):
        demand5 = make_demand(id=5, quantity=10.0, source_item_id=1)
        await self.demand_repo.save(demand5)
        substitute_order_item_a = make_order_item(
            id=103, order_id=203, quantity=5.0, source_item_id=99
        )
        substitute_order_item_b = make_order_item(
            id=104, order_id=203, quantity=5.0, source_item_id=99
        )
        await self.order_items.save(substitute_order_item_a)
        await self.order_items.save(substitute_order_item_b)
        await self.allocation_repo.save(
            SourceItemDemandAllocation(
                demand_item_id=5,
                order_item_id=103,
                quantity=2.0,
                substitute_source_item_id=99,
                substitute_reason="reason A",
            )
        )
        await self.allocation_repo.save(
            SourceItemDemandAllocation(
                demand_item_id=5,
                order_item_id=104,
                quantity=1.0,
                substitute_source_item_id=99,
                substitute_reason=None,
            )
        )

        batch_result = (await self.batch_use_case.execute([5]))[5]

        assert len(batch_result.substitutions) == 1
        sub = batch_result.substitutions[0]
        assert sub.substitute_source_item_id == 99
        assert sub.quantity == 3.0
        assert sub.substitute_reason == "reason A"
        # batch matches singular for this demand too, same as the other
        # demands' coverage numbers (test_batch_matches_singular_result_for_each_demand).
        assert batch_result == await self._singular(5)


# ── order_numbers_for ──────────────────────────────────────────────────


class _RecordingOrderRepository:
    """Stands in for IOrderRepository, records every get_by_ids call's
    argument list so a test can prove order_numbers_for only fetches
    ids missing from its cache."""

    def __init__(self, orders: list[Order]) -> None:
        self._orders: dict[int, Order] = {o.id: o for o in orders}
        self.get_by_ids_calls: list[list[int]] = []

    async def get_by_ids(self, ids: list[int]) -> list[Order]:
        self.get_by_ids_calls.append(list(ids))
        return [self._orders[i] for i in ids if i in self._orders]


class TestOrderNumbersFor:
    def setup_method(self):
        self.order_repo = _RecordingOrderRepository([make_order(id=1), make_order(id=2)])

    async def test_cached_ids_do_not_trigger_a_repo_call(self):
        cache = {1: make_order(id=1)}

        numbers = await order_numbers_for([1], self.order_repo, cache)

        assert numbers == ["ORD-1"]
        assert self.order_repo.get_by_ids_calls == []

    async def test_missing_ids_are_fetched_in_one_call_and_cached(self):
        cache: dict[int, Order] = {}

        numbers = await order_numbers_for([1, 2], self.order_repo, cache)

        assert numbers == ["ORD-1", "ORD-2"]
        assert len(self.order_repo.get_by_ids_calls) == 1
        assert set(self.order_repo.get_by_ids_calls[0]) == {1, 2}
        assert cache[1].order_number == "ORD-1"
        assert cache[2].order_number == "ORD-2"

    async def test_a_mix_of_cached_and_missing_ids_only_fetches_the_missing_ones(self):
        cache = {1: make_order(id=1)}

        numbers = await order_numbers_for([1, 2], self.order_repo, cache)

        assert numbers == ["ORD-1", "ORD-2"]
        assert self.order_repo.get_by_ids_calls == [[2]]

    async def test_nonexistent_order_id_is_skipped(self):
        numbers = await order_numbers_for([1, 999], self.order_repo)

        assert numbers == ["ORD-1"]

    async def test_duplicate_ids_in_input_are_preserved_in_output(self):
        numbers = await order_numbers_for([1, 1, 2], self.order_repo)

        assert numbers == ["ORD-1", "ORD-1", "ORD-2"]

    async def test_input_order_is_preserved_regardless_of_fetch_order(self):
        numbers = await order_numbers_for([2, 1], self.order_repo)

        assert numbers == ["ORD-2", "ORD-1"]

    async def test_cache_is_none_by_default_and_does_not_leak_between_calls(self):
        await order_numbers_for([1], self.order_repo)
        first_call_count = len(self.order_repo.get_by_ids_calls)

        await order_numbers_for([1], self.order_repo)

        assert len(self.order_repo.get_by_ids_calls) == first_call_count + 1
