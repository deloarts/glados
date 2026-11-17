"""
ORM model for the admin_notification_settings singleton table.
"""

from sqlalchemy import Integer
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.modules.platform.adapters.outbound.persistence.models.base import Base


class AdminNotificationSettingsOrmModel(Base):
    __tablename__ = "admin_notification_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    webhook_timeout_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="10"
    )
