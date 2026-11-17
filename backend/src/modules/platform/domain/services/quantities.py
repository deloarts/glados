"""The one tolerance for comparing quantities.

Quantities are floats, and a sum of fractional deliveries or completions such
as 0.7 + 0.2 + 0.1 misses the exact total by a rounding error. Comparing
through these helpers lets a line, the demand it covers and the lot position
it feeds agree on whether a quantity is reached. The tolerance is absolute:
1e-6 is far below any quantity a user enters and far above the error of
summing a few of them. A NaN never compares true here, so a NaN quantity
never counts as reached or as positive.
"""

import math

from src.modules.platform.domain.exceptions import DomainError
from src.modules.platform.domain.exceptions import FractionalPiecesError

QUANTITY_EPSILON = 1e-6

# Every piece quantity is stored with six decimals and twelve integer digits
# (NUMERIC(18, 6)), rounded on its way in; storage_refusal names the values
# that this or the tolerance would turn into nothing, or that do not fit.
STORED_DECIMALS = 6
MAX_STORED_QUANTITY = 1e12

# The unit codes that count whole things; the others (lengths, areas, volumes,
# weights, hours) measure and take fractions.
COUNTED_UNITS = frozenset({"PCS", "UNIT", "SET", "PAIR", "ROLL"})


def quantity_ge(value: float, target: float) -> bool:
    """True when value reaches target within the tolerance."""
    return value >= target - QUANTITY_EPSILON


def quantity_gt(value: float, target: float) -> bool:
    """True when value exceeds target by more than the tolerance. For values
    that are not NaN this is exactly `not quantity_ge(target, value)`."""
    return target < value - QUANTITY_EPSILON


def quantity_eq(value: float, target: float) -> bool:
    """True when the two quantities differ by no more than the tolerance."""
    return abs(value - target) <= QUANTITY_EPSILON


def snapped_to(value: float, *targets: float) -> float:
    """The first target the value agrees with within the tolerance, else the
    value, so a sum of fractional bookings that reaches a quantity or zero
    is stored as exactly that and an exact CHECK on the column holds."""
    return next((target for target in targets if quantity_eq(value, target)), value)


def is_zero_quantity(value: float) -> bool:
    """True when value is zero within the tolerance."""
    return abs(value) <= QUANTITY_EPSILON


def assert_finite(value: float, *, error: type[DomainError], what: str) -> None:
    """Raises `error` when value is NaN or infinite, since every comparison
    with NaN is false and such a quantity would slip past each guard. The
    caller passes its own error class, which already maps to an HTTP status,
    and names the quantity in `what`."""
    if not math.isfinite(value):
        raise error(f"{what} must be a finite number, got {value!r}.")


def counts_whole_units(unit: str) -> bool:
    """True when the unit counts whole things, compared without case and
    surrounding spaces, so "pcs" and " PCS" count as well."""
    return unit.strip().upper() in COUNTED_UNITS


def is_whole_quantity(value: float) -> bool:
    """True when the value is a whole number within the tolerance; never
    for NaN or infinity."""
    return math.isfinite(value) and quantity_eq(value, round(value))


def assert_whole_pieces(value: float, *, what: str, unit: str | None = None) -> None:
    """Raises FractionalPiecesError when the value is not a whole number and
    counts pieces: always without `unit`, else when the unit counts whole
    things."""
    if unit is not None and not counts_whole_units(unit):
        return
    if not is_whole_quantity(value):
        raise FractionalPiecesError(f"{what} must be a whole number, got {value:g}.")


def storage_refusal(value: float) -> str | None:
    """Why a finite quantity cannot be stored as entered, if it cannot: a
    value other than zero whose stored size is within QUANTITY_EPSILON of
    zero, which the columns would round to zero or every comparison here
    would take for nothing, so a demand of it would read fulfilled, or one
    whose rounded size reaches MAX_STORED_QUANTITY."""
    stored = round(value, STORED_DECIMALS)
    if value != 0 and abs(stored) <= QUANTITY_EPSILON:
        return (
            f"A quantity needs more than {QUANTITY_EPSILON:.6f}; a smaller one would count "
            "as nothing."
        )
    if abs(stored) >= MAX_STORED_QUANTITY:
        return f"A quantity must be below {MAX_STORED_QUANTITY:.0f}."
    return None
