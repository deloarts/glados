"""
Quantity edits of an order item through UpdateOrderItem: accepted only while
the line is pending, requested or ordered, a line that received pieces being
closed short instead (tests/unit/order/test_order_line_settlement.py), and
refused below what demands of both allocation families have allocated to the
line; after an accepted edit the lifecycle reconciler derives the line's and
the order's status, and the demands allocated to the line are recomputed. No
database, no HTTP, in-memory fakes only.
"""

from datetime import UTC
from datetime import date
from datetime import datetime

import pytest

from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.fulfillment.application.dto.order_dto import UpdateOrderItemCommand
from src.modules.fulfillment.application.use_cases.order.update_order_item import UpdateOrderItem
from src.modules.fulfillment.domain.entities.bought_item_allocation import (
    BoughtItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.bought_item_demand_item import BoughtItemDemandItem
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.source_item_allocation import (
    SourceItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.source_item_demand_item import SourceItemDemandItem
from src.modules.fulfillment.domain.errors import AllocationOverflowError
from src.modules.fulfillment.domain.errors import OrderItemQuantityNotEditableError
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.lifecycle.fake_reconciler import give_order_facts
from tests.unit.lifecycle.fake_reconciler import give_order_item_facts
from tests.unit.lifecycle.fake_reconciler import order_reconciler
from tests.unit.production_lot.fakes import FakeProjectRepository

# ── Builders ──────────────────────────────────────────────────────────


def make_order(status: OrderStatus = OrderStatus.PARTIALLY_DELIVERED) -> Order:
    return give_order_facts(
        Order(
            id=1,
            order_number="ORD-2026-0001",
            created=datetime(2026, 1, 1, tzinfo=UTC),
            changed=None,
            changes=[],
            status=status,
            note=None,
            ordered_date=datetime(2026, 1, 2, tzinfo=UTC),
            expected_delivery_date=None,
            delivery_date=None,
            storage_place=None,
            creator_id=1,
            supplier_id=1,
        )
    )


def make_line(
    *,
    id: int = 1,
    quantity: float = 10.0,
    delivered: float = 0.0,
    lost: float = 0.0,
    status: OrderItemStatus = OrderItemStatus.ORDERED,
) -> OrderItem:
    return give_order_item_facts(
        OrderItem(
            id=id,
            created=datetime(2026, 1, 1, tzinfo=UTC),
            changed=None,
            changes=[],
            status=status,
            quantity=quantity,
            quantity_delivered=delivered,
            unit="pcs",
            items_per_unit=1.0,
            price=None,
            note=None,
            ordered_date=None,
            expected_delivery_date=None,
            delivery_date=None,
            storage_place=None,
            expected_pickup_date=None,
            ready_for_pickup_date=None,
            position=id,
            creator_id=1,
            orderer_id=None,
            receiver_id=None,
            bought_item_id=1,
            order_id=1,
            supplier_id=1,
            project_id=1,
            line_type=OrderLineType.BOUGHT,
            lot_position_id=None,
            source_item_id=None,
            quantity_rejected=lost,
            quantity_rejected_lost=lost,
        )
    )


def make_bought_demand(
    id: int, quantity: float, status: BoughtItemDemandStatus = BoughtItemDemandStatus.ORDERED
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
        item_id=1,
        project_id=1,
    )


def make_source_demand(
    id: int, quantity: float, status: SourceItemDemandStatus = SourceItemDemandStatus.ORDERED
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
        bought_item_id=1,
        source_item_id=None,
        lot_id=1,
        project_id=1,
    )


# ── Fakes ─────────────────────────────────────────────────────────────


class FakeOrderRepository:
    def __init__(self, order: Order) -> None:
        self._orders = {order.id: order}
        self.saved: list[int] = []

    async def get_by_id(self, id: int) -> Order | None:
        return self._orders.get(id)

    async def save(self, order: Order) -> Order:
        self._orders[order.id] = order
        self.saved.append(order.id)
        return order


class FakeOrderItemRepository:
    def __init__(self, items: list[OrderItem]) -> None:
        self._items = {i.id: i for i in items}
        self.locked: list[int] = []

    async def get_by_id(self, id: int) -> OrderItem | None:
        return self._items.get(id)

    async def get_by_id_for_update(self, id: int) -> OrderItem | None:
        self.locked.append(id)
        return self._items.get(id)

    async def get_by_order_id(self, order_id: int) -> list[OrderItem]:
        return [i for i in self._items.values() if i.order_id == order_id]

    async def save(self, item: OrderItem) -> OrderItem:
        self._items[item.id] = item
        return item


class FakeAllocationRepository:
    """Serves both allocation families: only the order item and demand
    lookups are needed, and both entities share those fields."""

    def __init__(
        self, allocations: list[BoughtItemDemandAllocation] | list[SourceItemDemandAllocation]
    ) -> None:
        self._allocations = list(allocations)

    async def get_by_order_item_id(self, order_item_id: int) -> list:
        return [a for a in self._allocations if a.order_item_id == order_item_id]

    async def get_by_demand_item_id(self, demand_item_id: int) -> list:
        return [a for a in self._allocations if a.demand_item_id == demand_item_id]

    async def save(self, allocation):
        return allocation


class FakeDemandRepository:
    """Serves both demand families by id."""

    def __init__(self, demands: list) -> None:
        self._demands = {d.id: d for d in demands}

    async def get_by_id(self, id: int):
        return self._demands.get(id)

    async def save(self, demand):
        self._demands[demand.id] = demand
        return demand


class FakeCatalogueRepository:
    async def get_by_id(self, id: int) -> None:
        return None


# ── Tests ─────────────────────────────────────────────────────────────


class TestOrderItemQuantityEdit:
    def setup_method(self) -> None:
        self.actor = make_user(permissions=[Permission.WRITE_ORDERS, Permission.MANAGE_ORDERS])
        self.uow = FakeUnitOfWork()

    def _use_case(
        self,
        order: Order,
        lines: list[OrderItem],
        bought_allocations: list[BoughtItemDemandAllocation] | None = None,
        bought_demands: list[BoughtItemDemandItem] | None = None,
        source_allocations: list[SourceItemDemandAllocation] | None = None,
        source_demands: list[SourceItemDemandItem] | None = None,
    ) -> UpdateOrderItem:
        self.orders = FakeOrderRepository(order)
        self.lines = FakeOrderItemRepository(lines)
        self.bought_demands = FakeDemandRepository(bought_demands or [])
        self.source_demands = FakeDemandRepository(source_demands or [])
        return UpdateOrderItem(
            order_item_repo=self.lines,
            order_repo=self.orders,
            catalogue_repo=FakeCatalogueRepository(),
            allocation_repo=FakeAllocationRepository(bought_allocations or []),
            demand_repo=self.bought_demands,
            uow=self.uow,
            source_allocation_repo=FakeAllocationRepository(source_allocations or []),
            reconciler=order_reconciler(self.orders, self.lines),
            project_repo=FakeProjectRepository(),
        )

    async def _edit(self, use_case: UpdateOrderItem, quantity: float, note: str | None = None):
        return await use_case.execute(
            actor=self.actor,
            order_id=1,
            order_item_id=1,
            cmd=UpdateOrderItemCommand(quantity=quantity, unit="pcs", note=note),
        )

    async def test_a_partially_delivered_line_takes_no_quantity_change(self):
        # 10 ordered, 6 delivered, then set to 4; closing it short is the
        # way to settle it.
        line = make_line(quantity=10.0, delivered=6.0, status=OrderItemStatus.PARTIALLY_DELIVERED)
        use_case = self._use_case(make_order(), [line])

        with pytest.raises(OrderItemQuantityNotEditableError, match="close it short instead"):
            await self._edit(use_case, 4.0)

        assert line.quantity == 10.0
        assert line.status == "partially_delivered"
        assert not self.uow.committed

    async def test_lost_pieces_alone_fix_the_quantity_too(self):
        line = make_line(quantity=10.0, lost=2.0, status=OrderItemStatus.PARTIALLY_DELIVERED)
        use_case = self._use_case(make_order(), [line])

        with pytest.raises(OrderItemQuantityNotEditableError):
            await self._edit(use_case, 5.0)

        assert line.quantity == 10.0

    async def test_cutting_a_line_below_the_allocations_of_both_families_is_refused(self):
        # A bought line can also serve a source demand, so both tables count.
        line = make_line(quantity=10.0)
        use_case = self._use_case(
            make_order(status=OrderStatus.ORDERED),
            [line],
            bought_allocations=[
                BoughtItemDemandAllocation(demand_item_id=1, order_item_id=1, quantity=5.0)
            ],
            source_allocations=[
                SourceItemDemandAllocation(demand_item_id=2, order_item_id=1, quantity=3.0)
            ],
        )

        with pytest.raises(AllocationOverflowError, match=r"8\.000 pcs allocated"):
            await self._edit(use_case, 7.0)

        assert line.quantity == 10.0
        assert not self.uow.committed

    async def test_cutting_an_undelivered_line_to_its_allocations_keeps_its_status(self):
        line = make_line(quantity=10.0)
        use_case = self._use_case(
            make_order(status=OrderStatus.ORDERED),
            [line],
            bought_allocations=[
                BoughtItemDemandAllocation(demand_item_id=1, order_item_id=1, quantity=5.0)
            ],
            bought_demands=[make_bought_demand(1, quantity=5.0)],
            source_allocations=[
                SourceItemDemandAllocation(demand_item_id=2, order_item_id=1, quantity=3.0)
            ],
            source_demands=[make_source_demand(2, quantity=3.0)],
        )

        result = await self._edit(use_case, 8.0)

        assert result.quantity == 8.0
        assert result.status == "ordered"
        assert self.orders.saved == []
        assert self.uow.committed

    async def test_a_delivered_line_keeps_its_quantity(self):
        line = make_line(quantity=6.0, delivered=6.0, status=OrderItemStatus.DELIVERED)
        order = make_order(status=OrderStatus.DELIVERED)
        use_case = self._use_case(order, [line])

        with pytest.raises(OrderItemQuantityNotEditableError):
            await self._edit(use_case, 10.0)

        assert (line.quantity, line.status) == (6.0, "delivered")
        assert order.status == "delivered"
        assert not self.uow.committed

    async def test_a_note_edit_on_a_line_already_below_its_deliveries_is_accepted(self):
        line = make_line(quantity=4.0, delivered=6.0, status=OrderItemStatus.DELIVERED)
        use_case = self._use_case(make_order(status=OrderStatus.DELIVERED), [line])

        result = await self._edit(use_case, 4.0, note="Supplier sent two extra.")

        assert result.note == "Supplier sent two extra."
        assert result.quantity == 4.0
        assert result.status == "delivered"
        assert self.uow.committed

    async def test_each_changed_field_gets_an_entry_with_its_old_and_new_value(self):
        line = make_line(quantity=10.0)
        use_case = self._use_case(make_order(status=OrderStatus.ORDERED), [line])

        await self._edit(use_case, 8.0, note="Split delivery")

        entries = [c for c in line.changes if getattr(c, "field", None)]
        assert [(c.field, c.old, c.new) for c in entries] == [
            ("quantity", "10", "8"),
            ("note", "empty", "Split delivery"),
        ]

    async def test_the_line_is_read_with_the_lock(self):
        use_case = self._use_case(make_order(status=OrderStatus.ORDERED), [make_line()])

        await self._edit(use_case, 12.0)

        assert self.lines.locked == [1]
