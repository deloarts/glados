"""
Direct coverage of _raw_material_coverage.py's ORM-facing adapters
(_AllocationRow, _OrmOrderItemCoverageSource) and the multi-allocation
summation they feed into compute_coverage_totals. This is the mechanism
the raw-material-as-virtual-predecessor gate (lot_rules.py) relies on to
decide whether a lot's step 1 may start/complete, it must correctly sum
delivered + fulfilled_from_stock across every allocation linked to a
demand (multiple order items, plus one stock row), not just look at a
single link.

compute_raw_material_arrived_quantity() itself takes a live SQLAlchemy
Session and isn't exercised here, this codebase's test suite has no
DB-backed test fixtures anywhere (all unit tests replace dependencies
with in-memory fakes), so introducing one for a single float-returning
helper isn't warranted. The two adapters below are exactly the part of
that function with real logic (arrived pieces, STOCK vs ORDER
routing); the DB queries around them are plain SQLAlchemy filters with
nothing to unit test.
"""

from dataclasses import dataclass

from src.modules.fulfillment.adapters.outbound.persistence.repositories._raw_material_coverage import (
    _AllocationRow,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories._raw_material_coverage import (
    _OrmOrderItemCoverageSource,
)
from src.modules.fulfillment.domain.services.allocation_coverage import compute_coverage_totals
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemAllocationSource,
)


@dataclass
class _FakeAllocationOrm:
    quantity: float
    source: str
    order_item_id: int | None
    demand_item_id: int = 1


@dataclass
class _FakeOrderItemOrm:
    id: int
    status: str
    quantity: float
    quantity_delivered: float


class TestAllocationRow:
    def test_order_sourced_row_exposes_order_item_id_as_ref(self):
        row = _AllocationRow(_FakeAllocationOrm(quantity=5.0, source="order", order_item_id=42))
        assert row.quantity == 5.0
        assert row.source == "order"
        assert row.coverage_ref_id == 42

    def test_stock_sourced_row_has_no_coverage_ref(self):
        row = _AllocationRow(_FakeAllocationOrm(quantity=3.0, source="stock", order_item_id=None))
        assert row.coverage_ref_id is None


class TestOrmOrderItemCoverageSource:
    def test_reports_the_accepted_pieces_of_a_placed_order_item(self):
        order_item = _FakeOrderItemOrm(
            id=1,
            status=OrderItemStatus.PARTIALLY_DELIVERED.value,
            quantity=10.0,
            quantity_delivered=4.0,
        )
        source = _OrmOrderItemCoverageSource({1: order_item})
        coverage = source.coverage_for(1)
        assert coverage is not None
        assert coverage.is_placed is True
        assert coverage.arrived == 4.0

    def test_pending_order_item_is_not_placed(self):
        order_item = _FakeOrderItemOrm(
            id=1, status=OrderItemStatus.PENDING.value, quantity=10.0, quantity_delivered=0.0
        )
        source = _OrmOrderItemCoverageSource({1: order_item})
        assert source.coverage_for(1).is_placed is False

    def test_unknown_ref_returns_none(self):
        source = _OrmOrderItemCoverageSource({})
        assert source.coverage_for(999) is None

    def test_zero_quantity_order_item_has_nothing_arrived(self):
        order_item = _FakeOrderItemOrm(
            id=1, status=OrderItemStatus.ORDERED.value, quantity=0.0, quantity_delivered=0.0
        )
        source = _OrmOrderItemCoverageSource({1: order_item})
        assert source.coverage_for(1).arrived == 0.0


class TestMultiAllocationSummation:
    """
    Proves the exact scenario the raw-material gate depends on: a demand
    covered by several order items (at different delivery stages) plus a
    stock top-up sums to delivered + fulfilled_from_stock correctly.
    """

    def test_sums_delivered_across_multiple_order_items_plus_stock(self):
        order_items_by_id = {
            1: _FakeOrderItemOrm(
                id=1,
                status=OrderItemStatus.DELIVERED.value,
                quantity=4.0,
                quantity_delivered=4.0,
            ),
            2: _FakeOrderItemOrm(
                id=2,
                status=OrderItemStatus.PARTIALLY_DELIVERED.value,
                quantity=10.0,
                quantity_delivered=5.0,
            ),
        }
        allocations = [
            _AllocationRow(_FakeAllocationOrm(quantity=4.0, source="order", order_item_id=1)),
            _AllocationRow(_FakeAllocationOrm(quantity=2.0, source="order", order_item_id=2)),
            _AllocationRow(_FakeAllocationOrm(quantity=1.5, source="stock", order_item_id=None)),
        ]

        allocated, ordered, delivered, fulfilled_from_stock = compute_coverage_totals(
            allocations,
            _OrmOrderItemCoverageSource(order_items_by_id),
            SourceItemAllocationSource.STOCK.value,
            rank=1,
            fill={},
        )

        # "allocated" excludes stock-sourced rows (that's fulfilled_from_stock);
        # only the two order-backed allocations count: 4.0 + 2.0.
        assert allocated == 6.0
        assert ordered == 6.0
        # order 1: 4 arrived -> the allocation of 4 takes 4
        # order 2: 5 arrived, nothing ahead -> the allocation of 2 takes 2
        assert delivered == 6.0
        assert fulfilled_from_stock == 1.5
        # "arrived" for the raw-material gate is delivered + fulfilled_from_stock
        assert delivered + fulfilled_from_stock == 7.5

    def test_no_allocations_means_nothing_arrived(self):
        allocated, ordered, delivered, fulfilled_from_stock = compute_coverage_totals(
            [],
            _OrmOrderItemCoverageSource({}),
            SourceItemAllocationSource.STOCK.value,
            rank=1,
            fill={},
        )
        assert (allocated, ordered, delivered, fulfilled_from_stock) == (0.0, 0.0, 0.0, 0.0)

    def test_stock_only_fulfillment_counts_as_arrived_with_no_order(self):
        allocations = [
            _AllocationRow(_FakeAllocationOrm(quantity=6.0, source="stock", order_item_id=None))
        ]
        _, _, delivered, fulfilled_from_stock = compute_coverage_totals(
            allocations,
            _OrmOrderItemCoverageSource({}),
            SourceItemAllocationSource.STOCK.value,
            rank=1,
            fill={},
        )
        assert delivered == 0.0
        assert fulfilled_from_stock == 6.0
