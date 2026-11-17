"""
Covers how a lot's "where is my raw material coming from" block
(source_order_id / source_order_number / source_expected_delivery_date /
source_delivery_date) is resolved and carried out to the API.

Two halves, matching how test_raw_material_coverage.py splits the same
kind of ORM-facing helper:

  - _order_item_arrival_sort_key, the actual decision logic, which of a
    demand's several order items decides when the material lands. The
    surrounding _source_order_info_by_demand_id is plain batched
    SQLAlchemy filters plus this key, and this suite has no DB-backed
    fixtures anywhere, so the key is the part worth testing directly.
  - LotMapper, so the resolved values actually reach LotResult /
    LotSummaryResult rather than being dropped a layer below the API.
"""

from datetime import UTC
from datetime import date
from datetime import datetime

from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository._read_model import (
    _order_item_arrival_sort_key,
)
from src.modules.fulfillment.application.mappers.production_lot_mapper import LotMapper
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass


class _FakeOrderItemOrm:
    """Only the two date columns the sort key reads."""

    def __init__(self, expected_delivery_date: date | None, delivery_date: date | None) -> None:
        self.expected_delivery_date = expected_delivery_date
        self.delivery_date = delivery_date


def make_lot(**overrides) -> ProductionLot:
    defaults = dict(
        id=1,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        lot_number="LOT-0001",
        quantity=10.0,
        status=LotStatus.DRAFT,
        priority=UrgencyClass.NORMAL,
        note=None,
        creator_id=1,
        made_item_id=1,
        project_id=1,
        input_demand_id=None,
    )
    defaults.update(overrides)
    return ProductionLot(**defaults)


class TestOrderItemArrivalSortKey:
    def test_confirmed_delivery_outranks_any_projection(self):
        """An arrived item decides the answer even when another order is
        projected to land much later, the projection can still move, the
        fact cannot."""
        arrived = _FakeOrderItemOrm(expected_delivery_date=None, delivery_date=date(2026, 1, 1))
        projected_far_out = _FakeOrderItemOrm(
            expected_delivery_date=date(2026, 12, 31), delivery_date=None
        )
        winner = max([projected_far_out, arrived], key=_order_item_arrival_sort_key)
        assert winner is arrived

    def test_latest_confirmed_delivery_wins(self):
        early = _FakeOrderItemOrm(expected_delivery_date=None, delivery_date=date(2026, 3, 1))
        late = _FakeOrderItemOrm(expected_delivery_date=None, delivery_date=date(2026, 6, 1))
        assert max([early, late], key=_order_item_arrival_sort_key) is late
        assert max([late, early], key=_order_item_arrival_sort_key) is late

    def test_latest_projection_wins_when_nothing_arrived(self):
        early = _FakeOrderItemOrm(expected_delivery_date=date(2026, 3, 1), delivery_date=None)
        late = _FakeOrderItemOrm(expected_delivery_date=date(2026, 6, 1), delivery_date=None)
        assert max([early, late], key=_order_item_arrival_sort_key) is late

    def test_undated_item_loses_to_any_dated_sibling(self):
        undated = _FakeOrderItemOrm(expected_delivery_date=None, delivery_date=None)
        dated = _FakeOrderItemOrm(expected_delivery_date=date(2026, 3, 1), delivery_date=None)
        assert max([undated, dated], key=_order_item_arrival_sort_key) is dated

    def test_undated_item_still_selectable_when_it_is_all_there_is(self):
        """A demand allocated against an order that has no dates yet should
        still surface its order link, not fall back to "no source order"."""
        undated = _FakeOrderItemOrm(expected_delivery_date=None, delivery_date=None)
        assert max([undated], key=_order_item_arrival_sort_key) is undated


class TestLotMapperCarriesSourceOrder:
    def test_to_summary_carries_resolved_source_order(self):
        lot = make_lot(
            input_demand_id=7,
            source_order_id=42,
            source_order_number="ORD-0042",
            source_expected_delivery_date=date(2026, 5, 1),
            # Arrival is a recorded event and carries a time of day; the
            # expected date above is a projection and stays a plain date.
            source_delivery_date=datetime(2026, 4, 28, 11, 5, tzinfo=UTC),
        )
        result = LotMapper.to_summary(lot)
        assert result.source_order_id == 42
        assert result.source_order_number == "ORD-0042"
        assert result.source_expected_delivery_date == date(2026, 5, 1)
        assert result.source_delivery_date == datetime(2026, 4, 28, 11, 5, tzinfo=UTC)

    def test_to_result_carries_resolved_source_order(self):
        lot = make_lot(
            input_demand_id=7,
            source_order_id=42,
            source_order_number="ORD-0042",
            source_expected_delivery_date=date(2026, 5, 1),
            source_delivery_date=None,
        )
        result = LotMapper.to_result(lot)
        assert result.source_order_id == 42
        assert result.source_order_number == "ORD-0042"
        assert result.source_expected_delivery_date == date(2026, 5, 1)
        assert result.source_delivery_date is None

    def test_lot_without_demand_reports_no_source_order(self):
        """A lot with no linked demand (or one fulfilled purely from stock)
        must report nothing rather than a fabricated order link."""
        result = LotMapper.to_summary(make_lot(input_demand_id=None))
        assert result.source_order_id is None
        assert result.source_order_number is None
        assert result.source_expected_delivery_date is None
        assert result.source_delivery_date is None
