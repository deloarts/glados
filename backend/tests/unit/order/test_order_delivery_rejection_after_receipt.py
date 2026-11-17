"""
A correction that carries a RejectionAfterReceipt takes accepted pieces of a
delivery row back as rejected ones, for damage found after the goods were
accepted. The new row holds the negative accepted quantity and the rejected
pieces with their reason, note and outcome, so every total of the line stays
the sum of its rows. Lost pieces count as settled and refit the line's
allocations, pieces sent back for redelivery leave the line open and clear
its expected delivery date, and the rejection is announced with
DeliveryPiecesRejected. The guards are the correction's. The world and its
builders come from test_order_delivery_correction.py.
"""

from datetime import date

import pytest

from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.fulfillment.domain.errors import DeliveryCannotBeCorrectedError
from src.modules.fulfillment.domain.errors import DeliveryRejectionInvalidError
from src.modules.fulfillment.domain.events.order_events import DeliveryPiecesRejected
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.rejection_after_receipt import (
    RejectionAfterReceipt,
)
from src.modules.fulfillment.domain.value_objects.rejection_outcome import RejectionOutcome
from tests.unit.lifecycle.fake_demand_reconciler import demand_reconciler_harness
from tests.unit.order._helpers import FakeEventBus
from tests.unit.order._helpers import make_allocation
from tests.unit.order._helpers import make_demand
from tests.unit.order.test_order_delivery_correction import _BOOKED
from tests.unit.order.test_order_delivery_correction import _EARLIER
from tests.unit.order.test_order_delivery_correction import RECEIVER
from tests.unit.order.test_order_delivery_correction import _dated
from tests.unit.order.test_order_delivery_correction import _row
from tests.unit.order.test_order_delivery_correction import _World

_LOST = RejectionAfterReceipt(
    reason="transport_damage", outcome=RejectionOutcome.LOST, note="Crushed corner"
)
_REDELIVER = RejectionAfterReceipt(reason="supplier_damage", outcome=RejectionOutcome.REDELIVER)


def _delivered(**kwargs) -> _World:
    """Ten pieces delivered in two rows, six and four, on a world whose
    correction publishes to a recording bus."""
    world = _World([_row(6.0), _row(4.0)], status=OrderItemStatus.DELIVERED, **kwargs)
    world.bus = FakeEventBus()
    world.use_case._bus = world.bus
    return world


async def _reject(
    world: _World, delivery_id: int, quantity: float, rejection: RejectionAfterReceipt
):
    return await world.use_case.execute(
        RECEIVER, 1, 1, delivery_id, quantity, None, rejection=rejection
    )


def _with_demand_reconciler(world: _World) -> None:
    harness = demand_reconciler_harness(
        bought_demands=world.use_case._demands,
        bought_allocations=world.use_case._allocations,
        order_items=world.lines,
        orders=world.orders,
    )
    world.use_case._reconciler = harness.reconciler


