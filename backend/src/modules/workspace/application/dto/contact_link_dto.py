"""
Results of the contact link use cases of products and projects, and the
usage of contacts across products and projects.
"""

from pydantic import BaseModel

from src.modules.catalogue.application.dto.contact_dto import ContactSummaryResult
from src.modules.platform.application.dto.base import ResultModel
from src.modules.workspace.domain.value_objects.contact_link_owner import ContactLinkOwner

# ── Commands (inbound) ────────────────────────────────────────────────


class LinkContactCommand(BaseModel):
    contact_id: int
    receives_meeting_notes: bool = True


# ── Results (outbound) ────────────────────────────────────────────────


class ProductContactResult(ResultModel):
    contact: ContactSummaryResult
    receives_meeting_notes: bool


class ProjectContactResult(ResultModel):
    contact: ContactSummaryResult
    # Linked by the project's product rather than the project itself.
    inherited: bool
    # What applies to the project: its own flag, or for an inherited contact
    # the project's override if it has one, else the product's flag.
    receives_meeting_notes: bool
    # The product's flag of an inherited contact, None for the project's own.
    product_receives_meeting_notes: bool | None
    # An inherited contact whose flag the project set for itself.
    overridden: bool


class ContactUsageRecordResult(ResultModel):
    owner: ContactLinkOwner
    id: int
    number: str
    receives_meeting_notes: bool


class ContactUsageMeetingResult(ResultModel):
    id: int
    meeting_number: str
    name: str


class ContactUsageResult(ResultModel):
    """Where a contact is used in Workspace: the products and projects that
    link it and the meetings it attends or owns todos in. Records that link
    contacts later add a list of their own here."""

    contact_id: int
    products: list[ContactUsageRecordResult]
    projects: list[ContactUsageRecordResult]
    meetings: list[ContactUsageMeetingResult]
