"""
Scenarios over multi-position lots and multi-line orders, run through the
real use cases and one lifecycle reconciler per request with every
aggregate enabled (model_world.py). After every step the stored status of
every aggregate in the world is compared with the scenario's expected table
as a whole, so a status the step should not have touched is checked too,
and a reconciler run over everything must change nothing.
"""

import pytest

from tests.unit.lifecycle.model_world import Outcome
from tests.unit.lifecycle.model_world import Spec
from tests.unit.lifecycle.model_world import World


class Scenario:
    """A world and the status table it must show after each step."""

    def __init__(self, spec: Spec) -> None:
        self.world = World(spec)
        self.expected = self.world.status_table()

    def step(self, outcome: Outcome, **changes: str) -> None:
        """Asserts the step went through and every aggregate now reads its
        expected status: the previous table with `changes` applied, keys
        written `kind_id` (lot_1, position_2, line_3, bought_demand_1)."""
        assert outcome.refused is None, outcome.refused
        self.check(**changes)

    def refused(self, outcome: Outcome) -> None:
        """Asserts the step was refused and nothing changed."""
        assert outcome.refused is not None
        self.check()

    def check(self, **changes: str) -> None:
        for key, status in changes.items():
            kind, _, row_id = key.rpartition("_")
            self.expected[f"{kind}#{row_id}"] = status
        assert self.world.status_table() == self.expected
        assert self.world.settle() == []

    def position_ids(self) -> list[int]:
        return [p.id for p in self.world.lot.positions]

    def production_order_on(self, position_id: int) -> int:
        live = [o.id for o in self.world.production_orders() if o.lot_position_id == position_id]
        return live[-1]


def test_a_scrap_at_position_two_shrinks_the_inspection_and_the_lot_still_completes() -> None:
    """A lot of 10 for two made demands (4 and 6): an external first step,
    an internal second one and an inspection. Two pieces scrapped at the
    second step shrink the lot, the later positions and the inspection order
    to 8 and are cut from the newer demand's allocation; the lot completes
    at 8, the older demand is covered and the newer one is left short."""
    s = Scenario(
        Spec(
            steps=3,
            inspection_last=True,
            lot_quantity=10.0,
            made_demands=(4.0, 6.0),
            bought_lines=(),
            bought_demands=(),
        )
    )
    w = s.world
    first, second, inspection = s.position_ids()
    qa = s.production_order_on(inspection)
    assert s.expected == {
        "lot#1": "partially_planned",
        "position#1": "pending/unassigned",
        "position#2": "pending/unassigned",
        "position#3": "ordered_or_queued/internal",
        f"production_order#{qa}": "queued",
        "order#1": "draft",
        "order#2": "draft",
        "made_demand#101": "ordered",
        "made_demand#102": "ordered",
        "source_demand#901": "open",
    }

    s.step(w.assign_external(first), position_1="pending/external", line_1="pending")
    planned = w.assign_internal(second, 10.0)
    po = s.production_order_on(second)
    s.step(
        planned,
        position_2="ordered_or_queued/internal",
        **{f"production_order_{po}": "queued"},
    )
    s.step(
        w.submit_order(),
        lot_1="planned",
        position_1="ordered_or_queued/external",
        order_1="ordered",
        line_1="ordered",
    )
    s.step(
        w.deliver(1, None),
        lot_1="in_progress",
        position_1="completed/external",
        order_1="delivered",
        line_1="delivered",
    )
    s.step(
        w.start(po), position_2="in_progress/internal", **{f"production_order_{po}": "in_progress"}
    )
    s.step(w.complete(po, 4.0), position_2="partially_completed/internal")

    s.step(w.scrap(po, 2.0), made_demand_102="allocated")
    lot = w.lot
    assert lot.quantity == 8.0
    assert [(p.quantity, p.quantity_completed) for p in lot.positions] == [
        (10.0, 10.0),
        (8.0, 4.0),
        (8.0, 0.0),
    ]
    assert w.floor.orders.orders[qa].quantity == 8.0
    shares = sorted((a.demand_item_id, a.quantity) for a in w.floor.made_allocations._allocations)
    assert shares == [(101, pytest.approx(4.0)), (102, pytest.approx(4.0))]

    s.step(
        w.complete(po, 4.0),
        position_2="completed/internal",
        **{f"production_order_{po}": "completed"},
    )
    s.step(
        w.start(qa), position_3="in_progress/internal", **{f"production_order_{qa}": "in_progress"}
    )
    s.step(
        w.complete(qa, 8.0),
        lot_1="completed",
        position_3="completed/internal",
        made_demand_101="fulfilled",
        **{f"production_order_{qa}": "completed"},
    )


