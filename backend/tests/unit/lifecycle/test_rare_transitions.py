"""
Transitions the seeded lifecycle exploration reaches only now and then,
driven here on purpose through the real use cases (model_world.py), so a
change that makes one impossible fails here and not only as a missing row
when the transition table is regenerated. The request each scenario is
about records its status changes like the exploration does, and
test_state_transitions.py runs SCENARIOS, so the generated table lists
these transitions too.
"""

from collections.abc import Callable

from tests.unit.lifecycle._transitions import record as record_transitions
from tests.unit.lifecycle.model_world import ORDER_ID
from tests.unit.lifecycle.model_world import Outcome
from tests.unit.lifecycle.model_world import Spec
from tests.unit.lifecycle.model_world import World

MADE_LINE = 2
SOURCE_LINE = 2
# With a SOURCE line in the spec, the line an external assignment creates
# comes after it.
MADE_LINE_AFTER_SOURCE = 3


def _statuses(world: World, *keys: str) -> dict[str, str]:
    table = world.status_table()
    return {key: table[key] for key in keys}


def _act(world: World, subject: str, call: Callable[[], Outcome]) -> Outcome:
    """Runs the request under test on `subject` (a status table key) and
    records its status changes for the transition table."""
    before = world.status_table()
    world.last_request = ""
    outcome = call()
    if outcome.refused is None:
        record_transitions(before, world.status_table(), subject, world.last_request)
    return outcome


def test_a_piece_lost_at_receipt_on_a_made_line_reopens_the_newest_made_demand() -> None:
    """A lot of 2 covers two made demands of one piece each. One piece is
    bought in on a MADE line and lost at receipt by deliver-all, with no
    replacement: the lot shrinks to 1, the cut comes off the newest demand,
    which loses all of its coverage and is open again, while the older one
    keeps its piece on a lot that is back in planning."""
    world = World(Spec(steps=1, lot_quantity=2.0, made_demands=(1.0, 1.0), bought_lines=(1.0,)))
    position_id = world.lot.positions[0].id
    assert world.assign_external(position_id, 1.0).refused is None
    assert world.mark_ordered(MADE_LINE).refused is None
    assert _statuses(world, "made_demand#101", "made_demand#102") == {
        "made_demand#101": "ordered",
        "made_demand#102": "ordered",
    }

    outcome = _act(world, f"order#{ORDER_ID}", lambda: world.deliver_all(losing=MADE_LINE))

    assert outcome.refused is None, outcome.refused
    assert _statuses(world, "lot#1", "line#2", "made_demand#101", "made_demand#102") == {
        "lot#1": "draft",
        "line#2": "delivered",
        "made_demand#101": "allocated",
        "made_demand#102": "open",
    }
    assert world.settle() == []


def test_closing_a_source_line_short_reopens_the_demand_the_arrived_pieces_missed() -> None:
    """Two raw material demands share a SOURCE line of 2: the lot's own (901)
    and the neighbour lot's (902), one metre each allocated, both short of
    their quantity. One metre arrives and fills the older demand first;
    closing the line short fits the allocations into that metre, so the
    newer demand's allocation goes and it is open again."""
    world = World(
        Spec(
            steps=1,
            lot_quantity=2.0,
            made_demands=(1.0,),
            bought_lines=(1.0,),
            bought_demands=(),
            source_line=2.0,
            neighbour_lot=2.0,
        )
    )
    assert world.allocate_source(901, SOURCE_LINE, 1.0).refused is None
    assert world.allocate_source(902, SOURCE_LINE, 1.0).refused is None
    assert world.mark_ordered(SOURCE_LINE).refused is None
    assert world.deliver(SOURCE_LINE, 1.0).refused is None
    assert _statuses(world, "source_demand#901", "source_demand#902") == {
        "source_demand#901": "allocated",
        "source_demand#902": "allocated",
    }

    outcome = _act(world, f"line#{SOURCE_LINE}", lambda: world.close_short(SOURCE_LINE))

    assert outcome.refused is None, outcome.refused
    assert _statuses(world, "line#2", "source_demand#901", "source_demand#902") == {
        "line#2": "delivered",
        "source_demand#901": "allocated",
        "source_demand#902": "open",
    }
    assert world.settle() == []


def test_losing_a_one_piece_lots_only_piece_at_receipt_scraps_the_partially_planned_lot() -> None:
    """A lot of one piece has two positions; only the first is assigned to
    a supplier, so the lot is partially planned. The supplier's only piece
    is lost at receipt on the MADE line without a replacement: the lot
    shrinks to nothing and is scrapped, and its raw material demand is
    canceled with it."""
    world = World(Spec(steps=2, lot_quantity=1.0, made_demands=(1.0,), bought_lines=(1.0,)))
    position_id = world.lot.positions[0].id
    assert world.assign_external(position_id, 1.0).refused is None
    assert world.mark_ordered(MADE_LINE).refused is None
    assert _statuses(world, "lot#1") == {"lot#1": "partially_planned"}

    outcome = _act(
        world,
        f"line#{MADE_LINE}",
        lambda: world.deliver(MADE_LINE, 0.0, rejected=1.0, outcome="lost"),
    )

    assert outcome.refused is None, outcome.refused
    assert _statuses(world, "lot#1", "line#2", "source_demand#901") == {
        "lot#1": "scrapped",
        "line#2": "delivered",
        "source_demand#901": "canceled",
    }
    assert world.settle() == []


