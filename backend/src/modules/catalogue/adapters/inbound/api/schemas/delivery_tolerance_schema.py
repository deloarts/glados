"""
The delivery tolerance fields a catalogue item's web form sends. They live
on the web requests only, so a pat client that updates an item without them
leaves the item's tolerances as they are. A tolerance is rounded to the
three decimals it is stored with, and its range is checked by the use case.
"""

from typing import Annotated

from pydantic import AfterValidator
from pydantic import BaseModel

from src.modules.catalogue.domain.services.item_delivery_tolerance_rules import TOLERANCE_DECIMALS


def _stored(value: float) -> float:
    return round(value, TOLERANCE_DECIMALS)


TolerancePercent = Annotated[float, AfterValidator(_stored)]


class DeliveryToleranceFields(BaseModel):
    """An item's own tolerances in percent; None takes the order settings'."""

    over_delivery_tolerance_percent: TolerancePercent | None = None
    under_delivery_tolerance_percent: TolerancePercent | None = None
