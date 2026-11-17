"""
Moving a line, removing a line and force-completing a lot each leave the
parent order with the status the lifecycle reconciler derives from its
lines. In all three a canceled order keeps its status, and canceled lines do
not count: an order whose remaining lines are all canceled is canceled, and
one delivered line next to canceled ones makes the order delivered. Fakes
and builders come from the production lot test package.
"""

from datetime import date

from src.modules.fulfillment.application.dto.production_lot_dto import CompleteLotCommand
from src.modules.fulfillment.application.use_cases.order.delete_order_item import RemoveOrderItem
from src.modules.fulfillment.application.use_cases.order.move_order_item import MoveOrderItem
from src.modules.fulfillment.application.use_cases.production_lot.lot_lifecycle import CompleteLot
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.lifecycle.fake_reconciler import give_order_facts
from tests.unit.lifecycle.fake_reconciler import give_order_item_facts
from tests.unit.lifecycle.fake_reconciler import order_reconciler
from tests.unit.production_lot._helpers import make_order
from tests.unit.production_lot._helpers import make_order_item
from tests.unit.production_lot._helpers import make_production_order
from tests.unit.production_lot.fakes import FakeBoughtItemAllocationRepository
from tests.unit.production_lot.fakes import FakeEventBus
from tests.unit.production_lot.fakes import FakeMadeItemAllocationRepository
from tests.unit.production_lot.fakes import FakeMadeItemDemandRepository
from tests.unit.production_lot.fakes import FakeOrderItemRepository
from tests.unit.production_lot.fakes import FakeOrderRepository
from tests.unit.production_lot.fakes import FakeProductionLotRepository
from tests.unit.production_lot.fakes import FakeProductionOrderRepository
from tests.unit.production_lot.fakes import FakeSourceItemAllocationRepository
from tests.unit.production_lot.fakes import FakeSourceItemDemandRepository
from tests.unit.production_lot.fakes import FakeUnitOfWork
from tests.unit.production_order.fakes import lifecycle_collaborators

MANAGER = [Permission.WRITE_ORDERS, Permission.MANAGE_ORDERS]


def order_in(id: int, status: OrderStatus) -> Order:
    order = make_order(id=id)
    order.status = status
    return give_order_facts(order)


def bought_line(
    id: int, order_id: int, status: OrderItemStatus, quantity_delivered: float = 0.0
) -> OrderItem:
    line = make_order_item(id=id, order_id=order_id, line_type=OrderLineType.BOUGHT)
    line.bought_item_id = 1
    line.quantity = 4.0
    line.quantity_delivered = quantity_delivered
    line.status = status
    return give_order_item_facts(line)


class TestMoveRollup:
    async def test_moving_a_line_out_of_a_canceled_order_keeps_it_canceled(self) -> None:
        source = order_in(1, OrderStatus.CANCELED)
        target = order_in(2, OrderStatus.ORDERED)
        # A canceled line stays on its order, so an ordered one moves.
        moved = bought_line(1, 1, OrderItemStatus.ORDERED)
        kept = bought_line(2, 1, OrderItemStatus.PARTIALLY_DELIVERED, quantity_delivered=1.0)
        target_line = bought_line(3, 2, OrderItemStatus.ORDERED)
        orders = FakeOrderRepository([source, target])
        lines = FakeOrderItemRepository([moved, kept, target_line])
        use_case = MoveOrderItem(
            order_repo=orders,
            order_item_repo=lines,
            uow=FakeUnitOfWork(),
            reconciler=order_reconciler(orders, lines),
        )

        await use_case.execute(
            actor=make_user(permissions=MANAGER),
            source_order_id=1,
            order_item_id=1,
            target_order_id=2,
        )

        assert source.status == OrderStatus.CANCELED.value
        assert target.status == OrderStatus.ORDERED.value


class TestRemoveRollup:
    def _use_case(self, orders: FakeOrderRepository, lines: list[OrderItem]) -> RemoveOrderItem:
        order_items = FakeOrderItemRepository(lines)
        return RemoveOrderItem(
            order_repo=orders,
            order_item_repo=order_items,
            allocation_repo=FakeBoughtItemAllocationRepository(),
            uow=FakeUnitOfWork(),
            reconciler=order_reconciler(orders, order_items),
        )

    async def test_removing_a_line_of_a_canceled_order_keeps_it_canceled(self) -> None:
        order = order_in(1, OrderStatus.CANCELED)
        # Only a pending or requested line is removed.
        removed = bought_line(1, 1, OrderItemStatus.PENDING)
        kept = bought_line(2, 1, OrderItemStatus.PARTIALLY_DELIVERED, quantity_delivered=1.0)
        use_case = self._use_case(FakeOrderRepository([order]), [removed, kept])

        await use_case.execute(actor=make_user(permissions=MANAGER), order_id=1, order_item_id=1)

        assert order.status == OrderStatus.CANCELED.value

    async def test_removing_the_last_live_line_leaves_an_order_of_canceled_lines_canceled(
        self,
    ) -> None:
        order = order_in(1, OrderStatus.ORDERED)
        # Only a pending or requested line is removed.
        removed = bought_line(1, 1, OrderItemStatus.PENDING)
        kept = bought_line(2, 1, OrderItemStatus.CANCELED)
        use_case = self._use_case(FakeOrderRepository([order]), [removed, kept])

        await use_case.execute(actor=make_user(permissions=MANAGER), order_id=1, order_item_id=1)

        assert order.status == OrderStatus.CANCELED.value


