"""
The extra cost rules: an amount above zero, a label where the kind needs
one, a line of the document, the totals with a discount subtracted and the
line total over the priced lines that are not canceled.
"""

import pytest

from src.modules.fulfillment.domain.errors import ExtraCostInvalidError
from src.modules.fulfillment.domain.services.extra_cost_rules import ExtraCostDraft
from src.modules.fulfillment.domain.services.extra_cost_rules import PricedLine
from src.modules.fulfillment.domain.services.extra_cost_rules import assert_valid_extra_costs
from src.modules.fulfillment.domain.services.extra_cost_rules import describe_extra_cost_change
from src.modules.fulfillment.domain.services.extra_cost_rules import extra_costs_total
from src.modules.fulfillment.domain.services.extra_cost_rules import lines_total
from src.modules.fulfillment.domain.services.extra_cost_rules import net_total
from src.modules.fulfillment.domain.value_objects.extra_cost_kind import ExtraCostKind


def test_extra_costs_valid_list_passes() -> None:
    assert_valid_extra_costs(
        [
            ExtraCostDraft(kind=ExtraCostKind.SHIPPING, amount=1500),
            ExtraCostDraft(kind=ExtraCostKind.SETUP, amount=900, line_id=7),
            ExtraCostDraft(kind=ExtraCostKind.OTHER, amount=100, label="Pallet deposit"),
        ],
        {7},
    )


@pytest.mark.parametrize(
    "draft",
    [
        ExtraCostDraft(kind=ExtraCostKind.SHIPPING, amount=0),
        ExtraCostDraft(kind=ExtraCostKind.OTHER, amount=100),
        ExtraCostDraft(kind=ExtraCostKind.OTHER, amount=100, label="   "),
        ExtraCostDraft(kind=ExtraCostKind.PACKAGING, amount=100, label="x" * 121),
        ExtraCostDraft(kind=ExtraCostKind.SETUP, amount=100, line_id=8),
    ],
)
def test_extra_costs_invalid_cost_is_refused(draft: ExtraCostDraft) -> None:
    with pytest.raises(ExtraCostInvalidError):
        assert_valid_extra_costs([draft], {7})


def test_extra_costs_total_subtracts_a_discount() -> None:
    assert extra_costs_total([("shipping", 1500), ("discount", 300), ("customs", 200)]) == 1400


def test_extra_costs_lines_total_counts_priced_live_lines() -> None:
    total = lines_total(
        [
            PricedLine(price=250, quantity=4),
            PricedLine(price=None, quantity=3),
            PricedLine(price=1000, quantity=2, canceled=True),
            PricedLine(price=33, quantity=1.5),
        ]
    )

    assert total == 1050


def test_extra_costs_totals_stay_empty_without_prices_or_costs() -> None:
    assert lines_total([PricedLine(price=None, quantity=2)]) is None
    assert net_total(None, 0, has_costs=False) is None
    assert net_total(None, 1500, has_costs=True) == 1500
    assert net_total(1000, -300, has_costs=True) == 700


def test_extra_costs_change_is_described_only_when_something_changed() -> None:
    same = [("shipping", 1500, None, None, None)]

    assert describe_extra_cost_change(same, same) is None
    assert describe_extra_cost_change(same, []) == "Extra costs removed."
    assert (
        describe_extra_cost_change(
            [], [("shipping", 1500, None, None, None), ("discount", 300, None, None, None)]
        )
        == "Extra costs set: shipping 15.00 EUR, discount -3.00 EUR."
    )