def test_scrapping_a_lot_by_deliver_all_cancels_its_allocated_raw_material_demand() -> None:
    """The lot's raw material demand is allocated to a SOURCE line that is
    not ordered yet, so it stays allocated. Deliver-all loses the only piece
    of the one-piece lot on its MADE line: the lot is scrapped and its raw
    material demand goes from allocated straight to canceled, while the
    pending SOURCE line is left alone."""
    world = World(
        Spec(
            steps=2,
            lot_quantity=1.0,
            made_demands=(1.0,),
            bought_lines=(1.0,),
            bought_demands=(),
            source_line=1.0,
        )
    )
    assert world.allocate_source(901, SOURCE_LINE, 1.0).refused is None
    position_id = world.lot.positions[0].id
    assert world.assign_external(position_id, 1.0).refused is None
    assert world.mark_ordered(MADE_LINE_AFTER_SOURCE).refused is None
    assert _statuses(world, "lot#1", "source_demand#901") == {
        "lot#1": "partially_planned",
        "source_demand#901": "allocated",
    }

    outcome = _act(
        world, f"order#{ORDER_ID}", lambda: world.deliver_all(losing=MADE_LINE_AFTER_SOURCE)
    )

    assert outcome.refused is None, outcome.refused
    assert _statuses(world, "lot#1", "line#2", "line#3", "source_demand#901") == {
        "lot#1": "scrapped",
        "line#2": "pending",
        "line#3": "delivered",
        "source_demand#901": "canceled",
    }
    assert world.settle() == []


def test_an_award_and_its_void_move_the_quote_request() -> None:
    """Awarding every line of a sent request derives it awarded. Canceling
    the MADE line the award placed voids that award and the request waits
    for an award again."""
    world = World(Spec(steps=1, made_demands=(6.0,), bought_lines=(), bought_demands=()))
    position_id = world.lot.positions[0].id
    request = world.quote_request(source_share=2.0, position_id=position_id)
    key = f"quote_request#{request.id}"

    assert _act(world, key, lambda: world.award(request.id)).refused is None
    assert _statuses(world, key) == {key: "awarded"}

    [made] = world.made_lines()
    assert _act(world, f"line#{made.id}", lambda: world.cancel_line(made.id)).refused is None
    assert _statuses(world, key) == {key: "sent"}
    assert world.settle() == []


def test_reopening_a_line_closed_short_puts_it_back_to_partially_delivered() -> None:
    """A line of 4 receives 2 and is closed short, which makes it delivered.
    Reopening it brings its quantity back, so it is partially delivered."""
    world = World(Spec(steps=1, bought_lines=(4.0,), bought_demands=()))
    assert world.mark_ordered(1).refused is None
    assert world.deliver(1, 2.0).refused is None
    assert world.close_short(1).refused is None
    assert _statuses(world, "line#1") == {"line#1": "delivered"}

    assert _act(world, "line#1", lambda: world.reopen(1)).refused is None

    assert _statuses(world, "line#1") == {"line#1": "partially_delivered"}
    assert world.settle() == []


def test_a_lot_created_for_an_open_made_demand_allocates_it() -> None:
    """A made demand no lot covers is open. A lot created for it covers its
    quantity, so the demand is allocated."""
    world = World(Spec(steps=1, bought_lines=(), bought_demands=()))
    world.add_made_demand(150, 2.0)
    assert _statuses(world, "made_demand#150") == {"made_demand#150": "open"}

    outcome = _act(world, "made_demand#150", lambda: world.create_lot_for_demand(150, 2.0))

    assert outcome.refused is None, outcome.refused
    assert _statuses(world, "made_demand#150") == {"made_demand#150": "allocated"}
    assert world.settle() == []


def _first_row(world: World, line_id: int) -> int:
    ((row_id, _),) = world.open_rows(line_id)
    return row_id


def test_pieces_lost_after_receipt_reopen_the_bought_demands_they_filled() -> None:
    """A bought line of 4 fills two demands of 2, both fulfilled. A piece
    found damaged after receipt and lost takes the line's allocations down
    to 3, so the newer demand keeps one piece and is merely allocated; a
    second lost piece takes its last one, and it is open again."""
    world = World(Spec(steps=1, bought_lines=(4.0,), bought_demands=(2.0, 2.0)))
    assert world.allocate(1, 1, 2.0).refused is None
    assert world.allocate(2, 1, 2.0).refused is None
    assert world.mark_ordered(1).refused is None
    assert world.deliver(1, 4.0).refused is None
    assert _statuses(world, "bought_demand#1", "bought_demand#2") == {
        "bought_demand#1": "fulfilled",
        "bought_demand#2": "fulfilled",
    }
    row_id = _first_row(world, 1)

    first = _act(world, "line#1", lambda: world.correct(1, row_id, 1.0, rejected_as="lost"))
    assert first.refused is None, first.refused
    assert _statuses(world, "line#1", "bought_demand#1", "bought_demand#2") == {
        "line#1": "delivered",
        "bought_demand#1": "fulfilled",
        "bought_demand#2": "allocated",
    }

    second = _act(world, "line#1", lambda: world.correct(1, row_id, 1.0, rejected_as="lost"))
    assert second.refused is None, second.refused
    assert _statuses(world, "bought_demand#1", "bought_demand#2") == {
        "bought_demand#1": "fulfilled",
        "bought_demand#2": "open",
    }
    assert world.settle() == []