def test_an_order_of_a_bought_a_canceled_and_a_made_line_is_delivered() -> None:
    """One order with a bought line of 4 covering a demand of 4, a bought
    line of 2 that is canceled, and the MADE line of a one-step lot of 3.
    The bought line arrives in two fractional deliveries, which fulfil the
    demand only once both are in; the canceled line does not keep the order
    from DELIVERED."""
    s = Scenario(Spec(steps=1, lot_quantity=3.0, bought_lines=(4.0, 2.0), bought_demands=(4.0,)))
    w = s.world
    [only] = s.position_ids()
    s.step(w.assign_external(only), position_1="pending/external", line_3="pending")
    s.step(w.allocate(1, 1, 4.0), bought_demand_1="allocated")
    s.step(
        w.submit_order(),
        lot_1="planned",
        position_1="ordered_or_queued/external",
        order_1="ordered",
        line_1="ordered",
        line_2="ordered",
        line_3="ordered",
        bought_demand_1="ordered",
    )
    s.step(
        w.deliver(1, 1.3),
        order_1="partially_delivered",
        line_1="partially_delivered",
    )
    s.step(w.deliver(1, 2.7), line_1="delivered", bought_demand_1="fulfilled")
    s.step(w.cancel_line(2), line_2="canceled")
    s.step(
        w.deliver(3, None),
        lot_1="completed",
        position_1="completed/external",
        order_1="delivered",
        line_3="delivered",
    )


def test_canceling_an_order_closes_a_received_line_short_and_frees_the_made_position() -> None:
    """An order with a bought line of 4 allocated 3 to a demand, one piece
    received, and the MADE line of a one-step lot. Canceling the order
    closes the bought line at what it received and cuts the allocation to
    it, which leaves the demand partly covered, and cancels the MADE line,
    which leaves the position unassigned."""
    s = Scenario(Spec(steps=1, lot_quantity=3.0, bought_lines=(4.0,), bought_demands=(3.0,)))
    w = s.world
    [only] = s.position_ids()
    s.step(w.assign_external(only), position_1="pending/external", line_2="pending")
    s.step(w.allocate(1, 1, 3.0), bought_demand_1="allocated")
    s.step(
        w.submit_order(),
        lot_1="planned",
        position_1="ordered_or_queued/external",
        order_1="ordered",
        line_1="ordered",
        line_2="ordered",
        bought_demand_1="ordered",
    )
    s.step(
        w.deliver(1, 1.0),
        order_1="partially_delivered",
        line_1="partially_delivered",
    )

    s.step(
        w.cancel_order(),
        lot_1="draft",
        position_1="pending/unassigned",
        order_1="canceled",
        line_1="delivered",
        line_2="canceled",
        bought_demand_1="allocated",
    )
    assert w.lines.items[1].quantity == 1.0
    assert [a.quantity for a in w.bought_allocations.allocations] == [1.0]


def test_a_held_lot_completes_when_its_last_made_line_arrives() -> None:
    """A lot of two steps: the first runs internally to its end, the second
    is bought in. The lot is held, the MADE line arrives in full, and the
    lot completes although it is held."""
    s = Scenario(Spec(steps=2, lot_quantity=4.0, bought_lines=(), bought_demands=()))
    w = s.world
    first, second = s.position_ids()
    planned = w.assign_internal(first, 4.0)
    po = s.production_order_on(first)
    s.step(
        planned,
        lot_1="partially_planned",
        position_1="ordered_or_queued/internal",
        **{f"production_order_{po}": "queued"},
    )
    s.step(w.assign_external(second), position_2="pending/external", line_1="pending")
    s.step(
        w.submit_order(),
        lot_1="planned",
        position_2="ordered_or_queued/external",
        order_1="ordered",
        line_1="ordered",
    )
    s.step(
        w.start(po),
        lot_1="in_progress",
        position_1="in_progress/internal",
        **{f"production_order_{po}": "in_progress"},
    )
    s.step(
        w.complete(po, 4.0),
        position_1="completed/internal",
        **{f"production_order_{po}": "completed"},
    )
    s.step(w.hold(1), lot_1="on_hold")

    s.step(
        w.deliver(1, None),
        lot_1="completed",
        position_2="completed/external",
        order_1="delivered",
        line_1="delivered",
    )
    assert w.lot.held_at is not None


def test_force_completing_a_lot_closes_its_made_line_short_and_recomputes_its_demands() -> None:
    """A one-step lot of 6 for made demands of 2 and 4, bought in on a MADE
    line that received 3. The first 3 pieces fill the older demand, which
    is fulfilled. Force-complete closes the line at 3, completes the lot at
    3 and fits the allocations to the 3 pieces from the end of the fill, so
    the newer demand keeps the one piece that reached it."""
    s = Scenario(
        Spec(steps=1, lot_quantity=6.0, made_demands=(2.0, 4.0), bought_lines=(), bought_demands=())
    )
    w = s.world
    [only] = s.position_ids()
    s.step(w.assign_external(only), position_1="pending/external", line_1="pending")
    s.step(
        w.submit_order(),
        lot_1="planned",
        position_1="ordered_or_queued/external",
        order_1="ordered",
        line_1="ordered",
        made_demand_101="ordered",
        made_demand_102="ordered",
    )
    s.step(
        w.deliver(1, 3.0),
        lot_1="in_progress",
        position_1="partially_completed/external",
        order_1="partially_delivered",
        line_1="partially_delivered",
        made_demand_101="fulfilled",
    )

    s.step(
        w.force_complete(1),
        lot_1="completed",
        position_1="completed/external",
        order_1="delivered",
        line_1="delivered",
        made_demand_102="allocated",
        # The lot ends, so its raw material demand that nothing ordered is
        # settled with it.
        source_demand_901="canceled",
    )
    line = w.lines._items[1]
    assert (line.quantity, line.quantity_delivered) == (3.0, 3.0)
    assert w.lot.quantity == 3.0
    shares = sorted((a.demand_item_id, a.quantity) for a in w.floor.made_allocations._allocations)
    assert shares == [(101, pytest.approx(2.0)), (102, pytest.approx(1.0))]


