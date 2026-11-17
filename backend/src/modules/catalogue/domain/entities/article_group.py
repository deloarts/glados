"""
Grouping/categorization for bought items, used for filtering and
organization. Server-managed metadata (created, changed, archived) and audit
trail.
"""

from dataclasses import dataclass
from datetime import datetime

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class ArticleGroup(Entity):
    # ── Server-managed ────────────────────────────────────────────────
    created: datetime
    changed: datetime
    changes: list[str]
    archived: bool

    # ── Core fields ───────────────────────────────────────────────────
    name: LocalizedText
    label_color: str
    label_font_color: str
    description: LocalizedText

    # ── Audit ─────────────────────────────────────────────────────────
    creator_id: int
    creator: User | None = None
    changed_by_id: int | None = None
    changed_by: User | None = None

    # Position in the hand-kept order pickers offer the groups in, moved one
    # place at a time from the resources section (shared_kernel list_order).
    sort_order: int = 0
