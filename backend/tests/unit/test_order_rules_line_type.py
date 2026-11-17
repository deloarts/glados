"""
Unit tests for OrderRules.assert_valid_line_type: enforces
BOUGHT|MADE|SOURCE|VIRTUAL exclusivity at the domain-rule layer, mirroring
lot_rules.assert_valid_step_role in shape. Layer 1 (DB CHECK) and layer 3
(adapter DTO validator) are covered elsewhere; this is layer 2.
"""

from datetime import date

import pytest

from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.errors import OrderItemLineTypeMismatchError
from src.modules.fulfillment.domain.services.order_rules import OrderRules
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType


def make_item(
    *,
    line_type: OrderLineType,
    bought_item_id: int | None = None,
    source_item_id: int | None = None,
    lot_position_id: int | None = None,
    virtual_name: str | None = None,
) -> OrderItem:
    return OrderItem(
        id=1,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        status=OrderItemStatus.ORDERED,
        quantity=1.0,
        quantity_delivered=0.0,
        unit="pcs",
        items_per_unit=1.0,
        price=None,
        note=None,
        ordered_date=None,
        expected_delivery_date=None,
        delivery_date=None,
        storage_place=None,
        expected_pickup_date=None,
        ready_for_pickup_date=None,
        position=1,
        creator_id=1,
        orderer_id=None,
        receiver_id=None,
        bought_item_id=bought_item_id,
        order_id=1,
        supplier_id=1,
        project_id=1,
        line_type=line_type,
        lot_position_id=lot_position_id,
        source_item_id=source_item_id,
        virtual_name=virtual_name,
    )


# ── Valid shapes (one per line type) ────────────────────────────────────


class TestValidShapesAccepted:
    def test_bought_line_with_only_bought_item_id(self):
        item = make_item(line_type=OrderLineType.BOUGHT, bought_item_id=5)
        OrderRules.assert_valid_line_type(item)
        assert item.bought_item_id == 5
        assert item.source_item_id is None
        assert item.lot_position_id is None
        assert item.virtual_name is None

    def test_source_line_with_only_source_item_id(self):
        item = make_item(line_type=OrderLineType.SOURCE, source_item_id=7)
        OrderRules.assert_valid_line_type(item)
        assert item.source_item_id == 7
        assert item.bought_item_id is None
        assert item.lot_position_id is None
        assert item.virtual_name is None

    def test_made_line_with_only_lot_position_id(self):
        item = make_item(line_type=OrderLineType.MADE, lot_position_id=9)
        OrderRules.assert_valid_line_type(item)
        assert item.lot_position_id == 9
        assert item.bought_item_id is None
        assert item.source_item_id is None
        assert item.virtual_name is None

    def test_virtual_line_with_only_virtual_name(self):
        item = make_item(line_type=OrderLineType.VIRTUAL, virtual_name="Crating")
        OrderRules.assert_valid_line_type(item)
        assert item.virtual_name == "Crating"
        assert item.bought_item_id is None
        assert item.source_item_id is None
        assert item.lot_position_id is None


# ── Invalid shapes ───────────────────────────────────────────────────────


class TestInvalidShapesRejected:
    def test_bought_line_missing_bought_item_id(self):
        item = make_item(line_type=OrderLineType.BOUGHT)
        with pytest.raises(OrderItemLineTypeMismatchError, match="no bought_item_id"):
            OrderRules.assert_valid_line_type(item)

    def test_bought_line_with_both_bought_and_source(self):
        item = make_item(line_type=OrderLineType.BOUGHT, bought_item_id=1, source_item_id=2)
        with pytest.raises(OrderItemLineTypeMismatchError, match="source_item_id"):
            OrderRules.assert_valid_line_type(item)

    def test_source_line_missing_source_item_id(self):
        item = make_item(line_type=OrderLineType.SOURCE)
        with pytest.raises(OrderItemLineTypeMismatchError, match="no source_item_id"):
            OrderRules.assert_valid_line_type(item)

    def test_source_line_with_extra_virtual_name(self):
        item = make_item(line_type=OrderLineType.SOURCE, source_item_id=1, virtual_name="oops")
        with pytest.raises(OrderItemLineTypeMismatchError, match="virtual_name"):
            OrderRules.assert_valid_line_type(item)

    def test_made_line_missing_lot_position_id(self):
        item = make_item(line_type=OrderLineType.MADE)
        with pytest.raises(OrderItemLineTypeMismatchError, match="no lot_position_id"):
            OrderRules.assert_valid_line_type(item)

    def test_made_line_with_extra_bought_item_id(self):
        item = make_item(line_type=OrderLineType.MADE, lot_position_id=1, bought_item_id=2)
        with pytest.raises(OrderItemLineTypeMismatchError, match="bought_item_id"):
            OrderRules.assert_valid_line_type(item)

    def test_virtual_line_missing_virtual_name(self):
        item = make_item(line_type=OrderLineType.VIRTUAL)
        with pytest.raises(OrderItemLineTypeMismatchError, match="no virtual_name"):
            OrderRules.assert_valid_line_type(item)

    def test_virtual_line_with_empty_virtual_name(self):
        item = make_item(line_type=OrderLineType.VIRTUAL, virtual_name="")
        with pytest.raises(OrderItemLineTypeMismatchError, match="no virtual_name"):
            OrderRules.assert_valid_line_type(item)

    def test_virtual_line_with_extra_lot_position_id(self):
        item = make_item(line_type=OrderLineType.VIRTUAL, virtual_name="Crating", lot_position_id=1)
        with pytest.raises(OrderItemLineTypeMismatchError, match="lot_position_id"):
            OrderRules.assert_valid_line_type(item)

    def test_no_fk_set_at_all(self):
        item = make_item(line_type=OrderLineType.BOUGHT)
        with pytest.raises(OrderItemLineTypeMismatchError):
            OrderRules.assert_valid_line_type(item)

    def test_unknown_line_type(self):
        # A value outside the enum, which no mapper lets through, to show the
        # rule still refuses it.
        item = make_item(line_type="NONSENSE")  # type: ignore[arg-type]
        with pytest.raises(OrderItemLineTypeMismatchError, match="unknown line_type"):
            OrderRules.assert_valid_line_type(item)