def test_losing_a_whole_delivery_after_receipt_opens_its_bought_demands() -> None:
    """A bought line of 2 fulfils one demand of 2. Both pieces are found
    damaged after receipt and lost: the line still counts as delivered, its
    allocation goes, and the demand is open again."""
    world = World(Spec(steps=1, bought_lines=(2.0,), bought_demands=(2.0,)))
    assert world.allocate(1, 1, 2.0).refused is None
    assert world.mark_ordered(1).refused is None
    assert world.deliver(1, 2.0).refused is None
    row_id = _first_row(world, 1)

    outcome = _act(world, "line#1", lambda: world.correct(1, row_id, 2.0, rejected_as="lost"))

    assert outcome.refused is None, outcome.refused
    assert _statuses(world, "line#1", "bought_demand#1") == {
        "line#1": "delivered",
        "bought_demand#1": "open",
    }
    assert world.settle() == []


def _source_world() -> World:
    """A SOURCE line of 4 that fills the raw material demands of the lot
    (901) and of the neighbour lot (902), two metres each."""
    world = World(
        Spec(
            steps=1,
            lot_quantity=2.0,
            made_demands=(1.0,),
            bought_lines=(1.0,),
            bought_demands=(),
            source_line=4.0,
            neighbour_lot=2.0,
        )
    )
    assert world.allocate_source(901, SOURCE_LINE, 2.0).refused is None
    assert world.allocate_source(902, SOURCE_LINE, 2.0).refused is None
    assert world.mark_ordered(SOURCE_LINE).refused is None
    assert world.deliver(SOURCE_LINE, 4.0).refused is None
    assert _statuses(world, "source_demand#901", "source_demand#902") == {
        "source_demand#901": "fulfilled",
        "source_demand#902": "fulfilled",
    }
    return world


def test_material_lost_after_receipt_reopens_the_raw_material_demand_it_filled() -> None:
    """A metre of the SOURCE line is found damaged after receipt and lost:
    the newer raw material demand keeps one metre and is allocated; a
    second lost metre takes its last one, and it is open again."""
    world = _source_world()
    row_id = _first_row(world, SOURCE_LINE)
    line = f"line#{SOURCE_LINE}"

    first = _act(world, line, lambda: world.correct(SOURCE_LINE, row_id, 1.0, rejected_as="lost"))
    assert first.refused is None, first.refused
    assert _statuses(world, "source_demand#901", "source_demand#902") == {
        "source_demand#901": "fulfilled",
        "source_demand#902": "allocated",
    }

    second = _act(world, line, lambda: world.correct(SOURCE_LINE, row_id, 1.0, rejected_as="lost"))
    assert second.refused is None, second.refused
    assert _statuses(world, "source_demand#901", "source_demand#902") == {
        "source_demand#901": "fulfilled",
        "source_demand#902": "open",
    }
    assert world.settle() == []


def test_losing_all_material_after_receipt_opens_the_raw_material_demands() -> None:
    """All four metres of the SOURCE line are found damaged after receipt
    and lost, so both raw material demands are open again."""
    world = _source_world()
    row_id = _first_row(world, SOURCE_LINE)

    outcome = _act(
        world,
        f"line#{SOURCE_LINE}",
        lambda: world.correct(SOURCE_LINE, row_id, 4.0, rejected_as="lost"),
    )

    assert outcome.refused is None, outcome.refused
    assert _statuses(world, "source_demand#901", "source_demand#902") == {
        "source_demand#901": "open",
        "source_demand#902": "open",
    }
    assert world.settle() == []


SCENARIOS: tuple[Callable[[], None], ...] = (
    test_a_piece_lost_at_receipt_on_a_made_line_reopens_the_newest_made_demand,
    test_closing_a_source_line_short_reopens_the_demand_the_arrived_pieces_missed,
    test_losing_a_one_piece_lots_only_piece_at_receipt_scraps_the_partially_planned_lot,
    test_scrapping_a_lot_by_deliver_all_cancels_its_allocated_raw_material_demand,
    test_an_award_and_its_void_move_the_quote_request,
    test_reopening_a_line_closed_short_puts_it_back_to_partially_delivered,
    test_a_lot_created_for_an_open_made_demand_allocates_it,
    test_pieces_lost_after_receipt_reopen_the_bought_demands_they_filled,
    test_losing_a_whole_delivery_after_receipt_opens_its_bought_demands,
    test_material_lost_after_receipt_reopens_the_raw_material_demand_it_filled,
    test_losing_all_material_after_receipt_opens_the_raw_material_demands,
)
