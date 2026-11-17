"""
The document control fields every result of a controlled document carries
(see src/modules/quality/domain/entities/controlled_document.py).
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from src.modules.platform.application.dto.base import ResultBase


class ControlledDocumentResult(ResultBase):
    created: datetime
    changed: datetime | None
    creator_id: int
    creator_full_name: str
    document_number: str
    lineage: UUID
    revision: str
    revision_reason: str | None
    is_latest: bool
    superseded_at: datetime | None
    # Released or superseded, so it cannot change any more.
    read_only: bool
    # Who saved the last change, the person `changed` belongs to.
    changed_by_id: int | None
    changed_by_full_name: str | None
    released_at: datetime | None
    released_by_id: int | None
    released_by_full_name: str | None
    invalid_at: datetime | None
    invalid_by_id: int | None
    invalid_by_full_name: str | None
    invalid_reason: str | None
    # Who edits the document right now; empty once the lock has run out.
    locked_by_id: int | None
    locked_by_full_name: str | None
    locked_at: datetime | None
    lock_expires_at: datetime | None


class MarkInvalidCommand(BaseModel):
    reason: str


class LockCommand(BaseModel):
    # Take the lock over from another editor, which needs the kind's manage
    # permission; without it a live lock of someone else is refused.
    take_over: bool = False
