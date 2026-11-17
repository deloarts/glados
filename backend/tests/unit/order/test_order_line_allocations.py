"""
How the allocations on a line or lot are fitted into a smaller quantity
(lifecycle/demand.py fit_in_fill_order): unchanged when they fit, otherwise
cut from the end of the fill order, the newest demand first, so no demand
loses pieces that already reached it while a later one keeps an allocation;
finished demands are cut only after every live one, nothing grows, and the
allocations sum to the limit.
"""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from src.modules.fulfillment.domain.services.lifecycle.demand import fit_in_fill_order

_EPS = 1e-6


class TestFitInFillOrder:
    @pytest.mark.parametrize("limit", [10.0, 12.0, 10.0 - 1e-9])
    def test_allocations_that_fit_stay_as_they_are(self, limit: float) -> None:
        assert fit_in_fill_order([4.0, 6.0], limit) == [4.0, 6.0]

    def test_the_newest_demand_is_cut_first(self) -> None:
        assert fit_in_fill_order([4.0, 3.0, 3.0], 6.0) == [4.0, 2.0, 0.0]

    def test_a_cut_beyond_the_newest_demand_moves_to_the_one_before(self) -> None:
        assert fit_in_fill_order([4.0, 3.0, 3.0], 2.5) == [2.5, 0.0, 0.0]

    def test_a_finished_demand_is_cut_only_after_every_live_one(self) -> None:
        assert fit_in_fill_order([4.0, 3.0, 3.0], 5.0, [False, False, True]) == [2.0, 0.0, 3.0]

    def test_nothing_left_releases_every_allocation(self) -> None:
        assert fit_in_fill_order([3.0, 2.0], 0.0) == [0.0, 0.0]

    @given(
        quantities=st.lists(
            st.integers(min_value=0, max_value=1_000_000).map(lambda n: n / 1000),
            min_size=1,
            max_size=6,
        ),
        fraction=st.floats(min_value=0.0, max_value=1.0),
        finished=st.lists(st.booleans(), min_size=6, max_size=6),
    )
    def test_the_allocations_sum_to_the_limit_and_none_grows(
        self, quantities: list[float], fraction: float, finished: list[bool]
    ) -> None:
        limit = round(sum(quantities) * fraction, 3)

        fitted = fit_in_fill_order(quantities, limit, finished[: len(quantities)])

        assert len(fitted) == len(quantities)
        assert abs(sum(fitted) - min(limit, sum(quantities))) <= _EPS
        for kept, old in zip(fitted, quantities, strict=True):
            assert -_EPS <= kept <= old + _EPS
