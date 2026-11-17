"""
Mirrors webhook_schema.py's shape: the outbound *Result DTOs are reused
directly as response models (ResultBase/BaseModel already give FastAPI
everything it needs), only the two request bodies get their own schema
here.
"""

from pydantic import BaseModel
from pydantic import Field

from src.modules.platform.application.dto.acknowledgement_dto import AcknowledgementRecipientResult
from src.modules.platform.application.dto.acknowledgement_dto import AcknowledgementSummaryResult
from src.modules.platform.application.dto.acknowledgement_dto import MyAnnouncementsResult
from src.modules.platform.domain.value_objects.acknowledgement_show_when import (
    AcknowledgementShowWhen,
)
from src.modules.platform.domain.value_objects.announcement_severity import AnnouncementSeverity

__all__ = [
    "AcknowledgementRecipientResult",
    "AcknowledgementSummaryResult",
    "CreateAcknowledgementRequest",
    "MyAnnouncementsResult",
    "SetAcknowledgementEnabledRequest",
]


class CreateAcknowledgementRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    severity: AnnouncementSeverity
    enabled: bool
    show_when: AcknowledgementShowWhen
    recipient_ids: list[int] = Field(..., min_length=1)


class SetAcknowledgementEnabledRequest(BaseModel):
    enabled: bool