class TestForceCompleteRollup:
    async def _complete_lot_with_made_line(
        self,
        order: Order,
        made_line_status: OrderItemStatus,
        other_lines: list[OrderItem],
        *,
        delivered: float = 0.0,
        made_in_house: float = 0.0,
    ) -> OrderItem:
        """Force-completes a lot whose single position is supplied by a MADE
        line of `order`, next to `other_lines` of the same order. The line
        has `delivered` pieces in, and a canceled production order of the
        position made `made_in_house`, so the lot has produced something to
        close at. Returns the MADE line; a force-complete books no delivery
        on it, so its delivered count shows any forced booking."""
        lot_repo = FakeProductionLotRepository()
        lot = await lot_repo.save(
            ProductionLot(
                id=0,
                created=date(2026, 1, 1),
                changed=None,
                changes=[],
                lot_number="LOT-ROLLUP",
                quantity=4.0,
                status=LotStatus.IN_PROGRESS,
                priority=UrgencyClass.NORMAL,
                note=None,
                creator_id=1,
                made_item_id=1,
                project_id=1,
                input_demand_id=None,
            )
        )
        position = await lot_repo.save_position(
            LotPosition(
                id=0,
                created=date(2026, 1, 1),
                changed=None,
                changes=[],
                sequence=1,
                kind=LotPositionKind.EXTERNAL,
                status=LotPositionStatus.ORDERED_OR_QUEUED,
                quantity=4.0,
                quantity_completed=delivered + made_in_house,
                note=None,
                creator_id=1,
                lot_id=lot.id,
            )
        )
        made = make_order_item(id=1, order_id=order.id, lot_position_id=position.id)
        made.quantity = 4.0
        made.quantity_delivered = delivered
        made.status = made_line_status
        give_order_item_facts(made)
        production_orders, bus = FakeProductionOrderRepository(), FakeEventBus()
        if made_in_house:
            stopped = make_production_order(
                1, position.id, status=ProductionOrderStatus.CANCELED, quantity=4.0
            )
            stopped.quantity_completed = made_in_house
            await production_orders.save(stopped)
        orders, lines = FakeOrderRepository([order]), FakeOrderItemRepository([made, *other_lines])
        use_case = CompleteLot(
            lot_repo,
            production_orders,
            lines,
            event_bus=bus,
            uow=FakeUnitOfWork(),
            parent_order_repo=orders,
            made_item_demand_repo=FakeMadeItemDemandRepository(),
            made_item_allocation_repo=FakeMadeItemAllocationRepository(),
            **lifecycle_collaborators(
                production_orders, lot_repo, bus, orders=orders, order_items=lines
            ),
            source_item_demand_repo=FakeSourceItemDemandRepository(),
            source_item_allocation_repo=FakeSourceItemAllocationRepository(),
            bought_allocation_repo=FakeBoughtItemAllocationRepository(),
        )

        await use_case.execute(
            make_user(permissions=[Permission.WRITE_LOTS, Permission.MANAGE_LOTS]),
            lot.id,
            CompleteLotCommand(),
        )
        return made

    async def test_force_complete_keeps_a_canceled_parent_order_canceled(self) -> None:
        order = order_in(1, OrderStatus.CANCELED)

        made = await self._complete_lot_with_made_line(
            order, OrderItemStatus.CANCELED, [], made_in_house=2.0
        )

        assert order.status == OrderStatus.CANCELED.value
        # The canceled line takes no forced delivery: CompleteLot books no
        # delivery row at all, so its delivered count stays at 0.
        assert (made.status, made.quantity_delivered) == (OrderItemStatus.CANCELED.value, 0.0)

    async def test_force_complete_next_to_a_canceled_line_makes_the_order_delivered(
        self,
    ) -> None:
        order = order_in(1, OrderStatus.ORDERED)
        canceled = bought_line(2, 1, OrderItemStatus.CANCELED)

        made = await self._complete_lot_with_made_line(
            order, OrderItemStatus.PARTIALLY_DELIVERED, [canceled], delivered=2.0
        )

        # The line is closed short at what it delivered, which completes it.
        assert order.status == OrderStatus.DELIVERED.value
        assert (made.status, made.quantity, made.quantity_delivered) == (
            OrderItemStatus.DELIVERED.value,
            2.0,
            2.0,
        )
