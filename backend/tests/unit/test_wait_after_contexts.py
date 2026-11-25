"""
The scheduling context of an order reads the wait after its predecessor from
the predecessor's last step and its own wait from its own step. A completed
predecessor still holds the order while its wait runs, and holds nothing
once the wait is over.
"""

from datetime import UTC
from datetime import date
from datetime import datetime

from src.modules.fulfillment.application.services.scheduling_context import build_order_context
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from tests.unit.test_response_time_days_buffer import build_repos
from tests.unit.test_response_time_days_buffer import make_lot
from tests.unit.test_response_time_days_buffer import make_order
from tests.unit.test_response_time_days_buffer import make_position

TODAY = date(2026, 1, 10)


def _lot_with_wait(predecessor_wait: int | None, own_wait: int | None = None):
    lot = make_lot()
    predecessor = make_position(id=1, sequence=1)
    predecessor.steps[0].method_wait_after_minutes = predecessor_wait
    successor = make_position(id=2, sequence=2)
    successor.steps[0].method_wait_after_minutes = own_wait
    lot.positions = [predecessor, successor]
    return lot, predecessor


async def _context(lot, orders, successor_order):
    return await build_order_context(
        successor_order,
        lot,
        machine=None,
        repos=build_repos(orders=orders),
        target_date=None,
        internal_handoff_minutes=15,
        zone=UTC,
        today=TODAY,
    )


async def test_the_predecessors_wait_and_the_handoff_both_follow_its_end():
    lot, _ = _lot_with_wait(predecessor_wait=600, own_wait=90)
    predecessor_order = make_order(id=10, lot_position_id=1)
    predecessor_order.planned_end = datetime(2026, 1, 10, 14, 0, tzinfo=UTC)
    successor_order = make_order(id=20, lot_position_id=2)

    ctx = await _context(lot, [predecessor_order, successor_order], successor_order)

    # 14:00 plus 600 minutes of waiting plus 15 handoff minutes.
    assert ctx.predecessor_ready_moment == datetime(2026, 1, 11, 0, 15, tzinfo=UTC)
    assert ctx.predecessor_ready_at == date(2026, 1, 11)
    assert ctx.wait_after_minutes == 90


async def test_a_completed_predecessor_holds_the_order_while_its_wait_runs():
    lot, predecessor = _lot_with_wait(predecessor_wait=1440)
    predecessor.status = LotPositionStatus.COMPLETED
    done = make_order(id=10, lot_position_id=1)
    done.status = ProductionOrderStatus.COMPLETED
    done.actual_end = datetime(2026, 1, 10, 9, 0, tzinfo=UTC)
    successor_order = make_order(id=20, lot_position_id=2)

    ctx = await _context(lot, [done, successor_order], successor_order)

    assert ctx.predecessor_ready_at == date(2026, 1, 11)
    assert ctx.predecessor_ready_moment == datetime(2026, 1, 11, 9, 15, tzinfo=UTC)
    assert ctx.predecessor_chain_unknown is False


async def test_a_completed_predecessor_whose_wait_is_over_holds_nothing():
    lot, predecessor = _lot_with_wait(predecessor_wait=60)
    predecessor.status = LotPositionStatus.COMPLETED
    done = make_order(id=10, lot_position_id=1)
    done.status = ProductionOrderStatus.COMPLETED
    done.actual_end = datetime(2026, 1, 8, 9, 0, tzinfo=UTC)
    successor_order = make_order(id=20, lot_position_id=2)

    ctx = await _context(lot, [done, successor_order], successor_order)

    assert ctx.predecessor_positions == ()
    assert ctx.predecessor_ready_at is None
    assert ctx.predecessor_ready_moment is None
    assert ctx.predecessor_chain_unknown is False
