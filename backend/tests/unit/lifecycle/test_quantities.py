"""Unit tests for src/modules/platform/domain/services/quantities.py, the one
quantity tolerance of the lifecycle derivations."""

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from src.modules.fulfillment.domain.errors import InvalidDeliveryQuantityError
from src.modules.platform.domain.exceptions import FractionalPiecesError
from src.modules.platform.domain.services.quantities import QUANTITY_EPSILON
from src.modules.platform.domain.services.quantities import assert_finite
from src.modules.platform.domain.services.quantities import assert_whole_pieces
from src.modules.platform.domain.services.quantities import counts_whole_units
from src.modules.platform.domain.services.quantities import is_whole_quantity
from src.modules.platform.domain.services.quantities import is_zero_quantity
from src.modules.platform.domain.services.quantities import quantity_eq
from src.modules.platform.domain.services.quantities import quantity_ge
from src.modules.platform.domain.services.quantities import quantity_gt
from src.modules.platform.domain.services.quantities import snapped_to

finite = st.floats(allow_nan=False, allow_infinity=False, min_value=-1e9, max_value=1e9)


def test_quantity_tolerance_is_one_millionth():
    assert QUANTITY_EPSILON == 1e-6


def test_quantity_ge_accepts_fractional_deliveries_that_add_up():
    delivered = 0.7 + 0.2 + 0.1
    assert delivered < 1.0  # the rounding error the tolerance exists for
    assert quantity_ge(delivered, 1.0)


def test_quantity_eq_accepts_a_fractional_allocation_sum():
    assert 0.1 + 0.2 != 0.3
    assert quantity_eq(0.1 + 0.2, 0.3)


@pytest.mark.parametrize(
    ("value", "target", "expected"),
    [
        (1.0, 1.0, True),
        (2.0, 1.0, True),
        (1.0 - 1e-7, 1.0, True),
        (1.0 - QUANTITY_EPSILON, 1.0, True),
        (1.0 - 2e-6, 1.0, False),
        (0.0, 0.0, True),
        (999_999.999_999_5, 1e6, True),
        (999_999.99, 1e6, False),
    ],
)
def test_quantity_ge_reaches_the_target_within_the_tolerance(value, target, expected):
    assert quantity_ge(value, target) is expected


@pytest.mark.parametrize(
    ("value", "target", "expected"),
    [
        (2e-6, 0.0, True),
        (1e-7, 0.0, False),
        (0.0, 0.0, False),
        (1.0, 1.0, False),
        (1.0 + 2e-6, 1.0, True),
        (-1.0, 0.0, False),
    ],
)
def test_quantity_gt_needs_more_than_the_tolerance(value, target, expected):
    assert quantity_gt(value, target) is expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0.0, True), (-0.0, True), (1e-7, True), (-1e-7, True), (2e-6, False), (-2e-6, False)],
)
def test_is_zero_quantity_within_the_tolerance(value, expected):
    assert is_zero_quantity(value) is expected


def test_quantity_eq_holds_for_large_magnitudes():
    assert quantity_eq(1e6 + 1e-7, 1e6)
    assert not quantity_eq(1e6 + 1e-5, 1e6)


def test_quantity_helpers_never_hold_for_nan():
    nan = math.nan
    assert not quantity_ge(nan, 0.0)
    assert not quantity_ge(1.0, nan)
    assert not quantity_gt(nan, 0.0)
    assert not quantity_gt(1.0, nan)
    assert not quantity_eq(nan, nan)
    assert not is_zero_quantity(nan)


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_assert_finite_raises_the_callers_error(value):
    with pytest.raises(
        InvalidDeliveryQuantityError, match="Delivered quantity must be a finite number"
    ):
        assert_finite(value, error=InvalidDeliveryQuantityError, what="Delivered quantity")


@pytest.mark.parametrize("value", [0.0, -1.5, 1e9, 1e-9])
def test_assert_finite_accepts_finite_values(value):
    # A -> None validator: passing means it did not raise.
    assert_finite(value, error=InvalidDeliveryQuantityError, what="Delivered quantity")


@given(finite, finite)
def test_quantity_gt_is_the_complement_of_quantity_ge(a, b):
    assert quantity_gt(a, b) == (not quantity_ge(b, a))


@given(finite, finite)
def test_quantity_eq_is_symmetric(a, b):
    assert quantity_eq(a, b) == quantity_eq(b, a)


@given(finite)
def test_is_zero_quantity_is_equality_with_zero(value):
    assert is_zero_quantity(value) == quantity_eq(value, 0.0)


def test_a_sum_that_reaches_the_quantity_is_snapped_to_it():
    # 0.1 + 0.2 is 0.30000000000000004, above a quantity of 0.3, which the
    # exact CHECK on the production order's completed count refuses.
    assert snapped_to(0.1 + 0.2, 0.3) == 0.3


def test_a_value_is_snapped_to_the_first_target_it_agrees_with():
    assert snapped_to(1e-9, 0.0) == 0.0
    assert snapped_to(2.0 - 1e-9, 5.0, 2.0) == 2.0


def test_a_value_away_from_every_target_is_kept():
    assert snapped_to(0.25, 0.3, 0.0) == 0.25


@given(finite, finite)
def test_snapping_returns_the_target_or_the_value(value, target):
    snapped = snapped_to(value, target)
    assert snapped == (target if quantity_eq(value, target) else value)


@pytest.mark.parametrize("unit", ["PCS", "pcs", " Set ", "PAIR", "UNIT", "ROLL"])
def test_units_that_count_whole_things(unit):
    assert counts_whole_units(unit)


@pytest.mark.parametrize("unit", ["M", "KG", "L", "H", "M2", ""])
def test_units_that_measure(unit):
    assert not counts_whole_units(unit)


@pytest.mark.parametrize(
    ("value", "whole"),
    [(3.0, True), (0.1 * 3 * 10, True), (2.5, False), (math.nan, False), (math.inf, False)],
)
def test_is_whole_quantity(value, whole):
    assert is_whole_quantity(value) is whole


def test_pieces_without_a_unit_must_be_whole():
    with pytest.raises(FractionalPiecesError, match="The lot quantity must be a whole number"):
        assert_whole_pieces(2.5, what="The lot quantity")


def test_a_measured_unit_takes_fractions_and_a_counted_one_does_not():
    assert_whole_pieces(2.5, what="The demand quantity", unit="M")
    with pytest.raises(FractionalPiecesError):
        assert_whole_pieces(2.5, what="The demand quantity", unit="pcs")
