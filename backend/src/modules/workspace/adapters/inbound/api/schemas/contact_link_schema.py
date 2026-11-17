"""
HTTP schemas for the contact links of products and projects and the usage
of contacts. A link embeds Catalogue's contact summary.
"""

from pydantic import BaseModel

from src.modules.catalogue.adapters.inbound.api.schemas.contact_schema import ContactSummaryResponse
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel
from src.modules.workspace.domain.value_objects.contact_link_owner import ContactLinkOwner

# ── Request schemas ───────────────────────────────────────────────────


class ContactLinkCreateRequest(BaseModel):
    contact_id: int
    receives_meeting_notes: bool = True


class ContactLinkUpdateRequest(BaseModel):
    receives_meeting_notes: bool


# ── Response schemas ──────────────────────────────────────────────────


class ProductContactResponse(ResponseModel):
    contact: ContactSummaryResponse
    receives_meeting_notes: bool


class ProjectContactResponse(ResponseModel):
    contact: ContactSummaryResponse
    # Linked by the project's product, so the project cannot unlink it, only
    # set its flag for itself.
    inherited: bool
    # What applies to the project.
    receives_meeting_notes: bool
    # The product's flag of an inherited contact, None for the project's own.
    product_receives_meeting_notes: bool | None
    # An inherited contact whose flag the project set for itself.
    overridden: bool


class ContactUsageRecordResponse(ResponseModel):
    owner: ContactLinkOwner
    id: int
    number: str
    receives_meeting_notes: bool


class ContactUsageMeetingResponse(ResponseModel):
    id: int
    meeting_number: str
    name: str


class ContactUsageResponse(ResponseModel):
    contact_id: int
    products: list[ContactUsageRecordResponse]
    projects: list[ContactUsageRecordResponse]
    # The meetings the contact attends or owns todos in, latest first.
    meetings: list[ContactUsageMeetingResponse]
