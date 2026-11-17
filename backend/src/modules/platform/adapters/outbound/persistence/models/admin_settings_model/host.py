"""
ORM model for the admin_host_settings singleton table.
"""

from sqlalchemy import Integer
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.modules.platform.adapters.outbound.persistence.models.base import Base


class AdminHostSettingsOrmModel(Base):
    __tablename__ = "admin_host_settings"

    # No business columns: the contact address and legal URLs live in
    # admin_general_settings. Kept as the home for future host-scoped settings.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
