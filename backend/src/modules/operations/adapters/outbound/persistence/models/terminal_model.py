"""
SQLAlchemy ORM model for terminals. Infrastructure detail, never imported by
domain or application layers.

The public key is unique, since it is the device's identity. A pairing code
is unique among pending terminals only, through a partial unique index.
Terminals are devices rather than master data, so deleting one removes its
row.

The device details the table shows are typed columns; the rest of a report
lives in `device_details` as JSON, cleaned by the domain value object
before it is written.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from typing import Any

from sqlalchemy import JSON
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from sqlalchemy.sql import text

from src.modules.platform.adapters.outbound.persistence.models.base import Base

if TYPE_CHECKING:
    from src.modules.operations.adapters.outbound.persistence.models.infoscreen_model import (
        InfoscreenOrmModel,
    )
    from src.modules.platform.adapters.outbound.persistence.models.api_key_model import (
        ApiKeyOrmModel,
    )
    from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel


class TerminalOrmModel(Base):
    __tablename__ = "terminal_table"

    __table_args__ = (
        Index("uq_terminal_public_key", "public_key", unique=True),
        Index(
            "uq_terminal_pairing_code_pending",
            "pairing_code",
            unique=True,
            postgresql_where=text("status = 'pending'"),
            sqlite_where=text("status = 'pending'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── Identity ──────────────────────────────────────────────────────
    public_key: Mapped[str] = mapped_column(String, nullable=False)
    public_key_fingerprint: Mapped[str] = mapped_column(String, nullable=False)

    # ── State ─────────────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    mode: Mapped[str] = mapped_column(
        String, nullable=False, default="infoscreen", server_default="infoscreen"
    )
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    pairing_code: Mapped[str | None] = mapped_column(String, nullable=True)
    pairing_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    infoscreen_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("infoscreen_table.id", name="fk_terminal_infoscreen_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    api_key_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("api_key_table.id", name="fk_terminal_api_key_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ── Telemetry ─────────────────────────────────────────────────────
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_ip: Mapped[str | None] = mapped_column(String, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String, nullable=True)
    screen_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    screen_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    frontend_version: Mapped[str | None] = mapped_column(String, nullable=True)
    bridge_version: Mapped[str | None] = mapped_column(String, nullable=True)

    # ── Device details ────────────────────────────────────────────────
    device_computer_model: Mapped[str | None] = mapped_column(String, nullable=True)
    device_ram_mb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    device_os_name: Mapped[str | None] = mapped_column(String, nullable=True)
    device_display_make: Mapped[str | None] = mapped_column(String, nullable=True)
    device_display_model: Mapped[str | None] = mapped_column(String, nullable=True)
    device_display_width_px: Mapped[int | None] = mapped_column(Integer, nullable=True)
    device_display_height_px: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Every other reported detail.
    device_details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    device_reported_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Placement ─────────────────────────────────────────────────────
    location: Mapped[str | None] = mapped_column(String, nullable=True)

    # ── Approval and commands ─────────────────────────────────────────
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_terminal_approved_by_id"),
        nullable=True,
        index=True,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reload_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    identify_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    display_override: Mapped[str | None] = mapped_column(String, nullable=True)
    display_override_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Clone detection ───────────────────────────────────────────────
    last_session_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_session_ip: Mapped[str | None] = mapped_column(String, nullable=True)
    duplicate_detected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Relations ─────────────────────────────────────────────────────
    infoscreen: Mapped["InfoscreenOrmModel | None"] = relationship(
        "src.modules.operations.adapters.outbound.persistence.models.infoscreen_model.InfoscreenOrmModel",
        foreign_keys=[infoscreen_id],
        lazy="raise_on_sql",
    )
    api_key: Mapped["ApiKeyOrmModel | None"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.api_key_model.ApiKeyOrmModel",
        foreign_keys=[api_key_id],
        lazy="raise_on_sql",
    )
    approved_by: Mapped["UserOrmModel | None"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[approved_by_id],
        lazy="raise_on_sql",
    )
