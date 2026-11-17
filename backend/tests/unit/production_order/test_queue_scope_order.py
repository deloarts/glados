"""
Every writer that draws a queue place takes the queue's lock before any row
lock, the order Auto-Plan, a reorder and a reassignment keep, and refuses
with ConcurrentModificationError when the order moved to another queue
between its unlocked read and its locks. One log records the queue locks and
the row locks of the lot and production order fakes in the order they are
taken. No database, no HTTP.
"""

from datetime import UTC
from datetime import datetime
from typing import Any

import pytest

from src.modules.fulfillment.application.dto.production_order_dto import (
    AssignInternalPositionCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import (
    AssignInternalPositionOrderInput,
)
from src.modules.fulfillment.application.dto.production_order_dto import (
    ReassignProductionOrderMachineCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import (
    ReorderProductionOrdersCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import SplitProductionOrderCommand
from src.modules.fulfillment.application.dto.production_order_dto import StartProductionOrderCommand
from src.modules.fulfillment.application.dto.production_order_dto import (
    UpdateProductionOrderCommand,
)
from src.modules.fulfillment.application.use_cases.production_order.assign_internal_position import (
    AssignInternalPosition,
)
from src.modules.fulfillment.application.use_cases.production_order.production_order_lifecycle import (
    StartProductionOrder,
)
from src.modules.fulfillment.application.use_cases.production_order.reassign_production_order_machine import (
    ReassignProductionOrderMachine,
)
from src.modules.fulfillment.application.use_cases.production_order.reorder_production_orders import (
    ReorderProductionOrders,
)
from src.modules.fulfillment.application.use_cases.production_order.split_production_order import (
    SplitProductionOrder,
)
from src.modules.fulfillment.application.use_cases.production_order.update_production_order import (
    UpdateProductionOrder,
)
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.platform.domain.exceptions import ConcurrentModificationError
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.production_order._helpers import make_lot
from tests.unit.production_order._helpers import make_machine
from tests.unit.production_order._helpers import make_order
from tests.unit.production_order._helpers import make_pool
from tests.unit.production_order._helpers import make_position
from tests.unit.production_order.fakes import FakeAdminSettingsRepository
from tests.unit.production_order.fakes import FakeEventBus
from tests.unit.production_order.fakes import FakeMachinePoolRepository
from tests.unit.production_order.fakes import FakeProductionLotRepository
from tests.unit.production_order.fakes import FakeProductionMachineRepository
from tests.unit.production_order.fakes import FakeProductionOrderRepository
from tests.unit.production_order.fakes import FakeUnitOfWork
from tests.unit.production_order.fakes import lifecycle_collaborators
from tests.unit.production_order.fakes import production_order_reconciler

_ACTOR = make_user(
    permissions=[Permission.WRITE_PRODUCTION_ORDERS, Permission.MANAGE_PRODUCTION_ORDERS]
)
_POOL = 3


class _World:
    """A lot with one internal position and its orders, whose queue locks
    and row locks are logged in one list. `on_lot_lock` runs when the lot
    is first locked, standing for a change another request committed
    between the unlocked read and the locks."""

    def __init__(self, *orders: Any) -> None:
        self.log: list[tuple[str, Any]] = []
        self.on_lot_lock: Any = None
        position = make_position(id=1, quantity=10.0, kind=LotPositionKind.INTERNAL)
        lot = make_lot(positions=[position])
        lot.source_made_item_id = 99
        self.lot_repo = FakeProductionLotRepository([lot])
        self.order_repo = FakeProductionOrderRepository(list(orders))
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()
        self._spy()

    def _spy(self) -> None:
        orders, lots = self.order_repo, self.lot_repo
        lock_scope, lock_orders, lock_lots = (
            orders.lock_queue_scope,
            orders.lock_for_update,
            lots.lock_for_update,
        )

        async def scope(machine_id: int | None, machine_pool_id: int | None = None) -> None:
            self.log.append(("scope", (machine_id, machine_pool_id)))
            await lock_scope(machine_id, machine_pool_id)

        async def order_rows(ids: list[int]) -> None:
            self.log.append(("production_orders", tuple(ids)))
            await lock_orders(ids)

        async def lot_rows(ids: list[int]) -> None:
            self.log.append(("lots", tuple(ids)))
            if self.on_lot_lock is not None:
                self.on_lot_lock()
                self.on_lot_lock = None
            await lock_lots(ids)

        orders.lock_queue_scope = scope  # type: ignore[method-assign]
        orders.lock_for_update = order_rows  # type: ignore[method-assign]
        lots.lock_for_update = lot_rows  # type: ignore[method-assign]

    def reconciler(self) -> Any:
        return production_order_reconciler(self.order_repo, self.lot_repo, self.bus)

    def kinds(self) -> list[str]:
        return [kind for kind, _ in self.log]

    def move(self, order_id: int, machine_id: int | None, pool_id: int | None) -> None:
        order = self.order_repo.orders[order_id]
        order.machine_id, order.machine_pool_id = machine_id, pool_id


def _scope_before_rows(world: _World) -> None:
    kinds = world.kinds()
    assert "scope" in kinds
    rows = [i for i, kind in enumerate(kinds) if kind != "scope"]
    assert rows, kinds
    assert max(i for i, kind in enumerate(kinds) if kind == "scope") < min(rows), kinds


class TestSplit:
    def _split(self, world: _World) -> SplitProductionOrder:
        return SplitProductionOrder(
            world.order_repo,
            world.lot_repo,
            FakeAdminSettingsRepository(),
            event_bus=world.bus,
            uow=world.uow,
            reconciler=world.reconciler(),
        )

    async def test_the_queue_is_locked_before_the_lot_and_the_order(self):
        world = _World(make_order(id=1, machine_id=5, machine_pool_id=None))

        await self._split(world).execute(
            _ACTOR, production_order_id=1, cmd=SplitProductionOrderCommand(quantities=[6.0, 4.0])
        )

        _scope_before_rows(world)

    async def test_an_order_moved_to_another_queue_meanwhile_is_refused(self):
        world = _World(make_order(id=1, machine_id=5, machine_pool_id=None))
        world.on_lot_lock = lambda: world.move(1, 6, None)

        with pytest.raises(ConcurrentModificationError):
            await self._split(world).execute(
                _ACTOR,
                production_order_id=1,
                cmd=SplitProductionOrderCommand(quantities=[6.0, 4.0]),
            )

        assert world.uow.commits == 0
        assert len(world.order_repo.orders) == 1


class TestPoolStart:
    def _start(self, world: _World) -> StartProductionOrder:
        return StartProductionOrder(
            world.order_repo,
            world.lot_repo,
            machine_repo=FakeProductionMachineRepository([make_machine(id=1)]),
            pool_repo=FakeMachinePoolRepository(
                [make_pool(id=_POOL, machine_ids=[1], machines=[make_machine(id=1)])]
            ),
            event_bus=world.bus,
            uow=world.uow,
            **lifecycle_collaborators(world.order_repo, world.lot_repo, world.bus),
        )

    async def test_the_members_queue_is_locked_before_the_lot_and_the_order(self):
        world = _World(make_order(id=1, machine_id=None, machine_pool_id=_POOL))

        await self._start(world).execute(
            _ACTOR, production_order_id=1, cmd=StartProductionOrderCommand(machine_id=1)
        )

        _scope_before_rows(world)
        assert world.log[0] == ("scope", (1, _POOL))

    async def test_an_order_resolved_onto_a_machine_meanwhile_takes_no_late_queue_lock(self):
        world = _World(make_order(id=1, machine_id=5, machine_pool_id=None))
        world.on_lot_lock = lambda: world.move(1, None, _POOL)

        with pytest.raises(ConcurrentModificationError):
            await self._start(world).execute(
                _ACTOR, production_order_id=1, cmd=StartProductionOrderCommand(machine_id=1)
            )

        assert world.uow.commits == 0
        # The machine's queue, read before the locks, is the only queue
        # locked, and before the row locks; none is taken late.
        kinds = world.kinds()
        assert kinds[0] == "scope"
        assert "scope" not in kinds[1:]


class TestAssignInternal:
    async def test_the_target_queues_are_locked_before_the_lot(self):
        world = _World()
        use_case = AssignInternalPosition(
            world.lot_repo,
            FakeProductionMachineRepository([make_machine(id=1), make_machine(id=2)]),
            world.order_repo,
            FakeAdminSettingsRepository(),
            event_bus=world.bus,
            uow=world.uow,
            reconciler=world.reconciler(),
        )

        await use_case.execute(
            _ACTOR,
            lot_id=1,
            position_id=1,
            cmd=AssignInternalPositionCommand(
                orders=[
                    AssignInternalPositionOrderInput(machine_id=2, quantity=4.0),
                    AssignInternalPositionOrderInput(machine_id=1, quantity=6.0),
                ]
            ),
        )

        _scope_before_rows(world)
        assert [entry for entry in world.log if entry[0] == "scope"] == [
            ("scope", (1, None)),
            ("scope", (2, None)),
        ]


class TestUpdateProductionOrder:
    def _update(self, world: _World) -> UpdateProductionOrder:
        return UpdateProductionOrder(
            world.order_repo, uow=world.uow, lock_plan=world.reconciler().lock_plan
        )

    async def test_a_pin_takes_the_queue_lock_before_the_row_lock(self):
        world = _World(make_order(id=1, machine_id=5))

        await self._update(world).execute(
            _ACTOR, production_order_id=1, cmd=UpdateProductionOrderCommand(pinned=True)
        )

        assert world.log == [("scope", (5, None)), ("production_orders", (1,))]
        assert world.order_repo.orders[1].pinned is True

    async def test_a_note_takes_the_row_lock_alone(self):
        world = _World(make_order(id=1, machine_id=5))

        await self._update(world).execute(
            _ACTOR, production_order_id=1, cmd=UpdateProductionOrderCommand(note="Mind the burr.")
        )

        assert world.log == [("production_orders", (1,))]

    async def test_a_pin_on_an_order_moved_meanwhile_is_refused(self):
        world = _World(make_order(id=1, machine_id=5))
        order_rows = world.order_repo.lock_for_update

        async def moved_while_waiting(ids: list[int]) -> None:
            await order_rows(ids)
            world.move(1, 6, None)

        world.order_repo.lock_for_update = moved_while_waiting  # type: ignore[method-assign]

        with pytest.raises(ConcurrentModificationError):
            await self._update(world).execute(
                _ACTOR,
                production_order_id=1,
                cmd=UpdateProductionOrderCommand(
                    planned_start=datetime(2026, 3, 2, 8, tzinfo=UTC),
                    planned_end=datetime(2026, 3, 2, 9, tzinfo=UTC),
                    recompute_planned_end=False,
                ),
            )

        assert world.uow.commits == 0
        assert world.order_repo.orders[1].pinned is False


class TestReassign:
    def _reassign(self, world: _World) -> ReassignProductionOrderMachine:
        return ReassignProductionOrderMachine(
            world.order_repo,
            world.lot_repo,
            FakeProductionMachineRepository([make_machine(id=7)]),
            event_bus=world.bus,
            uow=world.uow,
            lock_plan=world.reconciler().lock_plan,
        )

    async def test_the_target_queue_is_locked_before_the_order_row(self):
        world = _World(make_order(id=1, machine_id=5))

        await self._reassign(world).execute(
            _ACTOR, production_order_id=1, cmd=ReassignProductionOrderMachineCommand(machine_id=7)
        )

        assert world.log == [("scope", (7, None)), ("production_orders", (1,))]
        assert world.order_repo.orders[1].machine_id == 7

    async def test_an_order_pinned_meanwhile_is_checked_under_the_lock(self):
        world = _World(make_order(id=1, machine_id=5))
        order_rows = world.order_repo.lock_for_update

        async def pinned_while_waiting(ids: list[int]) -> None:
            await order_rows(ids)
            world.order_repo.orders[1].pinned = True

        world.order_repo.lock_for_update = pinned_while_waiting  # type: ignore[method-assign]

        with pytest.raises(InsufficientPermissionsError, match="pinned"):
            await self._reassign(world).execute(
                _ACTOR,
                production_order_id=1,
                cmd=ReassignProductionOrderMachineCommand(machine_id=7),
            )

        assert world.order_repo.orders[1].machine_id == 5

    async def test_an_order_moved_to_another_pool_at_the_row_lock_is_refused(self):
        world = _World(make_order(id=1, machine_id=None, machine_pool_id=_POOL))
        order_rows = world.order_repo.lock_for_update

        async def moved_while_waiting(ids: list[int]) -> None:
            await order_rows(ids)
            world.move(1, None, _POOL + 1)

        world.order_repo.lock_for_update = moved_while_waiting  # type: ignore[method-assign]

        with pytest.raises(ConcurrentModificationError):
            await self._reassign(world).execute(
                _ACTOR, production_order_id=1, cmd=ReassignProductionOrderMachineCommand()
            )

        assert world.log[0] == ("scope", (None, _POOL))
        assert world.uow.commits == 0
        assert world.order_repo.orders[1].machine_pool_id == _POOL + 1


class TestReorder:
    async def test_the_queue_is_locked_before_the_rows_it_moves(self):
        world = _World(
            make_order(id=1, machine_id=5, queue_sequence=1),
            make_order(id=2, machine_id=5, queue_sequence=2),
        )
        use_case = ReorderProductionOrders(
            world.order_repo,
            event_bus=world.bus,
            uow=world.uow,
            lock_plan=world.reconciler().lock_plan,
        )

        await use_case.execute(
            _ACTOR, 5, ReorderProductionOrdersCommand(ordered_production_order_ids=[2, 1])
        )

        assert world.log == [("scope", (5, None)), ("production_orders", (1, 2))]
        assert world.order_repo.orders[2].queue_sequence == 1
