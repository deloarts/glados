"""
ORM model for the admin_retention_settings singleton table.
"""

from sqlalchemy import Integer
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.modules.platform.adapters.outbound.persistence.models.base import Base


class AdminRetentionSettingsOrmModel(Base):
    __tablename__ = "admin_retention_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    log_retention_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default="90")
    audit_retention_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default="365")
    soft_delete_cleanup_days: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    meeting_retention_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
