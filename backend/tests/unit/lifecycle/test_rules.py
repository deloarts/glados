"""Unit tests for src/modules/fulfillment/domain/services/lifecycle/rules.py: how a derivation
table evaluates its rows, and the checks its construction makes."""

from dataclasses import dataclass

import pytest

from src.modules.fulfillment.domain.services.lifecycle.demand import BOUGHT_DEMAND_STATUS
from src.modules.fulfillment.domain.services.lifecycle.demand import MADE_DEMAND_STATUS
from src.modules.fulfillment.domain.services.lifecycle.demand import SOURCE_DEMAND_STATUS
from src.modules.fulfillment.domain.services.lifecycle.lot import LOT_STATUS
from src.modules.fulfillment.domain.services.lifecycle.lot_position import POSITION_KIND
from src.modules.fulfillment.domain.services.lifecycle.lot_position import POSITION_STATUS
from src.modules.fulfillment.domain.services.lifecycle.order import ORDER_STATUS
from src.modules.fulfillment.domain.services.lifecycle.order_item import ORDER_ITEM_STATUS
from src.modules.fulfillment.domain.services.lifecycle.production_order import (
    PRODUCTION_ORDER_STATUS,
)
from src.modules.fulfillment.domain.services.lifecycle.rules import OTHERWISE
from src.modules.fulfillment.domain.services.lifecycle.rules import Derivation
from src.modules.fulfillment.domain.services.lifecycle.rules import DerivationRule
from src.modules.fulfillment.domain.services.lifecycle.rules import DerivationTable
from src.modules.fulfillment.domain.services.lifecycle.rules import otherwise
from src.modules.fulfillment.domain.services.lifecycle.rules import rule
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus

ALL_TABLES = [
    ORDER_ITEM_STATUS,
    ORDER_STATUS,
    PRODUCTION_ORDER_STATUS,
    POSITION_KIND,
    POSITION_STATUS,
    LOT_STATUS,
    BOUGHT_DEMAND_STATUS,
    MADE_DEMAND_STATUS,
    SOURCE_DEMAND_STATUS,
]


@dataclass(frozen=True)
class _Facts:
    a: bool
    b: bool


def _table() -> DerivationTable[_Facts, OrderStatus]:
    return DerivationTable(
        key="sample",
        rules=(
            rule(1, "a", OrderStatus.CANCELED, lambda f: f.a),
            rule(2, "b", OrderStatus.ORDERED, lambda f: f.b),
        ),
        fallback=otherwise(3, OrderStatus.DRAFT),
    )


def test_derive_first_matching_row_wins():
    assert _table().derive(_Facts(a=True, b=True)) == Derivation(OrderStatus.CANCELED, 1)


def test_derive_later_row_when_earlier_rows_do_not_apply():
    assert _table().derive(_Facts(a=False, b=True)) == Derivation(OrderStatus.ORDERED, 2)


def test_derive_falls_back_when_no_row_applies():
    assert _table().derive(_Facts(a=False, b=False)) == Derivation(OrderStatus.DRAFT, 3)


def test_rows_lists_the_fallback_last():
    assert [row.number for row in _table().rows] == [1, 2, 3]
    assert _table().rows[-1].condition == OTHERWISE


def test_rule_describes_a_constant_result_by_its_value():
    row = rule(1, "a", OrderStatus.CANCELED, lambda f: True)
    assert row.result == "canceled"
    assert row.results == (OrderStatus.CANCELED,)
    assert row.outcome(object()) is OrderStatus.CANCELED


def test_derive_uses_a_computed_outcome():
    computed = DerivationRule[_Facts, OrderStatus](
        number=1,
        condition="a",
        result="ordered if b, else requested",
        results=(OrderStatus.ORDERED, OrderStatus.REQUESTED),
        applies=lambda f: f.a,
        outcome=lambda f: OrderStatus.ORDERED if f.b else OrderStatus.REQUESTED,
    )
    table = DerivationTable(
        key="computed", rules=(computed,), fallback=otherwise(2, OrderStatus.DRAFT)
    )
    assert table.derive(_Facts(a=True, b=False)) == Derivation(OrderStatus.REQUESTED, 1)
    assert table.derive(_Facts(a=True, b=True)) == Derivation(OrderStatus.ORDERED, 1)


def test_table_rejects_rows_out_of_order():
    with pytest.raises(ValueError, match="numbered from 1 in order"):
        DerivationTable(
            key="gap",
            rules=(rule(1, "a", OrderStatus.CANCELED, lambda f: True),),
            fallback=otherwise(3, OrderStatus.DRAFT),
        )


def test_table_rejects_a_conditional_row_as_fallback():
    with pytest.raises(ValueError, match="must be the fallback row"):
        DerivationTable(
            key="no_fallback",
            rules=(rule(1, "a", OrderStatus.CANCELED, lambda f: True),),
            fallback=rule(2, "b", OrderStatus.DRAFT, lambda f: True),
        )


@pytest.mark.parametrize("table", ALL_TABLES, ids=lambda t: t.key)
def test_lifecycle_table_rows_are_numbered_and_described(table):
    assert [row.number for row in table.rows] == list(range(1, len(table.rows) + 1))
    assert table.rows[-1].condition == OTHERWISE
    for row in table.rows:
        assert row.condition
        assert row.result
        assert row.results


def test_lifecycle_table_keys_are_unique():
    keys = [table.key for table in ALL_TABLES]
    assert len(keys) == len(set(keys))
