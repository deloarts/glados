"""
Direct unit tests for the shared allocation-coverage math
(compute_coverage_totals), closing branch-coverage gaps not exercised by
its production callers:
  - tests/unit/test_raw_material_coverage.py (ORM-facing adapter)
  - tests/unit/test_made_item_allocation_use_cases.py::TestComputeCoverageTotals

Both of those pass a coverage_ref_id of None only for STOCK allocations,
which the loop filters out before the "ref_id is None" check, so only this
file exercises that branch. It also pins recorded_substitution, the one
substitution rule every order line allocation writer uses.
"""

from dataclasses import dataclass

from src.modules.fulfillment.domain.services.allocation_coverage import CoverageInfo
from src.modules.fulfillment.domain.services.allocation_coverage import RecordedSubstitution
from src.modules.fulfillment.domain.services.allocation_coverage import compute_coverage_totals
from src.modules.fulfillment.domain.services.allocation_coverage import fill_by_reference
from src.modules.fulfillment.domain.services.allocation_coverage import recorded_substitution


@dataclass
class _Alloc:
    quantity: float
    source: str
    coverage_ref_id: int | None
    demand_item_id: int = 1


class _FixedCoverageSource:
    def __init__(self, coverage: dict[int, CoverageInfo]) -> None:
        self._coverage = coverage

    def coverage_for(self, ref_id: int) -> CoverageInfo | None:
        return self._coverage.get(ref_id)


class TestComputeCoverageTotalsBranchGaps:
    def test_non_stock_allocation_without_coverage_ref_is_skipped(self):
        # A non-stock allocation with no coverage_ref_id shouldn't happen in
        # practice (every real order/lot allocation carries a ref id), but
        # the function has a defensive `continue` for it, prove it doesn't
        # crash and simply contributes nothing beyond "allocated".
        allocations = [_Alloc(quantity=5.0, source="order", coverage_ref_id=None)]

        allocated, ordered, delivered, fulfilled_from_stock = compute_coverage_totals(
            allocations, _FixedCoverageSource({}), stock_source_value="stock", rank=0, fill={}
        )

        assert allocated == 5.0
        assert ordered == 0.0
        assert delivered == 0.0
        assert fulfilled_from_stock == 0.0

    def test_delivered_accumulates_even_when_not_placed(self):
        # is_placed only gates "ordered", "delivered" accrues independently.
        allocations = [_Alloc(quantity=10.0, source="order", coverage_ref_id=1)]
        coverage = _FixedCoverageSource({1: CoverageInfo(is_placed=False, arrived=6.0)})

        allocated, ordered, delivered, fulfilled_from_stock = compute_coverage_totals(
            allocations, coverage, stock_source_value="stock", rank=0, fill={}
        )

        assert allocated == 10.0
        assert ordered == 0.0
        assert delivered == 6.0
        assert fulfilled_from_stock == 0.0

    def test_empty_allocations_returns_all_zero(self):
        allocated, ordered, delivered, fulfilled_from_stock = compute_coverage_totals(
            [], _FixedCoverageSource({}), stock_source_value="stock", rank=0, fill={}
        )
        assert (allocated, ordered, delivered, fulfilled_from_stock) == (0.0, 0.0, 0.0, 0.0)


class TestFillOrder:
    def test_arrived_pieces_fill_the_older_demand_first_and_the_surplus_last(self):
        # A line of 12 for demands #1 (6) and #2 (4) received 8: #1 takes 6,
        # #2 takes 2, and the 2 surplus pieces wait for no demand.
        allocations = [
            _Alloc(quantity=6.0, source="order", coverage_ref_id=1, demand_item_id=1),
            _Alloc(quantity=4.0, source="order", coverage_ref_id=1, demand_item_id=2),
        ]
        fill = fill_by_reference((0, allocations, "stock"))
        coverage = _FixedCoverageSource({1: CoverageInfo(is_placed=True, arrived=8.0)})

        delivered = [
            compute_coverage_totals([a], coverage, "stock", rank=0, fill=fill)[2]
            for a in allocations
        ]

        assert delivered == [6.0, 2.0]

    def test_a_later_family_waits_for_the_earlier_one(self):
        bought = [_Alloc(quantity=5.0, source="order", coverage_ref_id=1, demand_item_id=9)]
        source = [_Alloc(quantity=5.0, source="order", coverage_ref_id=1, demand_item_id=1)]
        fill = fill_by_reference((0, bought, "stock"), (1, source, "stock"))
        coverage = _FixedCoverageSource({1: CoverageInfo(is_placed=True, arrived=7.0)})

        assert compute_coverage_totals(source, coverage, "stock", rank=1, fill=fill)[2] == 2.0
        assert compute_coverage_totals(bought, coverage, "stock", rank=0, fill=fill)[2] == 5.0


class TestRecordedSubstitution:
    def test_a_line_for_another_item_records_it_with_the_reason(self):
        assert recorded_substitution(1, 2, "Successor part") == RecordedSubstitution(
            item_id=2, reason="Successor part"
        )

    def test_a_line_for_the_demands_own_item_drops_the_reason(self):
        assert recorded_substitution(1, 1, "stray reason") == RecordedSubstitution(
            item_id=None, reason=None
        )

    def test_no_item_on_either_side_is_a_plain_match(self):
        assert recorded_substitution(None, None, "stray reason") == RecordedSubstitution(
            item_id=None, reason=None
        )
