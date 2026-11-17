"""
ORM model for the admin_settings_audit log table.
"""

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.modules.platform.adapters.outbound.persistence.models.base import Base


class AdminSettingsAuditOrmModel(Base):
    __tablename__ = "admin_settings_audit"

    # No `index=True` here: the PK already provides one, a bare
    # `ix_<table>_id` would be pure duplication.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changed_by_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    changed_by_username: Mapped[str | None] = mapped_column(String, nullable=True)
    settings_domain: Mapped[str] = mapped_column(String, nullable=False, index=True)
    summary: Mapped[str] = mapped_column(String, nullable=False)
