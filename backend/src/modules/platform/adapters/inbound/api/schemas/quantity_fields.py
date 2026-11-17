"""
The quantity fields of the web requests. Every piece quantity is stored as
NUMERIC(18, 6) and compared within 0.000001, so a field rounds the value to
those six decimals on its way in, and the use case compares and writes what
reads back. A value of 0.000001 or less would count as nothing, a demand of
it reading back fulfilled, and a value of 10**12 or more does not fit the
column. Both are refused with 422 before a use case runs
(domain/services/quantities.storage_refusal), as is a value that is not finite.
Whether a quantity must be a whole number is a domain rule
(docs/reference/backend-conventions.md section 5).
"""

from typing import Annotated

from pydantic import AfterValidator
from pydantic import Field

from src.modules.platform.domain.services.quantities import MAX_STORED_QUANTITY
from src.modules.platform.domain.services.quantities import STORED_DECIMALS
from src.modules.platform.domain.services.quantities import storage_refusal


def _storable(value: float) -> float:
    refusal = storage_refusal(value)
    if refusal is not None:
        raise ValueError(refusal)
    return round(value, STORED_DECIMALS)


# A finite quantity of either sign, such as a part of a split, whose sign
# the use case checks.
Quantity = Annotated[
    float,
    Field(allow_inf_nan=False, gt=-MAX_STORED_QUANTITY, lt=MAX_STORED_QUANTITY),
    AfterValidator(_storable),
]
PositiveQuantity = Annotated[
    float, Field(allow_inf_nan=False, gt=0, lt=MAX_STORED_QUANTITY), AfterValidator(_storable)
]
NonNegativeQuantity = Annotated[
    float, Field(allow_inf_nan=False, ge=0, lt=MAX_STORED_QUANTITY), AfterValidator(_storable)
]
