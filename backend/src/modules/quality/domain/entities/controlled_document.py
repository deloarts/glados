"""
The document control every record shares that a PDF report can describe,
such as a calculation or a checklist, the way ISO 9001 7.5.3 asks for it:

- Revisions. All revisions of one document share a lineage and a document
  number, and exactly one of them is the latest. Only the latest revision can change, and only while
  it is a draft.
- Release. A released revision never changes again; a correction is a new
  revision. Releasing a later revision supersedes the one before it.
- Invalid. A released revision found to be wrong is marked invalid with a
  reason instead of losing its release, so what was signed off stays on
  record.
- Edit lock. One person edits a draft at a time and only that person
  saves it. The lock is a lease that runs out after a while without
  activity, so a closed browser does not block the document for good, and
  a manager can end it.
- Retention. A released revision is never deleted; only drafts are.

The rules that act on these fields live in services/document_control.py.
"""

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from uuid import UUID
from uuid import uuid4

from src.shared_kernel.domain.entities.base import Entity


@dataclass(kw_only=True)
class ControlledDocument(Entity):
    # ── Server-managed ────────────────────────────────────────────────
    created: datetime
    changed: datetime | None
    changes: list[str]
    creator_id: int  # → User, the author of this revision

    # ── Revision ──────────────────────────────────────────────────────
    # The readable number every revision of the document shares, such as
    # "CAL-26-0042"; quoted with the revision, "CAL-26-0042 rev. B".
    document_number: str = ""
    # A new document is the first revision of a lineage of its own.
    lineage: UUID = field(default_factory=uuid4)
    revision: str = "A"
    revision_reason: str | None = None
    is_latest: bool = True
    # Set once a newer revision has taken over as the valid one.
    superseded_at: datetime | None = None

    # ── Release ───────────────────────────────────────────────────────
    # Who saved the last change, the person `changed` belongs to.
    changed_by_id: int | None = None  # → User
    released_at: datetime | None = None
    released_by_id: int | None = None  # → User

    # ── Invalid ───────────────────────────────────────────────────────
    invalid_at: datetime | None = None
    invalid_by_id: int | None = None  # → User
    invalid_reason: str | None = None

    # ── Edit lock ─────────────────────────────────────────────────────
    locked_by_id: int | None = None  # → User
    locked_at: datetime | None = None
    lock_expires_at: datetime | None = None

    # Everyone who saved changes into this revision, besides its creator.
    editor_ids: list[int] = field(default_factory=list)

    # ── Denormalized (read-only, populated by repository mapper) ──────
    creator_full_name: str = ""
    released_by_full_name: str | None = None
    changed_by_full_name: str | None = None
    invalid_by_full_name: str | None = None
    locked_by_full_name: str | None = None

    @property
    def is_released(self) -> bool:
        return self.released_at is not None

    @property
    def is_invalid(self) -> bool:
        return self.invalid_at is not None

    @property
    def read_only(self) -> bool:
        return self.is_released or not self.is_latest

    def lock_holder_id(self, now: datetime) -> int | None:
        """Who holds the edit lock at `now`, or None once the lease has run out."""
        if self.locked_by_id is None or self.lock_expires_at is None:
            return None
        return self.locked_by_id if self.lock_expires_at > now else None
