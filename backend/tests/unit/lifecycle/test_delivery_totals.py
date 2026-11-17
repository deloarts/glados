"""Unit tests for src/modules/fulfillment/domain/services/lifecycle/delivery_totals.py, the
comparison of an order line's stored delivery totals with the sums over its
delivery rows."""

from src.modules.fulfillment.domain.services.lifecycle.delivery_totals import DeliveryTotals
from src.modules.fulfillment.domain.services.lifecycle.delivery_totals import TotalsDifference
from src.modules.fulfillment.domain.services.lifecycle.delivery_totals import (
    delivery_totals_differences,
)
from src.modules.fulfillment.domain.services.lifecycle.delivery_totals import stored_totals
from tests.unit.order._helpers import make_order_item


def test_totals_equal_to_their_rows_differ_nowhere():
    totals = DeliveryTotals(accepted=6.0, rejected=2.0, lost=1.0)

    assert delivery_totals_differences(totals, totals) == ()


def test_a_line_without_rows_and_without_totals_differs_nowhere():
    assert delivery_totals_differences(DeliveryTotals(), DeliveryTotals()) == ()


def test_every_differing_total_is_named_by_its_column_in_column_order():
    stored = DeliveryTotals(accepted=10.0, rejected=2.0, lost=2.0)
    from_rows = DeliveryTotals(accepted=4.0, rejected=2.0, lost=0.0)

    assert delivery_totals_differences(stored, from_rows) == (
        TotalsDifference(field="quantity_delivered", stored=10.0, from_rows=4.0),
        TotalsDifference(field="quantity_rejected_lost", stored=2.0, from_rows=0.0),
    )


def test_pieces_booked_without_a_row_differ_from_the_rows():
    stored = DeliveryTotals(accepted=10.0)

    assert delivery_totals_differences(stored, DeliveryTotals()) == (
        TotalsDifference(field="quantity_delivered", stored=10.0, from_rows=0.0),
    )


def test_float_noise_within_the_lifecycle_tolerance_is_no_difference():
    stored = DeliveryTotals(accepted=0.7 + 0.2 + 0.1, rejected=0.1 + 0.2)
    from_rows = DeliveryTotals(accepted=1.0, rejected=0.3)

    assert delivery_totals_differences(stored, from_rows) == ()


def test_a_line_stores_its_accepted_rejected_and_lost_pieces():
    line = make_order_item()
    line.quantity_delivered, line.quantity_rejected, line.quantity_rejected_lost = 6.0, 3.0, 2.0

    assert stored_totals(line) == DeliveryTotals(accepted=6.0, rejected=3.0, lost=2.0)
