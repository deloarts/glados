"""
SQLAlchemy ORM models of meetings and the rows that belong to them:
attendees, tags, cards with their revisions, mentions, decisions and todos
with their owners, the history, the files and the queue of bundled
notifications. No config imports. No domain imports.
"""

from datetime import date
from datetime import datetime
from datetime import time
from typing import Any
from typing import ClassVar

from sqlalchemy import JSON
from sqlalchemy import Boolean
from sqlalchemy import CheckConstraint
from sqlalchemy import Date
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import Time
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from sqlalchemy.sql import false
from sqlalchemy.sql import true

from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.adapters.outbound.persistence.models.changed_by_columns import (
    ChangedByColumns,
)
from src.modules.platform.adapters.outbound.persistence.models.edit_version_column import (
    EditVersionColumn,
)

_MODELS = "src.modules.workspace.adapters.outbound.persistence.models.meeting_model"


def _user_fk(name: str, *, nullable: bool) -> Mapped[Any]:
    return mapped_column(
        Integer, ForeignKey("user_table.id", name=name), nullable=nullable, index=True
    )


def _meeting_fk(prefix: str) -> Mapped[int]:
    return mapped_column(
        Integer,
        ForeignKey("meeting_table.id", name=f"fk_{prefix}_meeting_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


def _card_fk(prefix: str) -> Mapped[int]:
    return mapped_column(
        Integer,
        ForeignKey("meeting_card_table.id", name=f"fk_{prefix}_card_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


class MeetingOrmModel(EditVersionColumn, ChangedByColumns, Base):
    __tablename__ = "meeting_table"
    __table_args__ = (
        CheckConstraint(
            "(project_id IS NULL) <> (product_id IS NULL)", name="ck_meeting_table_one_owner"
        ),
    )
    # Sending and printing stamp these; an open edit form must not be
    # refused for it.
    __edit_version_ignored__: ClassVar[frozenset[str]] = frozenset(
        {"issue_number", "last_sent_at", "last_printed_at"}
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    meeting_number: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    project_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("project_table.id", name="fk_meeting_project_id"),
        nullable=True,
        index=True,
    )
    product_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("product_table.id", name="fk_meeting_product_id"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    next_meeting_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_meeting_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    next_meeting_location: Mapped[str | None] = mapped_column(String, nullable=True)
    follow_up_of_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("meeting_table.id", name="fk_meeting_follow_up_of_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    invalid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invalid_by_id: Mapped[int | None] = _user_fk("fk_meeting_invalid_by_id", nullable=True)
    invalid_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    issue_number: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_printed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    creator_id: Mapped[int] = _user_fk("fk_meeting_creator_id", nullable=False)
    changed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    attendees: Mapped[list["MeetingAttendeeOrmModel"]] = relationship(
        f"{_MODELS}.MeetingAttendeeOrmModel",
        order_by="MeetingAttendeeOrmModel.position",
        cascade="all, delete-orphan",
        lazy="raise_on_sql",
    )
    tags: Mapped[list["MeetingTagOrmModel"]] = relationship(
        f"{_MODELS}.MeetingTagOrmModel",
        order_by="MeetingTagOrmModel.position",
        cascade="all, delete-orphan",
        lazy="raise_on_sql",
    )


class MeetingTagOrmModel(Base):
    """One free-text tag of a meeting. The domain keeps a meeting's tags
    apart in case too, so the unique key on the spelling is enough here."""

    __tablename__ = "meeting_tag_table"
    __table_args__ = (UniqueConstraint("meeting_id", "name", name="uq_meeting_tag_meeting_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    meeting_id: Mapped[int] = _meeting_fk("meeting_tag")
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    name: Mapped[str] = mapped_column(String, nullable=False)


class MeetingAttendeeOrmModel(Base):
    __tablename__ = "meeting_attendee_table"
    __table_args__ = (
        CheckConstraint(
            "(kind = 'user' AND user_id IS NOT NULL AND contact_id IS NULL)"
            " OR (kind = 'contact' AND contact_id IS NOT NULL AND user_id IS NULL)"
            " OR (kind = 'guest' AND user_id IS NULL AND contact_id IS NULL)",
            name="ck_meeting_attendee_table_kind",
        ),
        UniqueConstraint("meeting_id", "user_id", name="uq_meeting_attendee_user"),
        UniqueConstraint("meeting_id", "contact_id", name="uq_meeting_attendee_contact"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    meeting_id: Mapped[int] = _meeting_fk("meeting_attendee")
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    kind: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[int | None] = _user_fk("fk_meeting_attendee_user_id", nullable=True)
    contact_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("contact_table.id", name="fk_meeting_attendee_contact_id"),
        nullable=True,
        index=True,
    )
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="present")
    anonymised_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MeetingCardOrmModel(EditVersionColumn, ChangedByColumns, Base):
    __tablename__ = "meeting_card_table"
    # Reordering the cards must not refuse an edit that is open meanwhile.
    __edit_version_ignored__: ClassVar[frozenset[str]] = frozenset({"position"})

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    meeting_id: Mapped[int] = _meeting_fk("meeting_card")
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    scope: Mapped[str | None] = mapped_column(String, nullable=True)
    scope_icon: Mapped[str | None] = mapped_column(String, nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    internal: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    creator_id: Mapped[int] = _user_fk("fk_meeting_card_creator_id", nullable=False)
    changed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MeetingCardRevisionOrmModel(Base):
    __tablename__ = "meeting_card_revision_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    card_id: Mapped[int] = _card_fk("meeting_card_revision")
    scope: Mapped[str | None] = mapped_column(String, nullable=True)
    scope_icon: Mapped[str | None] = mapped_column(String, nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    internal: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    author_id: Mapped[int] = _user_fk("fk_meeting_card_revision_author_id", nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    saved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MeetingCardMentionOrmModel(Base):
    __tablename__ = "meeting_card_mention_table"
    __table_args__ = (
        UniqueConstraint("card_id", "user_id", name="uq_meeting_card_mention_card_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    card_id: Mapped[int] = _card_fk("meeting_card_mention")
    user_id: Mapped[int] = _user_fk("fk_meeting_card_mention_user_id", nullable=False)
    present: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MeetingDecisionOrmModel(Base):
    __tablename__ = "meeting_decision_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    meeting_id: Mapped[int] = _meeting_fk("meeting_decision")
    card_id: Mapped[int] = _card_fk("meeting_decision")
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    creator_id: Mapped[int] = _user_fk("fk_meeting_decision_creator_id", nullable=False)


class MeetingTodoOrmModel(ChangedByColumns, Base):
    __tablename__ = "meeting_todo_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    meeting_id: Mapped[int] = _meeting_fk("meeting_todo")
    card_id: Mapped[int] = _card_fk("meeting_todo")
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    title: Mapped[str] = mapped_column(String, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    done_by_id: Mapped[int | None] = _user_fk("fk_meeting_todo_done_by_id", nullable=True)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    creator_id: Mapped[int] = _user_fk("fk_meeting_todo_creator_id", nullable=False)
    changed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    owners: Mapped[list["MeetingTodoOwnerOrmModel"]] = relationship(
        f"{_MODELS}.MeetingTodoOwnerOrmModel",
        order_by="MeetingTodoOwnerOrmModel.id",
        cascade="all, delete-orphan",
        lazy="raise_on_sql",
    )


class MeetingTodoOwnerOrmModel(Base):
    __tablename__ = "meeting_todo_owner_table"
    __table_args__ = (
        CheckConstraint(
            "(user_id IS NULL) <> (contact_id IS NULL)",
            name="ck_meeting_todo_owner_table_one_owner",
        ),
        UniqueConstraint("todo_id", "user_id", name="uq_meeting_todo_owner_user"),
        UniqueConstraint("todo_id", "contact_id", name="uq_meeting_todo_owner_contact"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    todo_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "meeting_todo_table.id", name="fk_meeting_todo_owner_todo_id", ondelete="CASCADE"
        ),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int | None] = _user_fk("fk_meeting_todo_owner_user_id", nullable=True)
    contact_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("contact_table.id", name="fk_meeting_todo_owner_contact_id"),
        nullable=True,
        index=True,
    )
    name: Mapped[str | None] = mapped_column(String, nullable=True)


class MeetingEventOrmModel(Base):
    __tablename__ = "meeting_event_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    meeting_id: Mapped[int] = _meeting_fk("meeting_event")
    kind: Mapped[str] = mapped_column(String, nullable=False)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor_id: Mapped[int | None] = _user_fk("fk_meeting_event_actor_id", nullable=True)
    # No references: the history outlives the cards, todos and files it names.
    card_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    todo_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    summary: Mapped[str | None] = mapped_column(String, nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class MeetingFileOrmModel(Base):
    __tablename__ = "meeting_file_table"
    __table_args__ = (UniqueConstraint("stored_name", name="uq_meeting_file_stored_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    meeting_id: Mapped[int] = _meeting_fk("meeting_file")
    card_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("meeting_card_table.id", name="fk_meeting_file_card_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    file_name: Mapped[str] = mapped_column(String, nullable=False)
    stored_name: Mapped[str] = mapped_column(String, nullable=False)
    mime_type: Mapped[str] = mapped_column(String, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_path: Mapped[str] = mapped_column(String, nullable=False)
    sha256: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)  # MeetingFileCategory
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    uploaded_by_user_id: Mapped[int] = _user_fk("fk_meeting_file_uploader_id", nullable=False)


class MeetingNotificationOrmModel(Base):
    """The mentions and todo assignments of a meeting that wait for one
    recipient to go out as one notification."""

    __tablename__ = "meeting_notification_table"
    __table_args__ = (
        UniqueConstraint(
            "meeting_id", "recipient_id", name="uq_meeting_notification_meeting_recipient"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    meeting_id: Mapped[int] = _meeting_fk("meeting_notification")
    recipient_id: Mapped[int] = _user_fk("fk_meeting_notification_recipient_id", nullable=False)
    actor_ids: Mapped[list[int]] = mapped_column(JSON, nullable=False)
    mention_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    todo_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    first_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
