"""
The timestamps every allocation table carries: when the row was created and
when it last changed. They are set on the Python side at insert and at every
ORM update, so each write path stamps them. Each model adds created_by_id,
set by the writer that knows the actor and left empty for system writes. No
config imports.
"""

from datetime import UTC
from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column


def _now() -> datetime:
    return datetime.now(UTC)


class AllocationAudit:
    """Timestamp mixin of the allocation ORM models."""

    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=_now
    )
    changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=_now, onupdate=_now
    )
