"""
SQLAlchemy ORM models for personal access tokens and their usage log.
Infrastructure detail, never imported by domain or application layers.
"""

from datetime import datetime

from sqlalchemy import JSON
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.modules.platform.adapters.outbound.persistence.models.base import Base


class PatOrmModel(Base):
    __tablename__ = "pat_table"

    # No `index=True`/`unique=True` here: the PK already provides both, a
    # bare `ix_<table>_id` would be pure duplication.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    token_hash: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    token_prefix: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_pat_table_user_id_user_table"),
        index=True,
        nullable=False,
    )
    permissions: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list, server_default="[]"
    )
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PatUsageLogOrmModel(Base):
    __tablename__ = "pat_usage_log_table"

    # No `index=True`/`unique=True` here: the PK already provides both, a
    # bare `ix_<table>_id` would be pure duplication.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    pat_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("pat_table.id", name="fk_pat_usage_log_table_pat_id_pat_table"),
        index=True,
        nullable=False,
    )
    called_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    method: Mapped[str] = mapped_column(String(16), nullable=False)
    path: Mapped[str] = mapped_column(String, nullable=False)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
