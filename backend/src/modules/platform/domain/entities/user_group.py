"""
A named bundle of permissions with its members. Every member holds the
group's permissions on top of their own direct grants, and since there are
only grants and no denials, a user's effective permissions are simply the
union of the two. Groups carry permissions only; nothing else is attached
to them.
"""

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime

from src.modules.platform.domain.entities.user import User
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class UserGroup(Entity):
    # ── Server-managed ────────────────────────────────────────────────
    created: datetime
    changed: datetime | None
    changes: list[str]

    # ── Core fields ───────────────────────────────────────────────────
    name: str
    description: str
    permissions: list[str]

    # ── Relations (FK ids only) ───────────────────────────────────────
    creator_id: int
    member_ids: list[int] = field(default_factory=list)

    # ── Denormalized (read-only, populated by repository mapper) ──────
    changed_by_id: int | None = None
    changed_by: User | None = None
