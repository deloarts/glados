"""
Domain entity for one admin settings audit log entry.

by_actor builds the unsaved entry a settings use case appends, stamped with
the current time and the acting user.
"""

from dataclasses import dataclass
from datetime import datetime

from src.modules.platform.domain.entities.user import User
from src.shared_kernel.domain.entities.base import Entity
from src.shared_kernel.domain.services.clock import now_utc


@dataclass
class AdminSettingsAuditEntry(Entity):
    """Immutable record of who changed which settings domain and when."""

    changed_at: datetime
    changed_by_id: int | None
    changed_by_username: str | None
    settings_domain: str  # host | mail | auth | storage | security | features | branding |
    # notifications | maintenance | retention | orders | made_items | production | banner |
    # pdm | time_tracking | stock
    summary: str

    @classmethod
    def by_actor(
        cls, actor: User, *, settings_domain: str, summary: str
    ) -> "AdminSettingsAuditEntry":
        """An unsaved entry recording that `actor` changed `settings_domain` now."""
        return cls(
            id=0,
            changed_at=now_utc(),
            changed_by_id=actor.id,
            changed_by_username=actor.username,
            settings_domain=settings_domain,
            summary=summary,
        )
