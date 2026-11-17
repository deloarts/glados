"""
`ResultModel` is the base of the outbound DTOs that a route also returns
as its response model. `ResultBase` adds the identity fields for "*Result"
DTOs that represent a single persisted row. Neither is for commands
(inbound).
"""

from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict


class ResultModel(BaseModel):
    """Base of the DTOs a route returns as its response model. A result
    always carries each of its fields, defaulted ones included, so the
    serialization JSON schema lists them all as required."""

    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class ResultBase(ResultModel):
    id: int
    public_id: UUID

    model_config = {"from_attributes": True}
