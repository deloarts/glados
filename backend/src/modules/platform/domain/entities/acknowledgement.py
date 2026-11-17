"""
Pure domain entities for the acknowledgements feature: an admin-authored
message every selected user must confirm in a dialog they cannot dismiss.
No SQLAlchemy, no Pydantic.
"""

from dataclasses import dataclass
from datetime import datetime

from src.modules.platform.domain.value_objects.acknowledgement_show_when import (
    AcknowledgementShowWhen,
)
from src.modules.platform.domain.value_objects.announcement_severity import AnnouncementSeverity
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class Acknowledgement(Entity):
    """The message itself. Text, severity, show_when and the recipient
    list are immutable after creation, since a changed text would invalidate
    confirmations already given. Only `enabled` may ever change again
    (SetAcknowledgementEnabled); an admin who wants different wording
    creates a new acknowledgement instead."""

    text: str
    severity: AnnouncementSeverity
    enabled: bool
    show_when: AcknowledgementShowWhen
    created_at: datetime
    created_by_id: int | None  # FK users, SET NULL once the creator account is deleted


@dataclass
class AcknowledgementRecipient:
    """One user's confirmation state for one acknowledgement: a join-table
    row, not an aggregate root of its own. The natural key is
    (acknowledgement_id, user_id), see the ORM model's composite primary
    key. Does not extend Entity, it has no independent int id."""

    acknowledgement_id: int
    user_id: int
    acknowledged_at: datetime | None
