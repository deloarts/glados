"""
Which portal number becomes order code 1 and which order code 2: the order
number first by default, the type number first for a manufacturer that
names its parts that way, and a second code only when it differs.
"""

from src.modules.external_data.application.services.edp_item_draft import order_codes
from src.modules.external_data.domain.value_objects.eplan_data_portal import EdpPart


def _part(order: str | None, type_number: str | None) -> EdpPart:
    return EdpPart(part_id=1, part_number="FES.170851", order_number=order, type_number=type_number)


def test_order_number_comes_first_by_default() -> None:
    assert order_codes(_part("170851", "DFM-25-50-P-A-GF"), False) == (
        "170851",
        "DFM-25-50-P-A-GF",
    )


def test_type_number_comes_first_when_the_manufacturer_says_so() -> None:
    assert order_codes(_part("170851", "DFM-25-50-P-A-GF"), True) == (
        "DFM-25-50-P-A-GF",
        "170851",
    )


def test_a_part_without_a_type_number_keeps_its_order_number_first() -> None:
    assert order_codes(_part("170851", None), True) == ("170851", None)


def test_the_second_code_is_dropped_when_it_is_the_same_code() -> None:
    assert order_codes(_part("3RT2015-1BB41", "3RT20151BB41"), False) == ("3RT2015-1BB41", None)
    assert order_codes(_part("3RT2015-1BB41", "3RT20151BB41"), True) == ("3RT20151BB41", None)
