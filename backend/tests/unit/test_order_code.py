"""tests/unit/test_order_code.py: the comparison form of an order code."""

import pytest

from src.modules.catalogue.domain.policies.order_code import normalize_order_code


@pytest.mark.parametrize(
    "raw",
    ["3RT2015-1BB41", "3RT20151BB41", " 3rt2015 1bb41 ", "3RT.2015/1BB_41", "3RT2015\t-1BB41"],
)
def test_order_code_normalize_ignores_case_whitespace_and_separators(raw: str) -> None:
    assert normalize_order_code(raw) == "3rt20151bb41"


def test_order_code_normalize_of_nothing_is_empty() -> None:
    assert normalize_order_code(None) == ""
    assert normalize_order_code(" - ") == ""
