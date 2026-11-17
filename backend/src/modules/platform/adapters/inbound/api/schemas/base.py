"""
Shared building blocks for the API schemas. `ResponseModel` is the base of
every outbound schema, and `EntityResponse` adds the identity fields for
the "*Response" schemas that represent a single persisted row; neither is
for request schemas. `NonBlankReason` is the
reason field type of request schemas that refuse a whitespace-only reason.
`expand_change_window` turns the created and changed date window of a
filter into UTC datetime bounds, reading its days in the tenant's timezone.
"""

from datetime import tzinfo
from typing import Annotated
from typing import Any
from uuid import UUID

from pydantic import AfterValidator
from pydantic import BaseModel
from pydantic import ConfigDict

from src.modules.platform.domain.services.datetime_filters import expand_date_filter


class ResponseModel(BaseModel):
    """Base of every response schema. A response always carries each of its
    fields, defaulted ones included, so the serialization JSON schema lists
    them all as required and the generated frontend types need no override
    to read them. Request schemas keep `BaseModel`, where a defaulted field
    stays optional for the client."""

    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class EntityResponse(ResponseModel):
    id: int
    public_id: UUID

    model_config = {"from_attributes": True}


def _strip_reason(value: str) -> str:
    """Trim the reason, so that one of only whitespace is refused with 422
    like an empty one. A ValueError raised in a Pydantic validator becomes
    a 422, whereas a DomainError raised later would need its own handler."""
    value = value.strip()
    if not value:
        raise ValueError("reason must not be blank.")
    return value


# A free-text reason that is trimmed and must not be blank. Length limits
# stay on the field's own Field(), since they differ per request.
NonBlankReason = Annotated[str, AfterValidator(_strip_reason)]


# The created and changed window fields of a list filter, each paired with
# whether a date-only value stands for the end of its day.
_CHANGE_WINDOW_FIELDS = (
    ("created_from", False),
    ("created_to", True),
    ("changed_from", False),
    ("changed_to", True),
)


def expand_change_window(data: dict[str, Any], zone: tzinfo) -> dict[str, Any]:
    """Expand the `created_from`, `created_to`, `changed_from` and
    `changed_to` values of a dumped filter into UTC datetime bounds in
    place, reading a date-only value as a day in `zone`, the tenant's
    timezone. Unset values stay None. Returns `data` for chaining into the
    DTO."""
    for field, end_of_day in _CHANGE_WINDOW_FIELDS:
        if data[field] is not None:
            data[field] = expand_date_filter(data[field], zone, end_of_day=end_of_day)
    return data
