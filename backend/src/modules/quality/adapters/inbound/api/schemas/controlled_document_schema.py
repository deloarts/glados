"""
Wire fields shared by every controlled document, such as calculations and
checklists: the document control fields of a response and the body that
starts a new revision.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator

from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse

MAX_REASON_LENGTH = 2000


class ControlledDocumentResponse(EntityResponse):
    created: datetime
    changed: datetime | None
    # Who saved the last change; empty for a revision nobody changed since
    # the column exists.
    changed_by_id: int | None
    changed_by_full_name: str | None
    creator_id: int
    creator_full_name: str
    document_number: str
    lineage: UUID
    revision: str
    revision_reason: str | None
    is_latest: bool
    superseded_at: datetime | None
    read_only: bool
    released_at: datetime | None
    released_by_id: int | None
    released_by_full_name: str | None
    invalid_at: datetime | None
    invalid_by_id: int | None
    invalid_by_full_name: str | None
    invalid_reason: str | None
    locked_by_id: int | None
    locked_by_full_name: str | None
    locked_at: datetime | None
    lock_expires_at: datetime | None


class DocumentReasonRequest(BaseModel):
    """A reason the changelog records, such as why a new revision starts."""

    reason: str = Field(..., min_length=1, max_length=MAX_REASON_LENGTH)

    @field_validator("reason")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("reason must not be blank")
        return value


class DocumentLockRequest(BaseModel):
    take_over: bool = Field(
        default=False, description="Take the lock over from the editor who holds it"
    )
