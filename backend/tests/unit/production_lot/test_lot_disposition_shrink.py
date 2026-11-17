"""
A disposition (scrap, inspection reject, pieces lost at receipt) closes the
lot short: the lot and every position from the disposed one on lose the
removed pieces, the live work of those positions is cut back to what they
still need, and the lifecycle reconciler then derives every status. The
pure rules are tested on their own, the flows over the shop floor fakes.
"""

import asyncio

import pytest
from hypothesis import given
from hypothesis import settings
from hypothesis import strategies as st

from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.errors import LotNotScrappableError
from src.modules.fulfillment.domain.errors import LotPositionOverflowError
from src.modules.fulfillment.domain.errors import ScrapQuantityExceedsAvailableError
from src.modules.fulfillment.domain.services.lot_rules import Commitment
from src.modules.fulfillment.domain.services.lot_rules import assert_disposition_keeps_completed
from src.modules.fulfillment.domain.services.lot_rules import plan_commitment_cuts
from src.modules.fulfillment.domain.services.lot_rules import shrink_lot_for_scrap
from src.modules.fulfillment.domain.services.lot_rules import split_quantity_by_largest_remainder
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from tests.unit.lifecycle.fake_world import make
from tests.unit.production_lot._floor import NOW
from tests.unit.production_lot._floor import Floor
from tests.unit.production_lot._helpers import make_source_item_demand


def _lot(quantity: float, positions: list[tuple[float, float]]) -> ProductionLot:
    """A lot whose positions have the given (quantity, completed) pairs."""
    lot = make(ProductionLot, id=1, quantity=quantity, status=LotStatus.IN_PROGRESS)
    lot.positions = [
        make(
            LotPosition,
            id=sequence,
            sequence=sequence,
            kind=LotPositionKind.INTERNAL,
            status=LotPositionStatus.IN_PROGRESS,
            quantity=position_quantity,
            quantity_completed=done,
            lot_id=1,
        )
        for sequence, (position_quantity, done) in enumerate(positions, start=1)
    ]
    return lot


# ── The shrink and the guard ────────────────────────────────────────────


def test_the_shrink_lowers_the_disposed_and_later_positions_only() -> None:
    lot = _lot(10.0, [(10.0, 9.0), (10.0, 4.0), (10.0, 0.0)])

    touched = shrink_lot_for_scrap(lot, lot.positions[1], 2.0)

    assert lot.quantity == 8.0
    assert [p.id for p in touched] == [2, 3]
    assert [(p.quantity, p.quantity_completed) for p in lot.positions] == [
        (10.0, 9.0),
        (8.0, 4.0),
        (8.0, 0.0),
    ]


def test_the_guard_refuses_a_removal_below_a_completed_count_and_takes_one_less() -> None:
    lot = _lot(10.0, [(10.0, 10.0), (10.0, 6.0), (10.0, 6.0)])

    with pytest.raises(LotNotScrappableError):
        assert_disposition_keeps_completed(lot, lot.positions[1], 5.0)
    assert_disposition_keeps_completed(lot, lot.positions[1], 4.0)


def test_the_guard_counts_the_pieces_the_operation_accepts_itself() -> None:
    lot = _lot(10.0, [(10.0, 10.0), (10.0, 0.0)])

    with pytest.raises(LotNotScrappableError):
        assert_disposition_keeps_completed(lot, lot.positions[1], 2.0, accepted_now=9.0)
    assert_disposition_keeps_completed(lot, lot.positions[1], 2.0, accepted_now=8.0)


# ── Cutting the live work ───────────────────────────────────────────────


def test_a_queued_order_after_the_disposition_is_cut_to_what_its_position_needs() -> None:
    position = make(LotPosition, id=3, sequence=3, quantity=8.0, quantity_completed=0.0)

    [cut] = plan_commitment_cuts(
        position, [Commitment(id=30, is_line=False, quantity=10.0, done=0.0, queued=True)]
    )

    assert (cut.commitment.id, cut.quantity, cut.cancels) == (30, 8.0, False)


def test_queued_orders_go_first_and_no_order_drops_below_what_it_processed() -> None:
    position = make(LotPosition, id=3, sequence=3, quantity=1.0, quantity_completed=0.0)
    running = Commitment(id=30, is_line=False, quantity=5.0, done=3.0)
    queued = Commitment(id=31, is_line=False, quantity=5.0, done=0.0, queued=True)

    cuts = plan_commitment_cuts(position, [running, queued])

    assert [(c.commitment.id, c.quantity, c.cancels) for c in cuts] == [
        (31, 0.0, True),
        (30, 4.0, False),
    ]


