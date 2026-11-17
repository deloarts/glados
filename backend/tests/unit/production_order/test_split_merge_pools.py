"""
A split keeps its parts in the queue of the order it splits: the order's
machine, or its machine pool while no machine is resolved. The parts copy
the pool, draw their places from that queue under its lock, and are
registered with the lifecycle reconciler as rows this transaction created,
so they take no row lock. A merge joins orders of one machine and one pool
only; a merged-away order is canceled through canceled_at and the
reconciler. No database, no HTTP.
"""

import pytest

from src.modules.fulfillment.application.dto.production_order_dto import (
    MergeProductionOrdersCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import SplitProductionOrderCommand
from src.modules.fulfillment.application.use_cases.production_order.merge_production_orders import (
    MergeProductionOrders,
)
from src.modules.fulfillment.application.use_cases.production_order.split_production_order import (
    SplitProductionOrder,
)
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.errors import ProductionOrderCannotMergeError
from src.modules.fulfillment.domain.errors import ProductionOrderNotSplittableError
from src.modules.fulfillment.domain.events.production_order_events import ProductionOrderCanceled
from src.modules.fulfillment.domain.events.production_order_events import (
    ProductionOrderStatusChanged,
)
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.production_order._helpers import make_lot
from tests.unit.production_order._helpers import make_order
from tests.unit.production_order._helpers import make_position
from tests.unit.production_order.fakes import FakeAdminSettingsRepository
from tests.unit.production_order.fakes import FakeEventBus
from tests.unit.production_order.fakes import FakeProductionLotRepository
from tests.unit.production_order.fakes import FakeProductionOrderRepository
from tests.unit.production_order.fakes import FakeUnitOfWork
from tests.unit.production_order.fakes import production_order_reconciler

_ACTOR = make_user(permissions=[Permission.WRITE_PRODUCTION_ORDERS])
_POOL = 3


class _Queue:
    def __init__(self, *orders: ProductionOrder) -> None:
        self.order_repo = FakeProductionOrderRepository(list(orders))
        self.lot_repo = FakeProductionLotRepository(
            [make_lot(positions=[make_position(id=1, quantity=10.0)])]
        )
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()

    def split(self) -> SplitProductionOrder:
        return SplitProductionOrder(
            self.order_repo,
            self.lot_repo,
            FakeAdminSettingsRepository(),
            event_bus=self.bus,
            uow=self.uow,
            reconciler=production_order_reconciler(self.order_repo, self.lot_repo, self.bus),
        )

    def merge(self) -> MergeProductionOrders:
        return MergeProductionOrders(
            self.order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=production_order_reconciler(self.order_repo, self.lot_repo, self.bus),
        )


class TestSplit:
    async def test_the_parts_of_a_pool_order_stay_in_the_pools_queue(self):
        queue = _Queue(
            make_order(id=1, machine_id=None, machine_pool_id=_POOL, queue_sequence=4),
            make_order(id=2, machine_id=None, machine_pool_id=_POOL, queue_sequence=7),
            # Another queue, whose places the parts must not follow.
            make_order(id=3, machine_id=None, machine_pool_id=None, queue_sequence=20),
        )

        results = await queue.split().execute(
            _ACTOR, production_order_id=1, cmd=SplitProductionOrderCommand(quantities=[6.0, 4.0])
        )

        source, part = results
        assert (source.id, source.quantity) == (1, 6.0)
        assert part.quantity == 4.0
        assert (part.machine_id, part.machine_pool_id) == (None, _POOL)
        assert part.queue_sequence == 8
        assert part.status == ProductionOrderStatus.QUEUED.value
        assert queue.order_repo.queue_locks == [(None, _POOL)]

    async def test_the_parts_of_a_machine_order_keep_its_machine_and_pool(self):
        queue = _Queue(make_order(id=1, machine_id=5, machine_pool_id=_POOL, queue_sequence=2))

        results = await queue.split().execute(
            _ACTOR,
            production_order_id=1,
            cmd=SplitProductionOrderCommand(quantities=[5.0, 3.0, 2.0]),
        )

        parts = results[1:]
        assert [(p.machine_id, p.machine_pool_id) for p in parts] == [(5, _POOL), (5, _POOL)]
        assert [p.queue_sequence for p in parts] == [3, 4]
        assert queue.order_repo.queue_locks == [(5, _POOL)]

    async def test_only_the_split_order_is_row_locked_the_parts_are_new(self):
        queue = _Queue(make_order(id=1, machine_id=5, machine_pool_id=_POOL))

        results = await queue.split().execute(
            _ACTOR, production_order_id=1, cmd=SplitProductionOrderCommand(quantities=[6.0, 4.0])
        )

        assert queue.lot_repo.lock_calls == [[1]]
        assert queue.order_repo.lock_calls == [[1]]
        assert [r.status for r in results] == [ProductionOrderStatus.QUEUED.value] * 2
        assert queue.uow.commits == 1

    async def test_a_running_order_is_not_split(self):
        queue = _Queue(make_order(id=1, status=ProductionOrderStatus.IN_PROGRESS))

        with pytest.raises(ProductionOrderNotSplittableError, match="in_progress"):
            await queue.split().execute(
                _ACTOR,
                production_order_id=1,
                cmd=SplitProductionOrderCommand(quantities=[6.0, 4.0]),
            )

        assert list(queue.order_repo.orders) == [1]
        assert queue.uow.commits == 0


class TestMerge:
    async def test_orders_of_different_pools_are_not_merged(self):
        queue = _Queue(
            make_order(id=1, machine_id=None, machine_pool_id=_POOL, quantity=6.0),
            make_order(id=2, machine_id=None, machine_pool_id=_POOL + 1, quantity=4.0),
        )

        with pytest.raises(ProductionOrderCannotMergeError, match="different machine pools"):
            await queue.merge().execute(
                _ACTOR, cmd=MergeProductionOrdersCommand(production_order_ids=[1, 2])
            )

        assert [o.canceled_at for o in queue.order_repo.orders.values()] == [None, None]
        assert queue.uow.commits == 0

    async def test_a_machine_order_and_a_pool_order_are_not_merged(self):
        queue = _Queue(
            make_order(id=1, machine_id=5, machine_pool_id=_POOL, quantity=6.0),
            make_order(id=2, machine_id=5, machine_pool_id=None, quantity=4.0),
        )

        with pytest.raises(ProductionOrderCannotMergeError, match="different machine pools"):
            await queue.merge().execute(
                _ACTOR, cmd=MergeProductionOrdersCommand(production_order_ids=[1, 2])
            )

    async def test_the_merged_away_order_is_canceled_by_the_reconciler(self):
        queue = _Queue(
            make_order(
                id=1, machine_id=None, machine_pool_id=_POOL, quantity=6.0, queue_sequence=1
            ),
            make_order(
                id=2, machine_id=None, machine_pool_id=_POOL, quantity=4.0, queue_sequence=2
            ),
        )

        result = await queue.merge().execute(
            _ACTOR, cmd=MergeProductionOrdersCommand(production_order_ids=[1, 2])
        )

        keeper, merged = queue.order_repo.orders[1], queue.order_repo.orders[2]
        assert (result.id, result.quantity, result.status) == (1, 10.0, "queued")
        assert keeper.status == ProductionOrderStatus.QUEUED.value
        assert merged.status == ProductionOrderStatus.CANCELED.value
        assert merged.canceled_at is not None
        assert merged.quantity == 0.0
        changes = [e for e in queue.bus.published if isinstance(e, ProductionOrderStatusChanged)]
        assert [(e.production_order_id, e.new_status) for e in changes] == [
            (2, ProductionOrderStatus.CANCELED)
        ]
        canceled = [e for e in queue.bus.published if isinstance(e, ProductionOrderCanceled)]
        assert [e.production_order_id for e in canceled] == [2]

    async def test_the_lot_and_every_merged_order_are_locked_first(self):
        queue = _Queue(
            make_order(id=1, quantity=6.0, queue_sequence=1),
            make_order(id=2, quantity=4.0, queue_sequence=2),
        )

        await queue.merge().execute(
            _ACTOR, cmd=MergeProductionOrdersCommand(production_order_ids=[2, 1])
        )

        assert queue.lot_repo.lock_calls == [[1]]
        assert queue.order_repo.lock_calls == [[1, 2]]


class TestPinnedOrders:
    """A pinned order changes only in the hands of a manager, as on every
    other edit of it."""

    async def test_a_pinned_order_is_not_split_without_the_manage_permission(self):
        queue = _Queue(make_order(id=1, machine_id=5, pinned=True))

        with pytest.raises(InsufficientPermissionsError, match="pinned"):
            await queue.split().execute(
                _ACTOR,
                production_order_id=1,
                cmd=SplitProductionOrderCommand(quantities=[6.0, 4.0]),
            )

    async def test_a_pinned_order_is_not_merged_without_the_manage_permission(self):
        queue = _Queue(
            make_order(id=1, machine_id=5, queue_sequence=1, pinned=True),
            make_order(id=2, machine_id=5, queue_sequence=2),
        )

        with pytest.raises(InsufficientPermissionsError, match="pinned"):
            await queue.merge().execute(
                _ACTOR, MergeProductionOrdersCommand(production_order_ids=[1, 2])
            )


async def test_a_split_moves_the_edit_version_of_the_order_it_shrinks():
    """A client that read the order before the split would otherwise edit
    the duration computed for the whole quantity."""
    queue = _Queue(make_order(id=1, machine_id=5))
    before = queue.order_repo._orders[1].edit_version

    source, _part = await queue.split().execute(
        _ACTOR, production_order_id=1, cmd=SplitProductionOrderCommand(quantities=[6.0, 4.0])
    )

    assert source.edit_version == before + 1
