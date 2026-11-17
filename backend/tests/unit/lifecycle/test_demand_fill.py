"""
Which demands a new or larger allocation would take arrived pieces from:
arrived pieces fill a line oldest demand first within a family and bought
before source, so an allocation that sorts ahead takes pieces from the
demands behind it, and one that sorts behind takes none.
"""

from src.modules.fulfillment.domain.services.lifecycle.demand import BOUGHT_FILL_RANK
from src.modules.fulfillment.domain.services.lifecycle.demand import SOURCE_FILL_RANK
from src.modules.fulfillment.domain.services.lifecycle.demand import displaced_demand_ids


def test_an_older_demand_ahead_takes_the_pieces_of_a_younger_one() -> None:
    fill = [(BOUGHT_FILL_RANK, 2, 5.0)]

    assert displaced_demand_ids(fill, 5.0, BOUGHT_FILL_RANK, 1, 5.0) == [2]


def test_a_younger_demand_behind_takes_nothing() -> None:
    fill = [(BOUGHT_FILL_RANK, 1, 5.0)]

    assert displaced_demand_ids(fill, 5.0, BOUGHT_FILL_RANK, 2, 5.0) == []


def test_an_allocation_ahead_takes_nothing_while_no_piece_arrived() -> None:
    fill = [(BOUGHT_FILL_RANK, 2, 5.0)]

    assert displaced_demand_ids(fill, 0.0, BOUGHT_FILL_RANK, 1, 5.0) == []


def test_an_allocation_ahead_takes_only_what_the_line_cannot_cover_for_both() -> None:
    fill = [(BOUGHT_FILL_RANK, 2, 5.0)]

    assert displaced_demand_ids(fill, 10.0, BOUGHT_FILL_RANK, 1, 5.0) == []
    assert displaced_demand_ids(fill, 8.0, BOUGHT_FILL_RANK, 1, 5.0) == [2]


def test_a_bought_allocation_comes_before_every_source_one() -> None:
    fill = [(SOURCE_FILL_RANK, 1, 5.0)]

    assert displaced_demand_ids(fill, 5.0, BOUGHT_FILL_RANK, 9, 2.0) == [1]


def test_growing_an_own_allocation_counts_against_the_demands_behind() -> None:
    fill = [(BOUGHT_FILL_RANK, 1, 2.0), (BOUGHT_FILL_RANK, 2, 5.0)]

    assert displaced_demand_ids(fill, 7.0, BOUGHT_FILL_RANK, 1, 4.0) == [2]
    assert displaced_demand_ids(fill, 7.0, BOUGHT_FILL_RANK, 1, 2.0) == []
