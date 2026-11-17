"""
The piece balance of a lot's positions: arrived = good + scrap + rework +
lost + WIP, from the completions of each position's orders, its supplier's
deliveries and losses, and for position 1 the raw material that arrived; a
position that booked more than reached it shows a negative difference.
"""

from datetime import UTC
from datetime import date
from datetime import datetime

from src.modules.fulfillment.domain.entities.production_order_completion import (
    ProductionOrderCompletion,
)
from src.modules.fulfillment.domain.services.position_reconciliation import balance_positions
from tests.unit.production_order._helpers import make_order
from tests.unit.production_order._helpers import make_position


def _completion(accepted: float, *, scrap: float = 0.0, rework: float = 0.0):
    return ProductionOrderCompletion(
        id=0,
        production_order_id=1,
        quantity=accepted + scrap + rework,
        quantity_accepted=accepted,
        quantity_rejected=scrap + rework,
        quantity_scrap=scrap,
        quantity_rework=rework,
        completion_date=date(2026, 10, 20),
        note=None,
        operator_id=1,
        recorded_by_id=1,
        created=datetime(2026, 10, 20, tzinfo=UTC),
    )


def test_every_piece_of_each_position_is_accounted_for() -> None:
    first = make_position(1, sequence=1, quantity=10.0, quantity_completed=7.0)
    second = make_position(2, sequence=2, quantity=10.0, quantity_completed=4.0)
    order_one = make_order(1, lot_position_id=1)
    order_one.completions = [_completion(7.0, scrap=1.0)]
    order_two = make_order(2, lot_position_id=2)
    order_two.completions = [_completion(4.0, rework=1.0)]

    first_balance, second_balance = balance_positions(
        [second, first],
        10.0,
        {1: [order_one], 2: [order_two]},
        {},
        raw_material_arrived=9.0,
    )

    # Position 1 got 9 of its 10 pieces of material.
    assert (first_balance.arrived, first_balance.good, first_balance.scrap) == (9.0, 7.0, 1.0)
    assert (first_balance.wip, first_balance.difference, first_balance.produced) == (1.0, 0.0, 8.0)
    # Position 2 got position 1's 7 good pieces.
    assert (second_balance.arrived, second_balance.good, second_balance.rework) == (7.0, 4.0, 1.0)
    assert (second_balance.wip, second_balance.difference) == (2.0, 0.0)


def test_a_supplier_s_lost_pieces_and_an_over_booking_show_up() -> None:
    external = make_position(1, sequence=1, quantity=5.0, quantity_completed=3.0)
    external.order_item_quantity_delivered = 3.0
    over = make_position(2, sequence=2, quantity=5.0, quantity_completed=3.0)
    order = make_order(2, lot_position_id=2)
    order.completions = [_completion(3.0, scrap=1.0)]

    external_balance, over_balance = balance_positions(
        [external, over], 5.0, {2: [order]}, {1: 2.0}, raw_material_arrived=None
    )

    assert (external_balance.good, external_balance.lost, external_balance.wip) == (3.0, 2.0, 0.0)
    assert external_balance.difference == 0.0
    # Position 2 booked 4 pieces of the 3 that reached it.
    assert (over_balance.arrived, over_balance.wip, over_balance.difference) == (3.0, 0.0, -1.0)