def test_a_pending_line_is_cut_and_an_ordered_line_is_kept() -> None:
    position = make(LotPosition, id=3, sequence=3, quantity=6.0, quantity_completed=0.0)
    pending = Commitment(id=40, is_line=True, quantity=10.0, done=0.0)
    ordered = Commitment(id=41, is_line=True, quantity=10.0, done=0.0, cuttable=False)

    assert [(c.commitment.id, c.quantity) for c in plan_commitment_cuts(position, [pending])] == [
        (40, 6.0)
    ]
    assert plan_commitment_cuts(position, [ordered]) == []


def test_a_fully_removed_position_cancels_its_untouched_work() -> None:
    position = make(LotPosition, id=3, sequence=3, quantity=0.0, quantity_completed=0.0)

    [cut] = plan_commitment_cuts(
        position, [Commitment(id=30, is_line=False, quantity=10.0, done=0.0, queued=True)]
    )

    assert cut.cancels


# ── Splitting the removed pieces across demand allocations ─────────────


def test_a_finished_demand_never_gives_up_more_than_its_exact_share() -> None:
    # The naive largest-remainder split hands the extra rounding unit to the
    # first share, which would lower the finished demand below its exact
    # proportional allocation.
    assert split_quantity_by_largest_remainder(1.0, [1.0, 1.0, 1.0]) == [
        0.333334,
        0.333333,
        0.333333,
    ]

    shares = split_quantity_by_largest_remainder(1.0, [1.0, 1.0, 1.0], [True, False, False])

    assert shares == [0.333333, 0.333334, 0.333333]
    assert shares[0] <= 1.0 / 3.0
    assert round(sum(shares), 6) == 1.0


def test_finished_demands_absorb_the_remainder_only_when_no_live_one_can() -> None:
    shares = split_quantity_by_largest_remainder(1.0, [1.0, 1.0, 1.0], [True, True, True])

    assert round(sum(shares), 6) == 1.0
    assert split_quantity_by_largest_remainder(3.0, [2.0, 1.0], [True, False]) == [2.0, 1.0]


def test_split_gives_nothing_without_a_total_or_weights() -> None:
    assert split_quantity_by_largest_remainder(5.0, []) == []
    assert split_quantity_by_largest_remainder(0.0, [1.0, 2.0]) == [0.0, 0.0]
    assert split_quantity_by_largest_remainder(-1.0, [1.0]) == [0.0]
    assert split_quantity_by_largest_remainder(1.0, [0.0, 0.0]) == [0.0, 0.0]


def test_split_clamps_the_total_to_the_weight_sum() -> None:
    assert split_quantity_by_largest_remainder(10.0, [1.0, 2.0]) == [1.0, 2.0]


def test_split_hands_the_remainder_to_finished_demands_once_live_ones_are_full() -> None:
    # Each exact share is two thirds of a unit, so all floor to zero; the
    # live first share takes one unit up to its weight, and the remaining
    # unit goes to the finished share with the largest remainder.
    shares = split_quantity_by_largest_remainder(2e-6, [1e-6, 1e-6, 1e-6], [False, True, True])
    assert shares == [1e-6, 1e-6, 0.0]


def test_split_never_lifts_a_share_above_its_weight_to_close_the_sum() -> None:
    shares = split_quantity_by_largest_remainder(
        1.000002, [0.5000005, 0.5000005, 1e-6], [True, True, False]
    )
    assert shares == [0.5, 0.5, 1e-6]


# ── Flows ───────────────────────────────────────────────────────────────


async def test_a_scrap_at_position_two_shrinks_the_qa_order_and_everything_completes() -> None:
    floor = Floor(positions=3)
    lot = await floor.lot(10.0)
    first, second, third = await floor.positions(lot.id)
    await floor.order(first, processed=10.0)
    running = await floor.order(second)
    waiting = await floor.order(third, status=ProductionOrderStatus.QUEUED)
    await floor.settle(lot.id)

    await floor.scrap(running.id, 2.0)

    lot = await floor.reload(lot.id)
    assert lot.quantity == 8.0
    assert [(p.quantity, p.quantity_completed) for p in lot.positions] == [
        (10.0, 10.0),
        (8.0, 0.0),
        (8.0, 0.0),
    ]
    assert (running.quantity, waiting.quantity) == (10.0, 8.0)

    await floor.complete(running.id, 8.0)
    await floor.start(waiting)
    await floor.complete(waiting.id, 8.0)

    lot = await floor.reload(lot.id)
    assert [p.status for p in lot.positions] == ["completed", "completed", "completed"]
    assert lot.status == "completed"
    assert waiting.status == ProductionOrderStatus.COMPLETED.value


