"""
A completion and a scrap record the machine the order was on when they were
booked, so the pieces stay with the machine that made them once a paused
order moves to another one.
"""

from tests.unit.production_lot._floor import Floor


async def test_a_completion_and_a_scrap_record_the_order_s_machine() -> None:
    floor = Floor(positions=1)
    lot = await floor.lot()
    [position] = await floor.positions(lot.id)
    order = await floor.order(position)
    order.machine_id = 7
    await floor.orders.save(order)

    await floor.complete(order.id, 2.0)
    order.machine_id = 8
    await floor.orders.save(order)
    await floor.scrap(order.id, 1.0)

    completions = await floor.orders.get_completions(order.id)
    assert [(c.quantity, c.machine_id) for c in completions] == [(2.0, 7), (1.0, 8)]
