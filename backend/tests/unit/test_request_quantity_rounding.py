"""
A quantity enters the API rounded to the six decimals its NUMERIC column
stores, so the value a use case compares and writes is the value that reads
back, not one the database rounds later.
"""

import pytest
from pydantic import TypeAdapter

from src.modules.fulfillment.adapters.inbound.api.schemas.allocation_schema import (
    AllocationCreateRequest,
)
from src.modules.platform.adapters.inbound.api.schemas.quantity_fields import NonNegativeQuantity
from src.modules.platform.adapters.inbound.api.schemas.quantity_fields import PositiveQuantity
from src.modules.platform.adapters.inbound.api.schemas.quantity_fields import Quantity


@pytest.mark.parametrize(
    ("kind", "entered", "stored"),
    [
        (PositiveQuantity, 1.23456789, 1.234568),
        (PositiveQuantity, 2.0000004, 2.0),
        (NonNegativeQuantity, 7.4999996, 7.5),
        (Quantity, -3.1234567, -3.123457),
        (Quantity, 5.0, 5.0),
    ],
)
def test_a_quantity_is_rounded_to_the_stored_decimals(
    kind: object, entered: float, stored: float
) -> None:
    assert TypeAdapter(kind).validate_python(entered) == stored


def test_a_request_body_carries_the_rounded_quantity() -> None:
    parsed = AllocationCreateRequest.model_validate(
        {"demand_item_id": 1, "order_item_id": 2, "quantity": 4.0000006}
    )

    assert parsed.quantity == 4.000001
