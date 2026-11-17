"""
SQLAlchemy ORM model for infoscreens. Infrastructure detail, never imported by
domain or application layers. The pages and the display schedule live in
JSON columns, validated by the domain value objects on every write.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from typing import Any

from sqlalchemy import JSON
from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from sqlalchemy.sql import false
from sqlalchemy.sql import text
from sqlalchemy.sql import true

from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.adapters.outbound.persistence.models.changed_by_columns import (
    ChangedByColumns,
)
from src.modules.platform.adapters.outbound.persistence.models.changelog_type import ChangelogType

# The default bars as stored JSON, matching value_objects.infoscreen.
HEADER_SERVER_DEFAULT = (
    '{"left": ["logo", "title"], "center": [], "right": ["clock"], "text": null}'
)
FOOTER_SERVER_DEFAULT = '{"left": [], "center": [], "right": ["last_updated"], "text": null}'

if TYPE_CHECKING:
    from src.modules.operations.adapters.outbound.persistence.models.terminal_model import (
        TerminalOrmModel,
    )
    from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel


class InfoscreenOrmModel(ChangedByColumns, Base):
    __tablename__ = "infoscreen_table"

    # `name` uniqueness is scoped to non-archived rows by a partial unique index.
    __table_args__ = (
        Index(
            "uq_infoscreen_name_active",
            "name",
            unique=True,
            postgresql_where=text("archived IS false"),
            sqlite_where=text("archived = 0"),
        ),
    )

    # ── Server-managed ────────────────────────────────────────────────
    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    changes: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(ChangelogType), nullable=False, default=[]
    )
    archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )

    # ── Core fields ───────────────────────────────────────────────────
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    color_mode: Mapped[str] = mapped_column(
        String, nullable=False, default="dark", server_default="dark"
    )
    theme_preset: Mapped[str | None] = mapped_column(String, nullable=True)
    primary_color: Mapped[str | None] = mapped_column(String, nullable=True)
    rotation_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=30, server_default="30"
    )
    show_banner: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    pages: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list, server_default="[]"
    )
    show_header: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    header: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, server_default=HEADER_SERVER_DEFAULT
    )
    show_footer: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    footer: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, server_default=FOOTER_SERVER_DEFAULT
    )
    # A Language value; None is the tenant default.
    language: Mapped[str | None] = mapped_column(String, nullable=True)
    # A DisplayScheduleMode value: which schedule the displays follow.
    display_schedule_mode: Mapped[str] = mapped_column(
        String(16), nullable=False, default="default", server_default="default"
    )
    # None means always on.
    display_schedule: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    off_on_holidays: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )

    # ── Relations ─────────────────────────────────────────────────────
    creator_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_infoscreen_creator_id"),
        nullable=False,
        index=True,
    )
    creator: Mapped["UserOrmModel"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[creator_id],
        lazy="raise_on_sql",
    )
    # The terminals showing this screen, for its read-only "shown on" list.
    terminals: Mapped[list["TerminalOrmModel"]] = relationship(
        "src.modules.operations.adapters.outbound.persistence.models.terminal_model.TerminalOrmModel",
        viewonly=True,
        order_by="TerminalOrmModel.id",
        lazy="raise_on_sql",
    )


class InfoscreenDisplayDefaultOrmModel(Base):
    """The singleton row of the default display schedule, which the screens
    in the Default mode follow. None means always on."""

    __tablename__ = "infoscreen_display_default"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    display_schedule: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    off_on_holidays: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
