"""
The manufacturer's product family of a bought item, such as cylinders or
valves, for quick filtering. Unlike article groups, which are Glados' own
purchasing classification and allow several per item, an item belongs to at
most one product family. Server-managed metadata (created, changed,
archived) and audit trail.
"""

from dataclasses import dataclass
from datetime import datetime

from src.modules.platform.domain.entities.user import User
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class ProductFamily(Entity):
    # ── Server-managed ────────────────────────────────────────────────
    created: datetime
    changed: datetime
    changes: list[str]
    archived: bool

    # ── Core fields ───────────────────────────────────────────────────
    name: str
    label_color: str
    label_font_color: str
    description: str

    # ── Audit ─────────────────────────────────────────────────────────
    creator_id: int
    creator: User | None = None
    changed_by_id: int | None = None
    changed_by: User | None = None

    # Position in the hand-kept order pickers offer the families in, moved one
    # place at a time from the resources section (shared_kernel list_order).
    sort_order: int = 0
