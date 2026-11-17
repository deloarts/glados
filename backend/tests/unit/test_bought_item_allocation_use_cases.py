"""
Unit tests for the bought-item allocation feature: manual allocation CRUD,
stock allocation, auto-allocate, and fulfill-from-stock. Mirrors
test_source_item_allocation_use_cases.py's shape, bought_item/create_
allocation.py, auto_allocate.py and fulfill_from_stock.py are structural
clones of their source_item_allocation counterparts (see those modules'
docstrings). No database, no HTTP. All dependencies replaced with
in-memory fakes.
"""

from datetime import UTC
from datetime import date
from datetime import datetime

import pytest

from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.value_objects.bought_item_status import AllocationSource
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.fulfillment.application.dto.allocation_dto import AutoAllocateCommand
from src.modules.fulfillment.application.dto.allocation_dto import CreateAllocationCommand
from src.modules.fulfillment.application.dto.allocation_dto import DemandSummaryResult
from src.modules.fulfillment.application.dto.allocation_dto import FulfillFromStockCommand
from src.modules.fulfillment.application.dto.allocation_dto import UpdateAllocationCommand
from src.modules.fulfillment.application.dto.allocation_dto import UpdateStockAllocationCommand
from src.modules.fulfillment.application.services.allocation_fill import LineFillRepos
from src.modules.fulfillment.application.services.allocation_lookup import order_numbers_for
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
from src.modules.fulfillment.application.use_cases.bought_item_demand.fulfill_from_stock import (
    FulfillDemandFromStock,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.get_allocations import (
    GetDemandSummary,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.get_allocations import (
    GetDemandSummaryBatch,
)
from src.modules.fulfillment.domain.entities.bought_item_allocation import (
    BoughtItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.bought_item_demand_item import BoughtItemDemandItem
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.errors import AllocationItemMismatchError
from src.modules.fulfillment.domain.errors import AllocationNotFoundError
from src.modules.fulfillment.domain.errors import AllocationOverflowError
from src.modules.fulfillment.domain.errors import DemandItemNotFoundError
from src.modules.fulfillment.domain.errors import OrderItemNotFoundError
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    DemandItemFilterDto,
)
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.lifecycle.fake_demand_reconciler import demand_reconciler
from tests.unit.production_lot.fakes import FakeProjectRepository
from tests.unit.production_lot.fakes import FakeSourceItemAllocationRepository

# ── Helpers ───────────────────────────────────────────────────────────


def make_demand(
    id: int = 1,
    quantity: float = 10.0,
    status: BoughtItemDemandStatus = BoughtItemDemandStatus.OPEN,
    item_id: int = 1,
) -> BoughtItemDemandItem:
    return BoughtItemDemandItem(
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
        item_id=item_id,
        project_id=1,
    )


def make_order_item(
    id: int = 1,
    order_id: int = 1,
    status: OrderItemStatus = OrderItemStatus.ORDERED,
    quantity: float = 10.0,
    quantity_delivered: float = 0.0,
    bought_item_id: int = 1,
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
        line_type=OrderLineType.BOUGHT,
        lot_position_id=None,
        source_item_id=None,
    )


def make_order(id: int = 1, order_number: str | None = None) -> Order:
    return Order(
        id=id,
        order_number=order_number or f"ORD-{id}",
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


def make_bought_item(
    id: int = 1, order_code_1: str = "SUB-1", article_name: str = "Sub"
) -> BoughtItem:
    return BoughtItem(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        archived=False,
        article_name=article_name,
        order_code_1=order_code_1,
        order_code_2=None,
        gtin=None,
        ean=None,
        tariff_number=None,
        status=BoughtItemCatalogueStatus.ACTIVE,
        data_source=DataSource.WEB,
        part_number=None,
        mass=None,
        note=None,
        weblink=None,
        files=[],
        creator_id=1,
        approver_id=None,
        manufacturer_id=1,
        article_group_ids=[],
        successor_item_id=None,
    )


class FakeDemandRepository:
    def __init__(self, demands: list[BoughtItemDemandItem] | None = None):
        self._demands: dict[int, BoughtItemDemandItem] = {d.id: d for d in (demands or [])}
        self.for_update_calls: list[int] = []
        # Counts get_by_id calls: GetDemandSummaryBatch must use get_by_ids
        # (below) for the whole batch instead of looping get_by_id per
        # demand, see the call-counting test.
        self.get_by_id_calls = 0

    async def get_by_id(self, id: int) -> BoughtItemDemandItem | None:
        self.get_by_id_calls += 1
        return self._demands.get(id)

    async def get_by_id_for_update(self, id: int) -> BoughtItemDemandItem | None:
        self.for_update_calls.append(id)
        return self._demands.get(id)

    async def get_by_ids(self, ids: list[int]) -> list[BoughtItemDemandItem]:
        return [self._demands[i] for i in ids if i in self._demands]

    async def get_by_project_id(self, project_id: int) -> list[BoughtItemDemandItem]:
        raise NotImplementedError

    async def get_pipeline(self, terminal_since: date) -> list[BoughtItemDemandItem]:
        raise NotImplementedError

    async def get_multi(self, filters: DemandItemFilterDto):
        raise NotImplementedError

    async def save(self, demand: BoughtItemDemandItem) -> BoughtItemDemandItem:
        self._demands[demand.id] = demand
        return demand

    async def delete(self, demand: BoughtItemDemandItem) -> None:
        raise NotImplementedError


class FakeOrderItemRepository:
    def __init__(self, items: list[OrderItem] | None = None):
        self._items: dict[int, OrderItem] = {i.id: i for i in (items or [])}
        # Counts get_by_id calls: the batched lookup path must use
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
        raise NotImplementedError

    async def next_position(self, order_id: int) -> int:
        return sum(1 for i in self._items.values() if i.order_id == order_id) + 1

    async def save(self, item: OrderItem) -> OrderItem:
        self._items[item.id] = item
        return item

    async def delete(self, item: OrderItem) -> None:
        self._items.pop(item.id, None)


class FakeAllocationRepository:
    def __init__(self, allocations: list[BoughtItemDemandAllocation] | None = None):
        self._allocations: list[BoughtItemDemandAllocation] = list(allocations or [])
        # Counts get_by_demand_item_id calls: the batched summary path
        # must use get_by_demand_item_ids (below) for the whole batch
        # instead of looping this per demand.
        self.get_by_demand_item_id_calls = 0

    @property
    def allocations(self) -> list[BoughtItemDemandAllocation]:
        """The stored allocations, for assertions."""
        return self._allocations

    async def get_by_demand_item_id(self, demand_item_id: int) -> list[BoughtItemDemandAllocation]:
        self.get_by_demand_item_id_calls += 1
        return [a for a in self._allocations if a.demand_item_id == demand_item_id]

    async def get_by_demand_item_ids(
        self, demand_item_ids: list[int]
    ) -> list[BoughtItemDemandAllocation]:
        return [a for a in self._allocations if a.demand_item_id in demand_item_ids]

    async def get_by_order_item_id(self, order_item_id: int) -> list[BoughtItemDemandAllocation]:
        return [a for a in self._allocations if a.order_item_id == order_item_id]

    async def get_by_order_item_ids(
        self, order_item_ids: list[int]
    ) -> list[BoughtItemDemandAllocation]:
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

    async def save(self, allocation: BoughtItemDemandAllocation) -> BoughtItemDemandAllocation:
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
        else:
            self._allocations.append(allocation)
        return allocation

    async def delete(self, allocation: BoughtItemDemandAllocation) -> None:
        self._allocations = [
            a
            for a in self._allocations
            if not (
                a.demand_item_id == allocation.demand_item_id
                and a.order_item_id == allocation.order_item_id
                and a.source == allocation.source
            )
        ]


class FakeOrderRepository:
    def __init__(self, orders: list[Order] | None = None):
        self._orders: dict[int, Order] = {o.id: o for o in (orders or [])}

    async def get_by_id(self, id: int) -> Order | None:
        return self._orders.get(id)

    async def get_by_ids(self, ids: list[int], *, refresh: bool = False) -> list[Order]:
        return [self._orders[i] for i in ids if i in self._orders]


class FakeCatalogueRepository:
    """Stands in for IBoughtItemRepository, GetDemandSummary(Batch)'s only
    use of it is the substitute-item lookup in _build_substitutions."""

    def __init__(self, items: list[BoughtItem] | None = None):
        self._items: dict[int, BoughtItem] = {i.id: i for i in (items or [])}
        # Counts get_by_id calls: proves the batch's catalogue_cache
        # fetches a given substitute item at most once per batch, even
        # when several demands substitute it.
        self.get_by_id_calls = 0

    async def get_by_id(self, id: int) -> BoughtItem | None:
        self.get_by_id_calls += 1
        return self._items.get(id)


class FakeUnitOfWork:
    def __init__(self):
        self.committed = False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        pass


# ── CreateAllocation / UpdateAllocation / DeleteAllocation ─────────────


class TestCreateAllocation:
    def setup_method(self):
        self.demand = make_demand(id=1, quantity=10.0, item_id=1)
        self.demand_repo = FakeDemandRepository([self.demand])
        self.order_item = make_order_item(id=1, quantity=10.0, bought_item_id=1)
        self.order_items = FakeOrderItemRepository([self.order_item])
        self.allocation_repo = FakeAllocationRepository()
        self.actor = make_user(permissions=[Permission.WRITE_ALLOCATIONS])
        self.use_case = CreateAllocation(
            self.allocation_repo,
            self.demand_repo,
            self.order_items,
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(
                bought_allocations=self.allocation_repo,
                bought_demands=self.demand_repo,
                order_items=self.order_items,
            ),
            fill_repos=LineFillRepos(
                bought=self.allocation_repo, source=FakeSourceItemAllocationRepository()
            ),
        )

    async def test_creates_allocation_and_updates_status(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=CreateAllocationCommand(demand_item_id=1, order_item_id=1, quantity=4.0),
        )
        assert result.quantity == 4.0
        assert result.order_item_id == 1
        assert (
            await self.demand_repo.get_by_id(1)
        ).status == BoughtItemDemandStatus.ALLOCATED.value

    async def test_the_allocation_names_its_creator_and_the_demand_logs_it(self):
        await self.use_case.execute(
            actor=self.actor,
            cmd=CreateAllocationCommand(demand_item_id=1, order_item_id=1, quantity=4.0),
        )

        [allocation] = await self.allocation_repo.get_by_demand_item_id(1)
        assert allocation.created_by_id == self.actor.id
        changes = (await self.demand_repo.get_by_id(1)).changes
        assert any(entry.endswith("Allocated 4.000 pcs on order item #1.") for entry in changes), (
            changes
        )

    async def test_demand_not_found_raises(self):
        with pytest.raises(DemandItemNotFoundError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=CreateAllocationCommand(demand_item_id=999, order_item_id=1, quantity=1.0),
            )

    async def test_order_item_not_found_raises(self):
        with pytest.raises(OrderItemNotFoundError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=CreateAllocationCommand(demand_item_id=1, order_item_id=999, quantity=1.0),
            )

    async def test_item_mismatch_raises(self):
        mismatched = make_order_item(id=2, bought_item_id=2)
        await self.order_items.save(mismatched)
        with pytest.raises(AllocationItemMismatchError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=CreateAllocationCommand(demand_item_id=1, order_item_id=2, quantity=1.0),
            )

    async def test_overallocation_beyond_demand_raises(self):
        with pytest.raises(AllocationOverflowError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=CreateAllocationCommand(demand_item_id=1, order_item_id=1, quantity=11.0),
            )

    async def test_overallocation_beyond_order_item_available_raises(self):
        small_order_item = make_order_item(id=3, quantity=2.0, bought_item_id=1)
        await self.order_items.save(small_order_item)
        with pytest.raises(AllocationOverflowError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=CreateAllocationCommand(demand_item_id=1, order_item_id=3, quantity=3.0),
            )

    async def test_reads_the_demand_with_a_row_lock(self):
        """Two concurrent allocations against the same demand must
        not both read the pre-insert already_allocated total, see
        IBoughtItemDemandItemRepository.get_by_id_for_update."""
        await self.use_case.execute(
            actor=self.actor,
            cmd=CreateAllocationCommand(demand_item_id=1, order_item_id=1, quantity=4.0),
        )
        assert self.demand_repo.for_update_calls == [1]

    async def test_substitute_equal_to_demands_own_item_stored_as_non_substitution(self):
        """order_item_id=1 already matches the demand's own item (1);
        declaring it as its own substitute is not a real substitution, so
        both fields are stored as None and the reason is dropped."""
        await self.use_case.execute(
            actor=self.actor,
            cmd=CreateAllocationCommand(
                demand_item_id=1,
                order_item_id=1,
                quantity=4.0,
                substitute_item_id=1,
                substitute_reason="not a real substitution",
            ),
        )

        [stored] = await self.allocation_repo.get_by_demand_item_id(1)
        assert stored.substitute_item_id is None
        assert stored.substitute_reason is None

    async def test_reason_without_substitution_is_dropped(self):
        """A reason sent without substitute_item_id (order item already
        matches the demand) is dropped, not stored."""
        await self.use_case.execute(
            actor=self.actor,
            cmd=CreateAllocationCommand(
                demand_item_id=1,
                order_item_id=1,
                quantity=4.0,
                substitute_reason="stray reason",
            ),
        )

        [stored] = await self.allocation_repo.get_by_demand_item_id(1)
        assert stored.substitute_item_id is None
        assert stored.substitute_reason is None

    async def test_declared_substitution_records_the_lines_item_and_reason(self):
        await self.order_items.save(make_order_item(id=2, bought_item_id=2))
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=CreateAllocationCommand(
                demand_item_id=1,
                order_item_id=2,
                quantity=4.0,
                substitute_item_id=2,
                substitute_reason="Successor part",
            ),
        )

        [stored] = await self.allocation_repo.get_by_demand_item_id(1)
        assert stored.substitute_item_id == 2
        assert stored.substitute_reason == "Successor part"
        assert (result.substitute_item_id, result.substitute_reason) == (2, "Successor part")


class TestUpdateAllocation:
    @pytest.fixture(autouse=True)
    async def _setup(self):
        self.demand = make_demand(id=1, quantity=10.0, item_id=1)
        self.demand_repo = FakeDemandRepository([self.demand])
        self.order_item = make_order_item(id=1, quantity=10.0, bought_item_id=1)
        self.order_items = FakeOrderItemRepository([self.order_item])
        self.allocation_repo = FakeAllocationRepository()
        self.actor = make_user(permissions=[Permission.WRITE_ALLOCATIONS])
        self.create_use_case = CreateAllocation(
            self.allocation_repo,
            self.demand_repo,
            self.order_items,
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(
                bought_allocations=self.allocation_repo,
                bought_demands=self.demand_repo,
                order_items=self.order_items,
            ),
            fill_repos=LineFillRepos(
                bought=self.allocation_repo, source=FakeSourceItemAllocationRepository()
            ),
        )
        self.update_use_case = UpdateAllocation(
            self.allocation_repo,
            self.demand_repo,
            self.order_items,
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(
                bought_allocations=self.allocation_repo,
                bought_demands=self.demand_repo,
                order_items=self.order_items,
            ),
            fill_repos=LineFillRepos(
                bought=self.allocation_repo, source=FakeSourceItemAllocationRepository()
            ),
        )
        await self.create_use_case.execute(
            actor=self.actor,
            cmd=CreateAllocationCommand(demand_item_id=1, order_item_id=1, quantity=4.0),
        )

    async def test_updates_quantity(self):
        result = await self.update_use_case.execute(
            actor=self.actor,
            demand_item_id=1,
            order_item_id=1,
            cmd=UpdateAllocationCommand(quantity=6.0),
        )
        assert result.quantity == 6.0

    async def test_not_found_raises(self):
        other_order_item = make_order_item(id=2, quantity=10.0, bought_item_id=1)
        await self.order_items.save(other_order_item)
        with pytest.raises(AllocationNotFoundError):
            await self.update_use_case.execute(
                actor=self.actor,
                demand_item_id=1,
                order_item_id=2,
                cmd=UpdateAllocationCommand(quantity=1.0),
            )

    async def test_overallocation_raises(self):
        with pytest.raises(AllocationOverflowError):
            await self.update_use_case.execute(
                actor=self.actor,
                demand_item_id=1,
                order_item_id=1,
                cmd=UpdateAllocationCommand(quantity=11.0),
            )

    async def test_reads_the_demand_with_a_row_lock(self):
        """See TestCreateAllocation's identical test."""
        self.demand_repo.for_update_calls.clear()  # setup_method's own create already locked once
        await self.update_use_case.execute(
            actor=self.actor,
            demand_item_id=1,
            order_item_id=1,
            cmd=UpdateAllocationCommand(quantity=6.0),
        )
        assert self.demand_repo.for_update_calls == [1]


class TestDeleteAllocation:
    @pytest.fixture(autouse=True)
    async def _setup(self):
        self.demand = make_demand(id=1, quantity=10.0, item_id=1)
        self.demand_repo = FakeDemandRepository([self.demand])
        self.order_item = make_order_item(id=1, quantity=10.0, bought_item_id=1)
        self.order_items = FakeOrderItemRepository([self.order_item])
        self.allocation_repo = FakeAllocationRepository()
        self.actor = make_user(permissions=[Permission.WRITE_ALLOCATIONS])
        self.create_use_case = CreateAllocation(
            self.allocation_repo,
            self.demand_repo,
            self.order_items,
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(
                bought_allocations=self.allocation_repo,
                bought_demands=self.demand_repo,
                order_items=self.order_items,
            ),
            fill_repos=LineFillRepos(
                bought=self.allocation_repo, source=FakeSourceItemAllocationRepository()
            ),
        )
        self.delete_use_case = DeleteAllocation(
            self.allocation_repo,
            self.demand_repo,
            self.order_items,
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(
                bought_allocations=self.allocation_repo,
                bought_demands=self.demand_repo,
                order_items=self.order_items,
            ),
            fill_repos=LineFillRepos(
                bought=self.allocation_repo, source=FakeSourceItemAllocationRepository()
            ),
        )
        await self.create_use_case.execute(
            actor=self.actor,
            cmd=CreateAllocationCommand(demand_item_id=1, order_item_id=1, quantity=4.0),
        )

    async def test_deletes_and_reverts_status(self):
        await self.delete_use_case.execute(actor=self.actor, demand_item_id=1, order_item_id=1)
        assert await self.allocation_repo.get_by_demand_item_id(1) == []
        assert (await self.demand_repo.get_by_id(1)).status == BoughtItemDemandStatus.OPEN.value

    async def test_not_found_raises(self):
        with pytest.raises(AllocationNotFoundError):
            await self.delete_use_case.execute(
                actor=self.actor, demand_item_id=1, order_item_id=999
            )


# ── Stock allocation ────────────────────────────────────────────────────


class TestStockAllocation:
    def setup_method(self):
        self.demand = make_demand(id=1, quantity=10.0)
        self.demand_repo = FakeDemandRepository([self.demand])
        self.order_items = FakeOrderItemRepository()
        self.allocation_repo = FakeAllocationRepository()
        self.actor = make_user(permissions=[Permission.WRITE_ALLOCATIONS])
        self.update_use_case = UpdateStockAllocation(
            self.allocation_repo,
            self.demand_repo,
            self.order_items,
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(
                bought_allocations=self.allocation_repo,
                bought_demands=self.demand_repo,
                order_items=self.order_items,
            ),
        )
        self.delete_use_case = DeleteStockAllocation(
            self.allocation_repo,
            self.demand_repo,
            self.order_items,
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(
                bought_allocations=self.allocation_repo,
                bought_demands=self.demand_repo,
                order_items=self.order_items,
            ),
        )

    async def test_sets_stock_allocation_and_updates_status(self):
        result = await self.update_use_case.execute(
            actor=self.actor,
            demand_item_id=1,
            cmd=UpdateStockAllocationCommand(quantity=4.0),
        )
        assert result.quantity == 4.0
        assert result.source == "stock"
        assert (
            await self.demand_repo.get_by_id(1)
        ).status == BoughtItemDemandStatus.ALLOCATED.value

    async def test_reads_the_demand_with_a_row_lock(self):
        """See TestCreateAllocation's identical test."""
        await self.update_use_case.execute(
            actor=self.actor,
            demand_item_id=1,
            cmd=UpdateStockAllocationCommand(quantity=4.0),
        )
        assert self.demand_repo.for_update_calls == [1]

    async def test_full_stock_allocation_fulfills_demand(self):
        await self.update_use_case.execute(
            actor=self.actor,
            demand_item_id=1,
            cmd=UpdateStockAllocationCommand(quantity=10.0),
        )
        assert (
            await self.demand_repo.get_by_id(1)
        ).status == BoughtItemDemandStatus.FULFILLED.value

    async def test_overallocation_raises(self):
        with pytest.raises(AllocationOverflowError):
            await self.update_use_case.execute(
                actor=self.actor,
                demand_item_id=1,
                cmd=UpdateStockAllocationCommand(quantity=11.0),
            )

    async def test_demand_not_found_raises(self):
        with pytest.raises(DemandItemNotFoundError):
            await self.update_use_case.execute(
                actor=self.actor,
                demand_item_id=999,
                cmd=UpdateStockAllocationCommand(quantity=1.0),
            )

    async def test_delete_removes_stock_allocation(self):
        await self.update_use_case.execute(
            actor=self.actor,
            demand_item_id=1,
            cmd=UpdateStockAllocationCommand(quantity=4.0),
        )
        await self.delete_use_case.execute(actor=self.actor, demand_item_id=1)
        assert await self.allocation_repo.get_by_demand_item_id(1) == []
        assert (await self.demand_repo.get_by_id(1)).status == BoughtItemDemandStatus.OPEN.value

    async def test_delete_without_existing_raises(self):
        with pytest.raises(AllocationNotFoundError):
            await self.delete_use_case.execute(actor=self.actor, demand_item_id=1)


# ── AutoAllocate ─────────────────────────────────────────────────────


class TestAutoAllocate:
    def setup_method(self):
        self.allocation_repo = FakeAllocationRepository()
        self.uow = FakeUnitOfWork()
        self.actor = make_user(permissions=[Permission.WRITE_ALLOCATIONS])

    async def test_allocates_against_matching_order_item(self):
        demand = make_demand(id=1, quantity=10.0, item_id=1)
        demand_repo = FakeDemandRepository([demand])
        order_item = make_order_item(id=1, quantity=6.0, bought_item_id=1)
        order_items = FakeOrderItemRepository([order_item])
        use_case = AutoAllocate(
            demand_repo,
            order_items,
            self.allocation_repo,
            uow=self.uow,
            reconciler=demand_reconciler(
                bought_demands=demand_repo,
                order_items=order_items,
                bought_allocations=self.allocation_repo,
            ),
            project_repo=FakeProjectRepository(),
            fill_repos=LineFillRepos(
                bought=self.allocation_repo, source=FakeSourceItemAllocationRepository()
            ),
        )

        result = await use_case.execute(actor=self.actor, cmd=AutoAllocateCommand(demand_item_id=1))
        assert result.allocations_created == 1
        assert result.total_newly_allocated == 6.0
        assert result.remaining_unallocated == 4.0
        assert (await demand_repo.get_by_id(1)).status == BoughtItemDemandStatus.ALLOCATED.value
        assert demand_repo.for_update_calls == [1]  # row lock, see the class docstring

    async def test_prefers_ordered_over_partially_delivered_and_earlier_delivery(self):
        demand = make_demand(id=3, quantity=5.0, item_id=1)
        demand_repo = FakeDemandRepository([demand])
        far = make_order_item(
            id=10,
            quantity=5.0,
            bought_item_id=1,
            status=OrderItemStatus.ORDERED,
            expected_delivery_date=date(2026, 12, 1),
        )
        near = make_order_item(
            id=11,
            quantity=5.0,
            bought_item_id=1,
            status=OrderItemStatus.ORDERED,
            expected_delivery_date=date(2026, 2, 1),
        )
        order_items = FakeOrderItemRepository([far, near])
        use_case = AutoAllocate(
            demand_repo,
            order_items,
            self.allocation_repo,
            uow=self.uow,
            reconciler=demand_reconciler(
                bought_demands=demand_repo,
                order_items=order_items,
                bought_allocations=self.allocation_repo,
            ),
            project_repo=FakeProjectRepository(),
            fill_repos=LineFillRepos(
                bought=self.allocation_repo, source=FakeSourceItemAllocationRepository()
            ),
        )

        await use_case.execute(actor=self.actor, cmd=AutoAllocateCommand(demand_item_id=3))

        allocations = await self.allocation_repo.get_by_demand_item_id(3)
        assert len(allocations) == 1
        assert allocations[0].order_item_id == 11

    async def test_ineligible_status_skipped(self):
        demand = make_demand(id=4, quantity=5.0, item_id=1)
        demand_repo = FakeDemandRepository([demand])
        pending = make_order_item(
            id=12, quantity=5.0, bought_item_id=1, status=OrderItemStatus.PENDING
        )
        order_items = FakeOrderItemRepository([pending])
        use_case = AutoAllocate(
            demand_repo,
            order_items,
            self.allocation_repo,
            uow=self.uow,
            reconciler=demand_reconciler(
                bought_demands=demand_repo,
                order_items=order_items,
                bought_allocations=self.allocation_repo,
            ),
            project_repo=FakeProjectRepository(),
            fill_repos=LineFillRepos(
                bought=self.allocation_repo, source=FakeSourceItemAllocationRepository()
            ),
        )

        result = await use_case.execute(actor=self.actor, cmd=AutoAllocateCommand(demand_item_id=4))
        assert result.allocations_created == 0
        assert result.total_newly_allocated == 0.0

    async def test_terminal_demand_is_a_no_op(self):
        demand = make_demand(id=5, quantity=5.0, item_id=1, status=BoughtItemDemandStatus.FULFILLED)
        demand_repo = FakeDemandRepository([demand])
        order_item = make_order_item(id=13, quantity=5.0, bought_item_id=1)
        order_items = FakeOrderItemRepository([order_item])
        use_case = AutoAllocate(
            demand_repo,
            order_items,
            self.allocation_repo,
            uow=self.uow,
            reconciler=demand_reconciler(
                bought_demands=demand_repo,
                order_items=order_items,
                bought_allocations=self.allocation_repo,
            ),
            project_repo=FakeProjectRepository(),
            fill_repos=LineFillRepos(
                bought=self.allocation_repo, source=FakeSourceItemAllocationRepository()
            ),
        )

        result = await use_case.execute(actor=self.actor, cmd=AutoAllocateCommand(demand_item_id=5))
        assert result.allocations_created == 0
        assert result.demand_status_changed_to is None

    async def test_demand_not_found_raises(self):
        demand_repo = FakeDemandRepository()
        order_items = FakeOrderItemRepository()
        use_case = AutoAllocate(
            demand_repo,
            order_items,
            self.allocation_repo,
            uow=self.uow,
            reconciler=demand_reconciler(
                bought_demands=demand_repo,
                order_items=order_items,
                bought_allocations=self.allocation_repo,
            ),
            project_repo=FakeProjectRepository(),
            fill_repos=LineFillRepos(
                bought=self.allocation_repo, source=FakeSourceItemAllocationRepository()
            ),
        )
        with pytest.raises(DemandItemNotFoundError):
            await use_case.execute(actor=self.actor, cmd=AutoAllocateCommand(demand_item_id=999))


# ── FulfillFromStock ─────────────────────────────────────────────────


class TestFulfillFromStock:
    def setup_method(self):
        self.demand = make_demand(id=1, quantity=10.0)
        self.demand_repo = FakeDemandRepository([self.demand])
        self.allocation_repo = FakeAllocationRepository()
        self.order_items = FakeOrderItemRepository()
        self.actor = make_user(permissions=[Permission.WRITE_ALLOCATIONS])
        self.uow = FakeUnitOfWork()
        self.use_case = FulfillDemandFromStock(
            self.demand_repo,
            self.allocation_repo,
            self.order_items,
            uow=self.uow,
            reconciler=demand_reconciler(
                bought_demands=self.demand_repo,
                bought_allocations=self.allocation_repo,
                order_items=self.order_items,
            ),
        )

    async def test_tops_up_stock_allocation(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=FulfillFromStockCommand(demand_item_id=1, quantity=3.0),
        )
        assert result.total_fulfilled_from_stock == 3.0
        assert result.demand_status_changed_to == BoughtItemDemandStatus.ALLOCATED.value
        assert self.uow.committed is True

        result2 = await self.use_case.execute(
            actor=self.actor,
            cmd=FulfillFromStockCommand(demand_item_id=1, quantity=2.0),
        )
        assert result2.total_fulfilled_from_stock == 5.0

    async def test_reads_the_demand_with_a_row_lock(self):
        """See TestCreateAllocation's identical test."""
        await self.use_case.execute(
            actor=self.actor,
            cmd=FulfillFromStockCommand(demand_item_id=1, quantity=3.0),
        )
        assert self.demand_repo.for_update_calls == [1]

    async def test_fulfilling_full_quantity_marks_fulfilled(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=FulfillFromStockCommand(demand_item_id=1, quantity=10.0),
        )
        assert result.demand_status_changed_to == BoughtItemDemandStatus.FULFILLED.value

    async def test_overallocation_raises(self):
        with pytest.raises(AllocationOverflowError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=FulfillFromStockCommand(demand_item_id=1, quantity=11.0),
            )

    async def test_demand_not_found_raises(self):
        with pytest.raises(DemandItemNotFoundError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=FulfillFromStockCommand(demand_item_id=999, quantity=1.0),
            )


# ── GetDemandSummaryBatch ───────────────────────────────────────────────
#
# Characterization tests pinning GetDemandSummaryBatch's behaviour, which
# matches a per-demand loop of single summaries. The call-counting tests at
# the bottom of this class pin the batched query shape: a constant number
# of repository calls, never one per demand.


class TestGetDemandSummaryBatch:
    def setup_method(self):
        # demand 1: single ORDER allocation, fully covers it.
        self.demand1 = make_demand(id=1, quantity=10.0)
        # demand 2: mixed stock (4) + order (6).
        self.demand2 = make_demand(id=2, quantity=10.0)
        # demand 3: zero allocations.
        self.demand3 = make_demand(id=3, quantity=5.0)
        # demand 4: ORDER allocation referencing an order item that no
        # longer exists (orphaned reference).
        self.demand4 = make_demand(id=4, quantity=8.0)
        # demand 5 & 6: both substitute the SAME catalogue item (50),
        # with different quantities, proving per-demand scoping survives
        # a shared batch-wide order-item/catalogue lookup.
        self.demand5 = make_demand(id=5, quantity=10.0)
        self.demand6 = make_demand(id=6, quantity=10.0)

        self.demand_repo = FakeDemandRepository(
            [self.demand1, self.demand2, self.demand3, self.demand4, self.demand5, self.demand6]
        )

        order_item_101 = make_order_item(id=101, order_id=201, quantity=10.0)
        order_item_102 = make_order_item(id=102, order_id=202, quantity=10.0)
        order_item_105 = make_order_item(id=105, order_id=205, quantity=10.0)
        order_item_106 = make_order_item(id=106, order_id=205, quantity=10.0)
        self.order_items = FakeOrderItemRepository(
            [order_item_101, order_item_102, order_item_105, order_item_106]
        )

        self.orders = FakeOrderRepository(
            [make_order(id=201), make_order(id=202), make_order(id=205)]
        )
        self.catalogue = FakeCatalogueRepository([make_bought_item(id=50)])

        self.allocations = [
            BoughtItemDemandAllocation(demand_item_id=1, order_item_id=101, quantity=10.0),
            BoughtItemDemandAllocation(
                demand_item_id=2,
                order_item_id=None,
                quantity=4.0,
                source=AllocationSource.STOCK,
            ),
            BoughtItemDemandAllocation(demand_item_id=2, order_item_id=102, quantity=6.0),
            # demand 3: none.
            BoughtItemDemandAllocation(demand_item_id=4, order_item_id=999, quantity=5.0),
            BoughtItemDemandAllocation(
                demand_item_id=5,
                order_item_id=105,
                quantity=6.0,
                substitute_item_id=50,
                substitute_reason="Sub A",
            ),
            BoughtItemDemandAllocation(
                demand_item_id=6,
                order_item_id=106,
                quantity=4.0,
                substitute_item_id=50,
                substitute_reason="Sub B",
            ),
        ]
        self.allocation_repo = FakeAllocationRepository(self.allocations)

        self.batch_use_case = GetDemandSummaryBatch(
            self.demand_repo, self.allocation_repo, self.order_items, self.orders, self.catalogue
        )

    async def _singular(self, demand_item_id: int) -> DemandSummaryResult:
        return await GetDemandSummary(
            self.demand_repo, self.allocation_repo, self.order_items, self.orders, self.catalogue
        ).execute(demand_item_id)

    async def test_batch_matches_singular_result_for_each_demand(self):
        ids = [1, 2, 3, 4, 5, 6]
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

    async def test_substitutions_aggregate_across_demands(self):
        result = await self.batch_use_case.execute([5, 6])

        demand5_subs = result[5].substitutions
        demand6_subs = result[6].substitutions
        assert len(demand5_subs) == 1
        assert demand5_subs[0].substitute_item_id == 50
        assert demand5_subs[0].quantity == 6.0
        assert len(demand6_subs) == 1
        assert demand6_subs[0].substitute_item_id == 50
        assert demand6_subs[0].quantity == 4.0

    # ── Call-counting ───────────────────────────────────────────────────

    async def test_batch_issues_a_constant_number_of_repository_calls(self):
        await self.batch_use_case.execute([1, 2, 3, 4, 5, 6])

        assert self.demand_repo.get_by_id_calls == 0
        assert self.allocation_repo.get_by_demand_item_id_calls == 0
        assert self.order_items.get_by_id_calls == 0

    async def test_catalogue_lookup_is_cached_across_the_batch(self):
        await self.batch_use_case.execute([5, 6])

        assert self.catalogue.get_by_id_calls == 1


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
        second_repo_calls = len(self.order_repo.get_by_ids_calls)

        await order_numbers_for([1], self.order_repo)

        assert len(self.order_repo.get_by_ids_calls) == second_repo_calls + 1