async def test_a_full_scrap_cancels_the_live_work_and_the_input_demand() -> None:
    floor = Floor(positions=2)
    lot = await floor.lot(4.0)
    first, second = await floor.positions(lot.id)
    running = await floor.order(first)
    waiting = await floor.order(second, status=ProductionOrderStatus.QUEUED)
    await floor.source_demands.save(make_source_item_demand(id=lot.input_demand_id, lot_id=lot.id))
    await floor.settle(lot.id)

    await floor.scrap(running.id, 4.0)

    lot = await floor.reload(lot.id)
    assert (lot.quantity, lot.status) == (0.0, "scrapped")
    assert waiting.status == ProductionOrderStatus.CANCELED.value
    assert waiting.canceled_at is not None
    stored = await floor.source_demands.get_by_id(lot.input_demand_id)
    assert stored is not None
    assert (stored.canceled_at is not None, stored.status) == (True, "canceled")


async def test_a_position_processes_no_more_than_its_predecessor_made_after_a_scrap() -> None:
    """Position 1 made 8. Position 2 completes 5 and scraps 2, so it has
    processed 7 of the 8 and only 1 is left for it: completing 2 more is
    refused, completing 1 is not. Position 1 keeps its quantity after the
    downstream scrap, so it can still scrap pieces of its own afterwards."""
    floor = Floor(positions=2)
    lot = await floor.lot(10.0)
    first, second = await floor.positions(lot.id)
    upstream = await floor.order(first, processed=8.0)
    downstream = await floor.order(second)
    await floor.settle(lot.id)
    await floor.complete(downstream.id, 5.0)
    await floor.scrap(downstream.id, 2.0)

    with pytest.raises(LotPositionOverflowError):
        await floor.complete(downstream.id, 2.0)
    await floor.complete(downstream.id, 1.0)
    lot = await floor.reload(lot.id)
    assert [(p.quantity, p.quantity_completed) for p in lot.positions] == [(10.0, 8.0), (8.0, 6.0)]

    await floor.scrap(upstream.id, 1.0)
    lot = await floor.reload(lot.id)
    assert lot.quantity == 7.0
    assert [(p.quantity, p.quantity_completed) for p in lot.positions] == [(9.0, 8.0), (7.0, 6.0)]


async def test_an_inspection_reject_shrinks_the_lot_by_the_rejected_pieces() -> None:
    floor = Floor(positions=2, inspection_last=True)
    lot = await floor.lot(10.0)
    first, second = await floor.positions(lot.id)
    await floor.order(first, processed=10.0)
    [qa] = await floor.orders_of(second)
    await floor.start(qa)
    await floor.settle(lot.id)
    await floor.complete(qa.id, 7.0)

    await floor.complete(qa.id, 3.0, rejected=1.0, scrap=1.0)

    lot = await floor.reload(lot.id)
    assert (lot.quantity, lot.positions[1].quantity, lot.positions[1].quantity_completed) == (
        9.0,
        9.0,
        9.0,
    )
    assert lot.status == "completed"


async def test_a_finished_demand_keeps_at_least_its_exact_share_through_a_scrap() -> None:
    floor = Floor(positions=1)
    lot = await floor.lot(
        9.0,
        demands=[
            (1, 3.0, MadeItemDemandStatus.OPEN),
            (2, 3.0, MadeItemDemandStatus.OPEN),
            (3, 3.0, MadeItemDemandStatus.OPEN),
        ],
    )
    finished = await floor.made_demands.get_by_id(1)
    assert finished is not None
    finished.status = MadeItemDemandStatus.FULFILLED
    finished.fulfilled_manually_at = NOW
    [only] = await floor.positions(lot.id)
    running = await floor.order(only)
    await floor.settle(lot.id)

    await floor.scrap(running.id, 1.0)

    allocations = {
        a.demand_item_id: a.quantity for a in await floor.made_allocations.get_by_lot_id(lot.id)
    }
    assert allocations[1] >= 3.0 * 8.0 / 9.0
    assert round(sum(allocations.values()), 6) == 8.0


async def _finished_and_live(floor: Floor) -> tuple[int, int]:
    """A lot of 9 covering a fulfilled demand #1 of 3 and an open demand #2
    of 6; returns the lot id and the running order of its last position."""
    lot = await floor.lot(
        9.0, demands=[(1, 3.0, MadeItemDemandStatus.OPEN), (2, 6.0, MadeItemDemandStatus.OPEN)]
    )
    finished = await floor.made_demands.get_by_id(1)
    assert finished is not None
    finished.status = MadeItemDemandStatus.FULFILLED
    finished.fulfilled_manually_at = NOW
    positions = await floor.positions(lot.id)
    for earlier in positions[:-1]:
        await floor.order(earlier, processed=9.0)
    running = await floor.order(positions[-1])
    await floor.settle(lot.id)
    return lot.id, running.id