class TestRejectionAfterReceipt:
    async def test_the_row_takes_the_pieces_back_as_rejected_ones(self) -> None:
        world = _delivered()

        result = await _reject(world, 1, 2.0, _LOST)

        row = (await world.rows())[-1]
        assert (row.quantity, row.quantity_rejected) == (-2.0, 2.0)
        assert (row.rejection_reason, row.rejection_outcome, row.rejection_note) == (
            "transport_damage",
            RejectionOutcome.LOST,
            "Crushed corner",
        )
        assert (row.corrects_delivery_id, row.correction_reason) == (1, None)
        assert [r.corrects_delivery_id for r in result.delivery_records] == [None, None, 1]
        assert world.uow.committed is True

    async def test_every_total_stays_the_sum_of_the_rows(self) -> None:
        world = _delivered()

        await _reject(world, 1, 2.0, _LOST)
        await _reject(world, 2, 1.0, _REDELIVER)

        rows = await world.rows()
        lost = [r for r in rows if r.rejection_outcome == RejectionOutcome.LOST]
        assert world.line.quantity_delivered == sum(r.quantity for r in rows) == 7.0
        assert world.line.quantity_rejected == sum(r.quantity_rejected for r in rows) == 3.0
        assert world.line.quantity_rejected_lost == sum(r.quantity_rejected for r in lost) == 2.0

    async def test_lost_pieces_count_as_settled_so_the_line_stays_delivered(self) -> None:
        world = _delivered()

        result = await _reject(world, 1, 2.0, _LOST)

        assert (world.line.quantity_delivered, world.line.quantity_rejected_lost) == (8.0, 2.0)
        assert (result.status, world.line.status, world.order.status) == (
            "delivered",
            "delivered",
            "delivered",
        )
        assert world.line.changes[-1].endswith(
            "Delivery #1: rejected 2.000 pcs after receipt (transport_damage, lost); "
            "8.000/10.000 delivered."
        )

    async def test_pieces_sent_back_reopen_the_line_and_clear_the_expected_date(self) -> None:
        world = _delivered()
        world.line.expected_delivery_date = date(2026, 3, 1)

        result = await _reject(world, 2, 4.0, _REDELIVER)

        assert (world.line.quantity_delivered, world.line.quantity_rejected_lost) == (6.0, 0.0)
        assert world.line.quantity_rejected == 4.0
        assert world.line.expected_delivery_date is None
        assert (result.status, world.order.status) == (
            "partially_delivered",
            "partially_delivered",
        )

    async def test_the_rejection_is_announced(self) -> None:
        world = _delivered()

        await _reject(world, 1, 2.0, _LOST)

        rejected = [e for e in world.bus.published if isinstance(e, DeliveryPiecesRejected)]
        assert [(e.order_item_id, e.quantity, e.reason, e.outcome) for e in rejected] == [
            (1, 2.0, "transport_damage", "lost")
        ]

    async def test_a_miscount_publishes_no_rejection(self) -> None:
        world = _delivered()

        await world.correct(1, 2.0)

        assert not [e for e in world.bus.published if isinstance(e, DeliveryPiecesRejected)]

    async def test_lost_pieces_refit_the_allocations_and_reopen_the_demand(self) -> None:
        demand = make_demand(id=1, status=BoughtItemDemandStatus.FULFILLED)
        world = _delivered(
            allocations=[make_allocation(demand_item_id=1, order_item_id=1, quantity=10.0)],
            demands=[demand],
        )
        _with_demand_reconciler(world)

        await _reject(world, 1, 2.0, _LOST)

        allocations = await world.use_case._allocations.get_by_order_item_id(1)
        assert {a.quantity for a in allocations} == {8.0}
        stored = await world.use_case._demands.get_by_id(1)
        assert stored is not None and stored.status != BoughtItemDemandStatus.FULFILLED.value

    async def test_pieces_sent_back_keep_the_allocations(self) -> None:
        demand = make_demand(id=1, status=BoughtItemDemandStatus.FULFILLED)
        world = _delivered(
            allocations=[make_allocation(demand_item_id=1, order_item_id=1, quantity=10.0)],
            demands=[demand],
        )
        _with_demand_reconciler(world)

        await _reject(world, 1, 2.0, _REDELIVER)

        allocations = await world.use_case._allocations.get_by_order_item_id(1)
        assert {a.quantity for a in allocations} == {10.0}
        stored = await world.use_case._demands.get_by_id(1)
        assert stored is not None and stored.status == BoughtItemDemandStatus.ORDERED.value

    async def test_a_row_rejected_entirely_after_receipt_still_counts_as_an_arrival(
        self,
    ) -> None:
        world = _World([_dated(_row(6.0), _EARLIER), _row(4.0)], status=OrderItemStatus.DELIVERED)
        world.line.delivery_date = _BOOKED

        await _reject(world, 2, 4.0, _REDELIVER)

        assert world.line.delivery_date == _BOOKED

    async def test_it_takes_back_no_more_than_the_row_accepted(self) -> None:
        world = _delivered()
        await _reject(world, 2, 3.0, _LOST)

        with pytest.raises(DeliveryCannotBeCorrectedError, match=r"has 1\.000 pcs accepted"):
            await _reject(world, 2, 2.0, _REDELIVER)

    async def test_a_made_line_is_refused(self) -> None:
        world = _World([_row(10.0)], status=OrderItemStatus.DELIVERED, made=True)

        with pytest.raises(DeliveryCannotBeCorrectedError, match="MADE line"):
            await _reject(world, 1, 1.0, _LOST)

    async def test_a_miscount_without_a_reason_is_refused(self) -> None:
        world = _delivered()

        with pytest.raises(DeliveryRejectionInvalidError, match="needs a reason"):
            await world.use_case.execute(RECEIVER, 1, 1, 1, 1.0, "  ")
        assert world.uow.committed is False