def test_scrapping_every_piece_scraps_the_lot_and_ends_its_work_and_demands() -> None:
    """A lot of 4 for a made demand of 4, two internal steps. Scrapping all
    four pieces at the first step scraps the lot, cancels the second step's
    order and the raw material demand, and leaves the made demand without
    cover. The first step's order processed its whole quantity, so it ends
    completed rather than canceled. The positions are of quantity 0; the
    second, with only a canceled order, reads pending and unassigned."""
    s = Scenario(
        Spec(steps=2, lot_quantity=4.0, made_demands=(4.0,), bought_lines=(), bought_demands=())
    )
    w = s.world
    first, second = s.position_ids()
    planned = w.assign_internal(first, 4.0)
    running = s.production_order_on(first)
    s.step(
        planned,
        lot_1="partially_planned",
        position_1="ordered_or_queued/internal",
        made_demand_101="ordered",
        **{f"production_order_{running}": "queued"},
    )
    planned = w.assign_internal(second, 4.0)
    waiting = s.production_order_on(second)
    s.step(
        planned,
        lot_1="planned",
        position_2="ordered_or_queued/internal",
        **{f"production_order_{waiting}": "queued"},
    )
    s.step(
        w.start(running),
        lot_1="in_progress",
        position_1="in_progress/internal",
        **{f"production_order_{running}": "in_progress"},
    )

    s.step(
        w.scrap(running, 4.0),
        lot_1="scrapped",
        position_1="pending/internal",
        position_2="pending/unassigned",
        made_demand_101="open",
        source_demand_901="canceled",
        **{f"production_order_{running}": "completed", f"production_order_{waiting}": "canceled"},
    )
    assert w.lot.quantity == 0.0


def test_a_partly_canceled_internal_position_is_topped_up_and_finished() -> None:
    """A one-step lot of 6 planned as one order, which makes 2 pieces and
    is canceled. The position keeps its 2 pieces, takes a new order for the
    4 it still lacks, and completes with it."""
    s = Scenario(Spec(steps=1, lot_quantity=6.0, bought_lines=(), bought_demands=()))
    w = s.world
    [only] = s.position_ids()
    planned = w.assign_internal(only, 6.0)
    first = s.production_order_on(only)
    s.step(
        planned,
        lot_1="planned",
        position_1="ordered_or_queued/internal",
        **{f"production_order_{first}": "queued"},
    )
    s.step(
        w.start(first),
        lot_1="in_progress",
        position_1="in_progress/internal",
        **{f"production_order_{first}": "in_progress"},
    )
    s.step(w.complete(first, 2.0), position_1="partially_completed/internal")
    s.step(w.cancel_production_order(first), **{f"production_order_{first}": "canceled"})
    assert w.lot.positions[0].quantity_completed == 2.0

    topped_up = w.assign_internal(only, 4.0)
    second = s.production_order_on(only)
    assert second != first
    s.step(topped_up, **{f"production_order_{second}": "queued"})
    s.step(w.start(second), **{f"production_order_{second}": "in_progress"})
    s.step(
        w.complete(second, 4.0),
        lot_1="completed",
        position_1="completed/internal",
        **{f"production_order_{second}": "completed"},
    )


def test_a_correction_reopens_a_delivered_line_and_its_order() -> None:
    """Two bought lines of 2, the first covering a demand of 2. Both arrive
    in full; the demand is fulfilled. A correction on the first line takes a
    piece back and the demand derives back to ordered, since nothing marked
    it fulfilled by hand; one on the second line reopens it too, and the
    order is partially delivered again."""
    s = Scenario(Spec(steps=1, bought_lines=(2.0, 2.0), bought_demands=(2.0,)))
    w = s.world
    s.step(w.allocate(1, 1, 2.0), bought_demand_1="allocated")
    s.step(
        w.submit_order(),
        order_1="ordered",
        line_1="ordered",
        line_2="ordered",
        bought_demand_1="ordered",
    )
    s.step(
        w.deliver_all(),
        order_1="delivered",
        line_1="delivered",
        line_2="delivered",
        bought_demand_1="fulfilled",
    )

    [(first_row, _)] = w.open_rows(1)
    s.step(
        w.correct(1, first_row, 1.0),
        order_1="partially_delivered",
        line_1="partially_delivered",
        bought_demand_1="ordered",
    )
    [(second_row, _)] = w.open_rows(2)
    s.step(w.correct(2, second_row, 1.0), line_2="partially_delivered")
    assert w.lines.items[2].quantity_delivered == 1.0
