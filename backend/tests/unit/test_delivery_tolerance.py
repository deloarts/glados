"""The delivery tolerance rule of a bought or source order line, and how an
item's create and update commands carry an item's own tolerances."""

import dataclasses
import math
from types import SimpleNamespace

import pytest

from src.modules.catalogue.application.dto.bought_item_dto import UpdateBoughtItemCommand
from src.modules.catalogue.application.services.item_delivery_tolerance import (
    keep_unsent_tolerances,
)
from src.modules.catalogue.domain.errors import DeliveryToleranceInvalidError
from src.modules.catalogue.domain.services.item_delivery_tolerance_rules import (
    assert_valid_tolerance,
)
from src.modules.fulfillment.domain.services.delivery_tolerance import NO_TOLERANCE
from src.modules.fulfillment.domain.services.delivery_tolerance import DeliveryTolerance
from src.modules.fulfillment.domain.services.delivery_tolerance import closes_within_under_tolerance
from src.modules.fulfillment.domain.services.delivery_tolerance import over_delivery_allowance
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from tests.unit.order._helpers import make_order_item


def _line(quantity=100.0, unit="pcs", line_type=OrderLineType.BOUGHT, **fields):
    return dataclasses.replace(
        make_order_item(status=OrderItemStatus.ORDERED),
        quantity=quantity,
        unit=unit,
        line_type=line_type,
        **fields,
    )


class TestResolve:
    def test_the_item_value_replaces_the_global_one(self):
        tolerance = DeliveryTolerance.resolve(
            over_percent=5.0, under_percent=2.0, item_over_percent=0.0, item_under_percent=None
        )
        assert tolerance == DeliveryTolerance(over_percent=0.0, under_percent=2.0)


class TestValidation:
    @pytest.mark.parametrize("value", [None, 0.0, 12.5, 100.0])
    def test_accepts_a_percentage(self, value):
        assert_valid_tolerance(value, what="The tolerance")

    @pytest.mark.parametrize("value", [-0.1, 100.1, math.nan, math.inf])
    def test_refuses_anything_else(self, value):
        with pytest.raises(DeliveryToleranceInvalidError, match="The tolerance"):
            assert_valid_tolerance(value, what="The tolerance")


class TestOverAllowance:
    def test_no_tolerance_allows_nothing_beyond_the_quantity(self):
        assert over_delivery_allowance(_line(), NO_TOLERANCE) == 0.0

    def test_counted_units_round_down_to_whole_pieces(self):
        tolerance = DeliveryTolerance(over_percent=3.0)
        assert over_delivery_allowance(_line(quantity=10.0), tolerance) == 0.0
        assert over_delivery_allowance(_line(quantity=150.0), tolerance) == 4.0

    def test_a_measured_unit_keeps_the_fraction(self):
        tolerance = DeliveryTolerance(over_percent=2.5)
        assert over_delivery_allowance(_line(quantity=10.0, unit="M"), tolerance) == 0.25

    def test_a_made_line_has_no_tolerance(self):
        line = _line(line_type=OrderLineType.MADE)
        assert over_delivery_allowance(line, DeliveryTolerance(over_percent=10.0)) == 0.0


class TestUnderTolerance:
    tolerance = DeliveryTolerance(under_percent=2.0)

    def test_a_line_within_the_tolerance_closes(self):
        assert closes_within_under_tolerance(_line(quantity_delivered=98.0), self.tolerance)

    def test_lost_pieces_count_as_settled(self):
        line = _line(quantity_delivered=97.0, quantity_rejected_lost=1.0)
        assert closes_within_under_tolerance(line, self.tolerance)

    def test_a_line_further_short_stays_open(self):
        assert not closes_within_under_tolerance(_line(quantity_delivered=97.0), self.tolerance)

    def test_a_line_settled_in_full_does_not_close_short(self):
        assert not closes_within_under_tolerance(_line(quantity_delivered=100.0), self.tolerance)

    def test_no_tolerance_never_closes(self):
        assert not closes_within_under_tolerance(_line(quantity_delivered=99.0), NO_TOLERANCE)

    def test_a_made_line_never_closes(self):
        line = _line(line_type=OrderLineType.MADE, quantity_delivered=99.0)
        assert not closes_within_under_tolerance(line, self.tolerance)


class TestKeepUnsentTolerances:
    def _command(self, **fields):
        return UpdateBoughtItemCommand(
            order_code_1="OC-1", article_name="Article", manufacturer_id=1, **fields
        )

    def test_an_update_without_them_keeps_the_item_values(self):
        item = SimpleNamespace(
            over_delivery_tolerance_percent=5.0, under_delivery_tolerance_percent=2.0
        )
        kept = keep_unsent_tolerances(self._command(), item)
        assert kept.over_delivery_tolerance_percent == 5.0
        assert kept.under_delivery_tolerance_percent == 2.0

    def test_values_the_update_sends_win_even_when_none(self):
        item = SimpleNamespace(
            over_delivery_tolerance_percent=5.0, under_delivery_tolerance_percent=2.0
        )
        sent = self._command(
            over_delivery_tolerance_percent=None, under_delivery_tolerance_percent=1.0
        )
        kept = keep_unsent_tolerances(sent, item)
        assert kept.over_delivery_tolerance_percent is None
        assert kept.under_delivery_tolerance_percent == 1.0