async def _follow_up_allocations(floor: Floor, lot_id: int) -> dict[int, float]:
    return {
        a.demand_item_id: a.quantity for a in await floor.made_allocations.get_by_lot_id(lot_id)
    }


async def test_a_replacement_lot_gives_a_finished_demand_no_share() -> None:
    floor = Floor(positions=1)
    _lot_id, running = await _finished_and_live(floor)

    [replacement] = await floor.scrap(running, 3.0, replace=True)

    # The finished demand is cut only after every live one, so the three
    # scrapped pieces come off the open demand and move to the replacement.
    assert await _follow_up_allocations(floor, replacement) == {2: 3.0}


async def test_a_rework_lot_gives_a_finished_demand_no_share() -> None:
    floor = Floor(positions=2, inspection_last=True)
    lot = await floor.lot(
        9.0, demands=[(1, 3.0, MadeItemDemandStatus.OPEN), (2, 6.0, MadeItemDemandStatus.OPEN)]
    )
    finished = await floor.made_demands.get_by_id(1)
    assert finished is not None
    finished.status = MadeItemDemandStatus.FULFILLED
    finished.fulfilled_manually_at = NOW
    first, second = await floor.positions(lot.id)
    await floor.order(first, processed=9.0)
    [qa] = await floor.orders_of(second)
    await floor.start(qa)
    await floor.settle(lot.id)

    await floor.complete(qa.id, 3.0, rejected=3.0, rework=3.0)

    rework_lots = [
        other.id
        for other in floor.lots._lots.values()
        if other.origin_lot_id == lot.id and other.origin_disposition == "rework"
    ]
    assert len(rework_lots) == 1
    assert await _follow_up_allocations(floor, rework_lots[0]) == {2: 3.0}


async def test_a_scrap_shrinks_only_what_the_allocations_exceed() -> None:
    floor = Floor(positions=1)
    lot = await floor.lot(10.0, demands=[(1, 4.0, MadeItemDemandStatus.OPEN)])
    [only] = await floor.positions(lot.id)
    running = await floor.order(only)
    await floor.settle(lot.id)

    await floor.scrap(running.id, 2.0)

    assert await _follow_up_allocations(floor, lot.id) == {1: 4.0}


def test_the_shrink_caps_a_legacy_completed_count_above_the_new_quantity() -> None:
    # Written before the disposition guard: position 2 completed more than
    # the shrunk lot leaves it, which the stored count cannot keep.
    lot = _lot(10.0, [(10.0, 10.0), (10.0, 10.0)])

    shrink_lot_for_scrap(lot, lot.positions[1], 2.0)

    assert [(p.quantity, p.quantity_completed) for p in lot.positions] == [
        (10.0, 10.0),
        (8.0, 8.0),
    ]


def test_a_cut_leaves_no_float_residue_below_what_an_order_processed() -> None:
    # 1.0 - 0.9 is a hair below 0.1, which would store an order whose
    # completed count exceeds its quantity.
    position = make(LotPosition, id=3, sequence=3, quantity=0.1, quantity_completed=0.0)
    running = Commitment(id=30, is_line=False, quantity=1.0, done=0.1)

    [cut] = plan_commitment_cuts(position, [running], accepted_now=0.1)

    assert cut.quantity == 0.1
    assert cut.quantity >= running.done


def test_the_shrink_leaves_no_float_residue_below_a_completed_count() -> None:
    lot = _lot(1.0, [(1.0, 0.1), (1.0, 0.1)])

    shrink_lot_for_scrap(lot, lot.positions[1], 0.9)

    assert [(p.quantity, p.quantity_completed) for p in lot.positions][1] == (0.1, 0.1)


def test_an_ordered_line_is_neither_cut_nor_counted_in_the_excess() -> None:
    position = make(LotPosition, id=3, sequence=3, quantity=6.0, quantity_completed=0.0)
    order = Commitment(id=30, is_line=False, quantity=6.0, done=0.0, queued=True)
    ordered = Commitment(id=41, is_line=True, quantity=4.0, done=0.0, cuttable=False)

    assert plan_commitment_cuts(position, [order, ordered]) == []


