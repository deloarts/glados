"""
SQLAlchemy ORM model of the drafts of meeting notes that AI agents prepare
for their users. No config imports. No domain imports.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON
from sqlalchemy import CheckConstraint
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.modules.platform.adapters.outbound.persistence.models.base import Base


class MeetingNotesDraftOrmModel(Base):
    """One draft. Its contents are JSON in the shapes the repository writes,
    since a draft is read and replaced as a whole and never queried by what
    it contains."""

    __tablename__ = "meeting_notes_draft_table"
    __table_args__ = (
        CheckConstraint(
            "(CASE WHEN meeting_id IS NULL THEN 0 ELSE 1 END)"
            " + (CASE WHEN project_id IS NULL THEN 0 ELSE 1 END)"
            " + (CASE WHEN product_id IS NULL THEN 0 ELSE 1 END) = 1",
            name="ck_meeting_notes_draft_table_one_target",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    creator_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_meeting_notes_draft_creator_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    meeting_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "meeting_table.id", name="fk_meeting_notes_draft_meeting_id", ondelete="CASCADE"
        ),
        nullable=True,
        index=True,
    )
    project_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "project_table.id", name="fk_meeting_notes_draft_project_id", ondelete="CASCADE"
        ),
        nullable=True,
        index=True,
    )
    product_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "product_table.id", name="fk_meeting_notes_draft_product_id", ondelete="CASCADE"
        ),
        nullable=True,
        index=True,
    )
    token_name: Mapped[str | None] = mapped_column(String, nullable=True)
    new_meeting: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    next_meeting: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    attendees: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    cards: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    review_note: Mapped[str | None] = mapped_column(String, nullable=True)
