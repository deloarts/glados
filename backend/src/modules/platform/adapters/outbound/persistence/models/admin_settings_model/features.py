"""
ORM model for the admin_feature_settings singleton table.
"""

from sqlalchemy import Boolean
from sqlalchemy import Integer
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.modules.platform.adapters.outbound.persistence.models.base import Base


class AdminFeatureSettingsOrmModel(Base):
    __tablename__ = "admin_feature_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    enable_email_notifications: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    enable_production_planning: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    allow_private_webhooks: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    enable_calculations: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    enable_checklists: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    enable_devices: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    enable_sequences: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    enable_todos: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
