"""
The valid range of a delivery tolerance, the percentage a delivery may go
beyond or stay below the ordered quantity. The order settings hold the
global tolerances and a catalogue item may hold its own; both are checked
here before they are stored.
"""

from src.modules.catalogue.domain.errors import DeliveryToleranceInvalidError
from src.modules.platform.domain.services.quantities import assert_finite

MAX_TOLERANCE_PERCENT = 100.0
# A tolerance is stored as NUMERIC(7, 3), so the requests round it to three
# decimals and a use case compares what reads back.
TOLERANCE_DECIMALS = 3


def assert_valid_tolerance(value: float | None, *, what: str) -> None:
    """Refuses a tolerance that is not a finite percentage from 0 to 100.
    None, an item that takes the global value, passes."""
    if value is None:
        return
    assert_finite(value, error=DeliveryToleranceInvalidError, what=what)
    if value < 0 or value > MAX_TOLERANCE_PERCENT:
        raise DeliveryToleranceInvalidError(
            f"{what} must be between 0 and {MAX_TOLERANCE_PERCENT:.0f} percent, got {value!r}."
        )
