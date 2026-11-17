"""
SQLAlchemy ORM models of the snapshots of printed, downloaded and sent
meeting notes, and of the contacts each snapshot names. No config imports.
No domain imports.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON
from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.sql import false

from src.modules.platform.adapters.outbound.persistence.models.base import Base


class MeetingSnapshotOrmModel(Base):
    """What one print, download or send of a meeting's notes contained. The
    contents are JSON in the shapes the repository writes, so a snapshot
    never changes when the meeting does."""

    __tablename__ = "meeting_snapshot_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    meeting_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("meeting_table.id", name="fk_meeting_snapshot_meeting_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # The export journal entry, which belongs to Quality & documents and
    # outlives the meeting, so it is named without a reference.
    journal_entry_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)  # MeetingDistributionKind
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_meeting_snapshot_actor_id"),
        nullable=False,
        index=True,
    )
    issue_number: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    issue_draft: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    language: Mapped[str] = mapped_column(String, nullable=False)
    options: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    meeting: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    cards: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    attendees: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    files: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    attachments: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    recipients: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    cc: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    subject: Mapped[str | None] = mapped_column(String, nullable=True)


class MeetingSnapshotContactOrmModel(Base):
    """A contact a snapshot keeps a copy of, as an attendee or a todo
    owner. The contact is named without a reference, since a snapshot must
    not keep a contact from being deleted."""

    __tablename__ = "meeting_snapshot_contact_table"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_id", "contact_id", name="uq_meeting_snapshot_contact_snapshot_contact"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    snapshot_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "meeting_snapshot_table.id",
            name="fk_meeting_snapshot_contact_snapshot_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    contact_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
