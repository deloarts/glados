"""
Request and response of the key surface's RFID lookup. The tag travels in
the body, so it never lands in an access log, a proxy log or the request
log the way a URL path does.
"""

from pydantic import BaseModel
from pydantic import Field

from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse


class RfidLookupRequest(BaseModel):
    # Enrolment refuses a tag shorter than eight characters, so no shorter
    # value can match.
    rfid: str = Field(..., min_length=8, max_length=255)


class RfidIdentityResponse(EntityResponse):
    """Who the tag belongs to, see RfidIdentityResult."""

    username: str
    full_name: str
