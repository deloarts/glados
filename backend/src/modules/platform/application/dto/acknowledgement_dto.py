"""
Input commands and output results for the acknowledgements feature (admin
CRUD) and the user-facing /announcements surface built on top of it.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import Field

from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.application.dto.base import ResultModel
from src.modules.platform.domain.value_objects.acknowledgement_show_when import (
    AcknowledgementShowWhen,
)
from src.modules.platform.domain.value_objects.announcement_severity import AnnouncementSeverity

# ── Admin CRUD ───────────────────────────────────────────────────────────


class CreateAcknowledgementCommand(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    severity: AnnouncementSeverity
    enabled: bool
    show_when: AcknowledgementShowWhen
    recipient_ids: list[int] = Field(..., min_length=1)


class AcknowledgementSummaryResult(ResultBase):
    """An acknowledgement as the admin list shows it, also returned by create
    and by the enabled toggle. `created_by_username` is null once the
    creator's account has been deleted."""

    text: str
    severity: AnnouncementSeverity
    enabled: bool
    show_when: AcknowledgementShowWhen
    created_at: datetime
    created_by_username: str | None
    recipients_total: int
    recipients_acknowledged: int


class AcknowledgementRecipientResult(ResultModel):
    user_id: int
    username: str
    full_name: str
    acknowledged_at: datetime | None


# ── User-facing (/announcements) ─────────────────────────────────────────


class MyAnnouncementsBannerResult(ResultModel):
    """The banner for signed-in users, present only while it is enabled and
    has text. The client decides whether to show it against `shows_from`
    and `shows_until`."""

    text: str
    severity: AnnouncementSeverity
    shows_from: datetime | None
    shows_until: datetime | None
    dismissable: bool
    updated_at: datetime


class PendingAcknowledgementResult(ResultModel):
    public_id: UUID
    text: str
    severity: AnnouncementSeverity
    created_at: datetime


class MyAnnouncementsResult(ResultModel):
    banner: MyAnnouncementsBannerResult | None
    pending_acknowledgements: list[PendingAcknowledgementResult]  # oldest first