def test_no_split_share_exceeds_its_weight() -> None:
    weights = [0.1234567, 0.2345678, 0.3456789]
    shares = split_quantity_by_largest_remainder(sum(weights), weights)

    assert all(share <= weight for share, weight in zip(shares, weights, strict=True))


async def test_a_replacement_takes_back_only_what_the_scrap_cut() -> None:
    """Lot 10 with one allocation of 4: a scrap of 3 leaves 7, which the 4
    still fit, so nothing is cut and the replacement takes nothing."""
    floor = Floor(positions=1)
    lot = await floor.lot(10.0, demands=[(1, 4.0, MadeItemDemandStatus.OPEN)])
    [only] = await floor.positions(lot.id)
    running = await floor.order(only)
    await floor.settle(lot.id)

    [replacement] = await floor.scrap(running.id, 3.0, replace=True)

    assert await _follow_up_allocations(floor, lot.id) == {1: 4.0}
    assert await _follow_up_allocations(floor, replacement) == {}


async def _demand_totals(floor: Floor) -> dict[int, float]:
    totals: dict[int, float] = {}
    for lot_id in floor.lots._lots:
        for allocation in await floor.made_allocations.get_by_lot_id(lot_id):
            totals[allocation.demand_item_id] = (
                totals.get(allocation.demand_item_id, 0.0) + allocation.quantity
            )
    return totals


@settings(max_examples=30, deadline=None)
@given(
    allocated=st.lists(st.integers(1, 4), min_size=1, max_size=3),
    spare=st.integers(0, 3),
    scrapped=st.integers(1, 5),
    replace=st.booleans(),
)
def test_no_demand_ends_above_its_allocation_across_origin_and_follow_up_lots(
    allocated: list[int], spare: int, scrapped: int, replace: bool
) -> None:
    async def scenario() -> None:
        quantity = float(sum(allocated) + spare)
        floor = Floor(positions=1)
        demands = [(i + 1, float(q), MadeItemDemandStatus.OPEN) for i, q in enumerate(allocated)]
        lot = await floor.lot(quantity, demands=demands)
        [only] = await floor.positions(lot.id)
        running = await floor.order(only)
        await floor.settle(lot.id)

        await floor.scrap(running.id, min(float(scrapped), quantity), replace=replace)

        totals = await _demand_totals(floor)
        for demand_id, need, _ in demands:
            assert totals.get(demand_id, 0.0) <= need + 1e-6, (demand_id, totals)
            if replace:
                # Whatever the scrap cut, the replacement took back.
                assert abs(totals.get(demand_id, 0.0) - need) <= 1e-6, (demand_id, totals)

    asyncio.run(scenario())


def test_the_lot_quantity_snaps_to_its_last_positions_quantity() -> None:
    # 1.0 - 0.9 leaves 0.09999999999999998 on the lot, a hair below the
    # 0.1 its last position completed.
    lot = _lot(1.0, [(1.0, 0.1), (1.0, 0.1)])

    shrink_lot_for_scrap(lot, lot.positions[1], 0.9)

    assert lot.quantity == 0.1
    assert lot.quantity == lot.positions[1].quantity


async def test_pieces_scrapped_once_cannot_be_scrapped_again() -> None:
    """Position 1 made 4. Scrapping those 4 at position 2 uses them up, so a
    second scrap of 4 there, a retried request for example, is refused
    instead of scrapping pieces that never arrived."""
    floor = Floor(positions=2)
    lot = await floor.lot(10.0)
    first, second = await floor.positions(lot.id)
    await floor.order(first, processed=4.0)
    downstream = await floor.order(second)
    await floor.settle(lot.id)
    await floor.scrap(downstream.id, 4.0)

    with pytest.raises(ScrapQuantityExceedsAvailableError):
        await floor.scrap(downstream.id, 4.0)
    lot = await floor.reload(lot.id)
    assert lot.quantity == 6.0


async def test_an_inspection_cannot_reject_more_than_reached_it() -> None:
    """Position 1 made 5. An inspection recording 10, 2 accepted and 8
    rejected, would dispose of pieces it never saw; it is refused, and
    recording the 5 that arrived is not."""
    floor = Floor(positions=2, inspection_last=True)
    lot = await floor.lot(10.0)
    first, second = await floor.positions(lot.id)
    await floor.order(first, processed=5.0)
    inspection = await floor.order(second)
    await floor.settle(lot.id)

    with pytest.raises(LotPositionOverflowError):
        await floor.complete(inspection.id, 10.0, rejected=8.0, scrap=8.0)
    await floor.complete(inspection.id, 5.0, rejected=1.0, scrap=1.0)
