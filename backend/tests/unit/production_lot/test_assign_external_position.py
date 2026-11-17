"""
Unit tests for TestAssignExternalPosition and
TestAssignExternalPositionPartialAndMixed. No database, no HTTP. All
dependencies replaced with in-memory fakes.
"""

from datetime import UTC
from datetime import date
from datetime import datetime

import pytest

from src.modules.fulfillment.application.dto.production_lot_dto import AssignExternalPositionCommand
from src.modules.fulfillment.application.use_cases.production_lot.assign_external_position import (
    AssignExternalPosition,
)
from src.modules.fulfillment.application.use_cases.production_lot.assign_external_position import (
    UnassignExternalPosition,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.errors import LotInvalidStatusTransitionError
from src.modules.fulfillment.domain.errors import LotPositionAlreadyAssignedError
from src.modules.fulfillment.domain.errors import LotPositionQuantityExceedsRemainingError
from src.modules.fulfillment.domain.errors import OrderCanceledError
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.lifecycle.fake_reconciler import give_order_facts
from tests.unit.lifecycle.fake_reconciler import give_order_item_facts
from tests.unit.production_lot._helpers import make_made_item
from tests.unit.production_lot._helpers import make_order
from tests.unit.production_lot._helpers import make_order_item
from tests.unit.production_lot._helpers import make_production_order
from tests.unit.production_lot.fakes import FakeEventBus
from tests.unit.production_lot.fakes import FakeMadeItemRepository
from tests.unit.production_lot.fakes import FakeOrderItemRepository
from tests.unit.production_lot.fakes import FakeOrderRepository
from tests.unit.production_lot.fakes import FakeProductionLotRepository
from tests.unit.production_lot.fakes import FakeProductionOrderRepository
from tests.unit.production_lot.fakes import FakeProjectRepository
from tests.unit.production_lot.fakes import FakeRecomputeMachineSchedule
from tests.unit.production_lot.fakes import FakeUnitOfWork
from tests.unit.production_lot.fakes import lot_reconciler


class TestAssignExternalPosition:
    @pytest.fixture(autouse=True)
    async def _setup(self):
        self.lot_repo = FakeProductionLotRepository()
        self.made_item_repo = FakeMadeItemRepository([make_made_item()])
        self.order_repo = FakeOrderRepository([make_order(id=1, supplier_id=7)])
        self.order_item_repo = FakeOrderItemRepository()
        self.production_orders = FakeProductionOrderRepository()
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()
        self.actor = make_user(permissions=[Permission.WRITE_LOTS, Permission.WRITE_ORDERS])

        lot = ProductionLot(
            id=0,
            created=date(2026, 1, 1),
            changed=None,
            changes=[],
            lot_number="LOT-1",
            quantity=5.0,
            status=LotStatus.DRAFT,
            priority=UrgencyClass.NORMAL,
            note=None,
            creator_id=1,
            made_item_id=1,
            project_id=1,
            input_demand_id=None,
        )
        self.lot = await self.lot_repo.save(lot)
        self.position = await self.lot_repo.save_position(
            LotPosition(
                id=0,
                created=date(2026, 1, 1),
                changed=None,
                changes=[],
                sequence=1,
                kind=LotPositionKind.UNASSIGNED,
                status=LotPositionStatus.PENDING,
                quantity=5.0,
                quantity_completed=0.0,
                note=None,
                creator_id=1,
                lot_id=self.lot.id,
            )
        )

    async def test_assign_creates_made_order_item_and_flips_kind(self):
        use_case = AssignExternalPosition(
            self.lot_repo,
            self.made_item_repo,
            self.order_repo,
            self.order_item_repo,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=lot_reconciler(
                self.lot_repo,
                self.production_orders,
                orders=self.order_repo,
                order_items=self.order_item_repo,
            ),
            project_repo=FakeProjectRepository(),
        )
        result = await use_case.execute(
            self.actor,
            self.lot.id,
            self.position.id,
            AssignExternalPositionCommand(order_id=1, unit="pcs"),
        )
        assert result.kind == "external"
        order_item = await self.order_item_repo.get_by_lot_position_id(self.position.id)
        assert order_item is not None
        assert order_item.line_type == "MADE"
        assert order_item.bought_item_id is None
        assert order_item.quantity == 5.0
        # The line stores no name of its own, virtual_name belongs to
        # VIRTUAL lines. A MADE line's name is resolved from its lot's
        # made item on read, so a rename reaches lines already ordered.
        assert order_item.virtual_name is None
        assert len(self.bus.published) == 1

    async def test_assign_invokes_the_line_type_guard(self, monkeypatch):
        # The MADE line this use case builds
        # is always internally consistent (bought_item_id/source_item_id/
        # virtual_name all None, lot_position_id set), so
        # OrderRules.assert_valid_line_type can never actually reject it
        # through this call site today; defence in depth against a
        # future change to this construction, not today's behaviour. This
        # proves the call is wired rather than trying to contrive a
        # currently-impossible invalid state.
        import src.modules.fulfillment.application.use_cases.production_lot.assign_external_position as module

        calls: list[object] = []
        monkeypatch.setattr(
            module.OrderRules, "assert_valid_line_type", lambda item: calls.append(item)
        )
        use_case = AssignExternalPosition(
            self.lot_repo,
            self.made_item_repo,
            self.order_repo,
            self.order_item_repo,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=lot_reconciler(
                self.lot_repo,
                self.production_orders,
                orders=self.order_repo,
                order_items=self.order_item_repo,
            ),
            project_repo=FakeProjectRepository(),
        )
        await use_case.execute(
            self.actor,
            self.lot.id,
            self.position.id,
            AssignExternalPositionCommand(order_id=1, unit="pcs"),
        )
        assert len(calls) == 1
        assert calls[0].line_type == "MADE"

    async def test_assign_passes_through_expected_pickup_date(self):
        use_case = AssignExternalPosition(
            self.lot_repo,
            self.made_item_repo,
            self.order_repo,
            self.order_item_repo,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=lot_reconciler(
                self.lot_repo,
                self.production_orders,
                orders=self.order_repo,
                order_items=self.order_item_repo,
            ),
            project_repo=FakeProjectRepository(),
        )
        await use_case.execute(
            self.actor,
            self.lot.id,
            self.position.id,
            AssignExternalPositionCommand(
                order_id=1,
                unit="pcs",
                expected_pickup_date=date(2026, 3, 1),
            ),
        )
        order_item = await self.order_item_repo.get_by_lot_position_id(self.position.id)
        assert order_item is not None
        assert order_item.expected_pickup_date == date(2026, 3, 1)

    async def test_rejects_assignment_on_canceled_lot(self):
        self.lot.status = LotStatus.CANCELED
        await self.lot_repo.save(self.lot)
        use_case = AssignExternalPosition(
            self.lot_repo,
            self.made_item_repo,
            self.order_repo,
            self.order_item_repo,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=lot_reconciler(
                self.lot_repo,
                self.production_orders,
                orders=self.order_repo,
                order_items=self.order_item_repo,
            ),
            project_repo=FakeProjectRepository(),
        )
        with pytest.raises(LotInvalidStatusTransitionError):
            await use_case.execute(
                self.actor,
                self.lot.id,
                self.position.id,
                AssignExternalPositionCommand(order_id=1, unit="pcs"),
            )
        assert await self.order_item_repo.get_by_lot_position_id(self.position.id) is None

    async def test_rejects_assignment_on_completed_lot(self):
        self.lot.status = LotStatus.COMPLETED
        await self.lot_repo.save(self.lot)
        use_case = AssignExternalPosition(
            self.lot_repo,
            self.made_item_repo,
            self.order_repo,
            self.order_item_repo,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=lot_reconciler(
                self.lot_repo,
                self.production_orders,
                orders=self.order_repo,
                order_items=self.order_item_repo,
            ),
            project_repo=FakeProjectRepository(),
        )
        with pytest.raises(LotInvalidStatusTransitionError):
            await use_case.execute(
                self.actor,
                self.lot.id,
                self.position.id,
                AssignExternalPositionCommand(order_id=1, unit="pcs"),
            )
        assert await self.order_item_repo.get_by_lot_position_id(self.position.id) is None

    async def test_locks_the_lot(self):
        use_case = AssignExternalPosition(
            self.lot_repo,
            self.made_item_repo,
            self.order_repo,
            self.order_item_repo,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=lot_reconciler(
                self.lot_repo,
                self.production_orders,
                orders=self.order_repo,
                order_items=self.order_item_repo,
            ),
            project_repo=FakeProjectRepository(),
        )
        await use_case.execute(
            self.actor,
            self.lot.id,
            self.position.id,
            AssignExternalPositionCommand(order_id=1, unit="pcs"),
        )
        assert self.lot_repo.for_update_calls == [self.lot.id]

    async def test_assign_to_not_yet_placed_order_leaves_lot_in_draft(self):
        # The order item starts PENDING (not yet submitted to the supplier),
        # PENDING means "not committed" regardless of assignment, so the lot
        # doesn't advance until the order is actually placed (see
        # MarkOrderItemOrdered's own recompute, tested in
        # tests/unit/order/test_mark_order_item_ordered.py).
        use_case = AssignExternalPosition(
            self.lot_repo,
            self.made_item_repo,
            self.order_repo,
            self.order_item_repo,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=lot_reconciler(
                self.lot_repo,
                self.production_orders,
                orders=self.order_repo,
                order_items=self.order_item_repo,
            ),
            project_repo=FakeProjectRepository(),
        )
        await use_case.execute(
            self.actor,
            self.lot.id,
            self.position.id,
            AssignExternalPositionCommand(order_id=1, unit="pcs"),
        )
        assert (await self.lot_repo.get_by_id(self.lot.id)).status == "draft"


class TestAssignExternalPositionPartialAndMixed:
    @pytest.fixture(autouse=True)
    async def _setup(self):
        self.lot_repo = FakeProductionLotRepository()
        self.made_item_repo = FakeMadeItemRepository([make_made_item()])
        self.order_repo = FakeOrderRepository([make_order(id=1, supplier_id=7)])
        self.order_item_repo = FakeOrderItemRepository()
        self.production_orders = FakeProductionOrderRepository()
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()
        self.actor = make_user(permissions=[Permission.WRITE_LOTS, Permission.WRITE_ORDERS])
        # A canceled order is past REQUESTED, which needs manage:orders.
        self.manager = make_user(
            permissions=[Permission.WRITE_LOTS, Permission.WRITE_ORDERS, Permission.MANAGE_ORDERS]
        )

        lot = ProductionLot(
            id=0,
            created=date(2026, 1, 1),
            changed=None,
            changes=[],
            lot_number="LOT-1",
            quantity=10.0,
            status=LotStatus.DRAFT,
            priority=UrgencyClass.NORMAL,
            note=None,
            creator_id=1,
            made_item_id=1,
            project_id=1,
            input_demand_id=None,
        )
        self.lot = await self.lot_repo.save(lot)

    def _use_case(self, recompute_schedule=None) -> AssignExternalPosition:
        return AssignExternalPosition(
            self.lot_repo,
            self.made_item_repo,
            self.order_repo,
            self.order_item_repo,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=lot_reconciler(
                self.lot_repo,
                self.production_orders,
                orders=self.order_repo,
                order_items=self.order_item_repo,
            ),
            recompute_schedule=recompute_schedule,
            project_repo=FakeProjectRepository(),
        )

    def _unassign_use_case(self, recompute_schedule=None) -> UnassignExternalPosition:
        return UnassignExternalPosition(
            self.lot_repo,
            self.order_item_repo,
            uow=self.uow,
            reconciler=lot_reconciler(
                self.lot_repo,
                self.production_orders,
                orders=self.order_repo,
                order_items=self.order_item_repo,
            ),
            recompute_schedule=recompute_schedule,
        )

    async def _make_position(
        self, kind: LotPositionKind = LotPositionKind.UNASSIGNED, production_orders=None
    ) -> LotPosition:
        position = await self.lot_repo.save_position(
            LotPosition(
                id=0,
                created=date(2026, 1, 1),
                changed=None,
                changes=[],
                sequence=1,
                kind=kind,
                status=LotPositionStatus.PENDING,
                quantity=10.0,
                quantity_completed=0.0,
                note=None,
                creator_id=1,
                lot_id=self.lot.id,
            )
        )
        position.production_orders = production_orders or []
        for order in position.production_orders:
            order.lot_position_id = position.id
            await self.production_orders.save(order)
        await self.lot_repo.save_position(position)
        return position

    async def test_an_assignment_and_its_undoing_each_request_one_schedule_walk(self):
        position = await self._make_position()
        recompute = FakeRecomputeMachineSchedule()

        await self._use_case(recompute).execute(
            self.actor,
            self.lot.id,
            position.id,
            AssignExternalPositionCommand(order_id=1, unit="pcs"),
        )
        assigned = recompute.calls
        await self._unassign_use_case(recompute).execute(self.actor, self.lot.id, position.id)

        assert (assigned, recompute.calls) == (1, 2)

    async def test_partial_quantity_leaves_position_external_with_remaining(self):
        position = await self._make_position()
        result = await self._use_case().execute(
            self.actor,
            self.lot.id,
            position.id,
            AssignExternalPositionCommand(order_id=1, unit="pcs", quantity=6.0),
        )
        assert result.kind == "external"
        assert result.quantity_remaining == 4.0
        order_item = await self.order_item_repo.get_by_lot_position_id(position.id)
        assert order_item is not None
        assert order_item.quantity == 6.0

    async def test_quantity_exceeding_remaining_is_rejected(self):
        position = await self._make_position()
        with pytest.raises(LotPositionQuantityExceedsRemainingError):
            await self._use_case().execute(
                self.actor,
                self.lot.id,
                position.id,
                AssignExternalPositionCommand(order_id=1, unit="pcs", quantity=11.0),
            )

    async def test_assigning_external_onto_internal_position_becomes_mixed(self):
        internal_order = make_production_order(1, 0, status=ProductionOrderStatus.QUEUED)
        internal_order.quantity = 4.0
        position = await self._make_position(
            kind=LotPositionKind.INTERNAL, production_orders=[internal_order]
        )
        result = await self._use_case().execute(
            self.actor,
            self.lot.id,
            position.id,
            AssignExternalPositionCommand(order_id=1, unit="pcs", quantity=6.0),
        )
        assert result.kind == "mixed"
        assert result.quantity_remaining == 0.0

    async def test_already_assigned_position_is_rejected(self):
        position = await self._make_position()
        await self._use_case().execute(
            self.actor,
            self.lot.id,
            position.id,
            AssignExternalPositionCommand(order_id=1, unit="pcs", quantity=6.0),
        )
        with pytest.raises(LotPositionAlreadyAssignedError):
            await self._use_case().execute(
                self.actor,
                self.lot.id,
                position.id,
                AssignExternalPositionCommand(order_id=1, unit="pcs", quantity=1.0),
            )

    async def test_unassign_from_mixed_position_reverts_to_internal(self):
        internal_order = make_production_order(1, 0, status=ProductionOrderStatus.QUEUED)
        internal_order.quantity = 4.0
        position = await self._make_position(
            kind=LotPositionKind.INTERNAL, production_orders=[internal_order]
        )
        await self._use_case().execute(
            self.actor,
            self.lot.id,
            position.id,
            AssignExternalPositionCommand(order_id=1, unit="pcs", quantity=6.0),
        )
        assert (await self.lot_repo.get_position_by_id(position.id)).kind == "mixed"

        await self._unassign_use_case().execute(self.actor, self.lot.id, position.id)

        reverted = await self.lot_repo.get_position_by_id(position.id)
        assert reverted.kind == "internal"
        assert await self.order_item_repo.get_by_lot_position_id(position.id) is None

    async def test_an_order_someone_canceled_takes_no_assigned_position(self):
        position = await self._make_position()
        order = await self.order_repo.get_by_id(1)
        assert order is not None
        order.status = OrderStatus.CANCELED
        give_order_facts(order)

        with pytest.raises(OrderCanceledError):
            await self._use_case().execute(
                self.manager,
                self.lot.id,
                position.id,
                AssignExternalPositionCommand(order_id=1, unit="pcs", quantity=6.0),
            )

        assert await self.order_item_repo.get_by_lot_position_id(position.id) is None

    async def test_an_order_canceled_only_by_its_lines_takes_an_assigned_position(self):
        """A placed order whose every line was canceled, for example by a lot
        cancel, reads canceled without its cancel intent. It takes the new
        line and derives from it: ordered again."""
        position = await self._make_position()
        order = await self.order_repo.get_by_id(1)
        assert order is not None
        order.status, order.ordered_date = OrderStatus.CANCELED, datetime(2026, 1, 2, tzinfo=UTC)
        canceled = make_order_item(id=50, order_id=1, line_type=OrderLineType.BOUGHT)
        canceled.bought_item_id, canceled.status = 1, OrderItemStatus.CANCELED
        await self.order_item_repo.save(give_order_item_facts(canceled))

        await self._use_case().execute(
            self.manager,
            self.lot.id,
            position.id,
            AssignExternalPositionCommand(order_id=1, unit="pcs", quantity=6.0),
        )

        line = await self.order_item_repo.get_by_lot_position_id(position.id)
        assert line is not None and line.status == "pending"
        assert (order.status, order.canceled_at) == ("ordered", None)

    async def test_unassigning_the_last_open_line_delivers_its_order(self):
        """The order is derived again without the removed line: next to a
        delivered line only, it is delivered and gets its delivery date."""
        position = await self._make_position()
        await self._use_case().execute(
            self.actor,
            self.lot.id,
            position.id,
            AssignExternalPositionCommand(order_id=1, unit="pcs", quantity=6.0),
        )
        delivered = make_order_item(id=50, order_id=1, line_type=OrderLineType.BOUGHT)
        delivered.bought_item_id = 1
        delivered.status, delivered.quantity_delivered = (
            OrderItemStatus.DELIVERED,
            delivered.quantity,
        )
        await self.order_item_repo.save(give_order_item_facts(delivered))
        order = await self.order_repo.get_by_id(1)
        assert order is not None
        order.status = OrderStatus.PARTIALLY_DELIVERED
        give_order_facts(order)

        await self._unassign_use_case().execute(self.actor, self.lot.id, position.id)

        assert await self.order_item_repo.get_by_lot_position_id(position.id) is None
        assert order.status == "delivered"
        assert order.delivery_date is not None

    async def test_unassign_requires_write_lots(self):
        internal_order = make_production_order(1, 0, status=ProductionOrderStatus.QUEUED)
        internal_order.quantity = 4.0
        position = await self._make_position(
            kind=LotPositionKind.INTERNAL, production_orders=[internal_order]
        )
        await self._use_case().execute(
            self.actor,
            self.lot.id,
            position.id,
            AssignExternalPositionCommand(order_id=1, unit="pcs", quantity=6.0),
        )
        assert await self.order_item_repo.get_by_lot_position_id(position.id) is not None

        permissionless = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self._unassign_use_case().execute(permissionless, self.lot.id, position.id)
        # Nothing deleted.
        assert await self.order_item_repo.get_by_lot_position_id(position.id) is not None
