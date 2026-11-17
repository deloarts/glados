"""
Domain entity for the signed-in banner settings singleton.
"""

from dataclasses import dataclass
from datetime import datetime

from src.modules.platform.domain.value_objects.announcement_severity import AnnouncementSeverity
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class AdminBannerSettings(Entity):
    """A dismissable, signed-in-only banner shown above the app header.

    `text` is "" when never set. `shows_from` and `shows_until` are UTC
    instants (None is open-ended) that the frontend evaluates; the API passes
    them through. `updated_at` is bumped on every save, even one that changes
    nothing, because the frontend keys its per-browser dismissal on it, so a
    re-saved banner reappears. `dismissable` only decides whether a close
    button is shown.
    """

    enabled: bool
    text: str
    severity: AnnouncementSeverity
    shows_from: datetime | None
    shows_until: datetime | None
    dismissable: bool
    updated_at: datetime
