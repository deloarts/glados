"""
ORM model for the admin_branding_settings singleton table.
"""

from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.modules.platform.adapters.outbound.persistence.models.base import Base


class AdminBrandingSettingsOrmModel(Base):
    __tablename__ = "admin_branding_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    app_name: Mapped[str] = mapped_column(String, nullable=False, server_default="Glados")
    app_description: Mapped[str | None] = mapped_column(String, nullable=True)
    footer_text: Mapped[str | None] = mapped_column(String, nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String, nullable=True)
    favicon_url: Mapped[str | None] = mapped_column(String, nullable=True)
    logo_key: Mapped[str | None] = mapped_column(String, nullable=True)
    favicon_key: Mapped[str | None] = mapped_column(String, nullable=True)
    login_background_video_key: Mapped[str | None] = mapped_column(String, nullable=True)
