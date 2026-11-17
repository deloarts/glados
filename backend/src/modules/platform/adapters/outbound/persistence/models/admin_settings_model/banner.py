"""
ORM model for the admin_banner_settings singleton table.
"""

from datetime import datetime

from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import func
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.modules.platform.adapters.outbound.persistence.models.base import Base


class AdminBannerSettingsOrmModel(Base):
    __tablename__ = "admin_banner_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    text: Mapped[str] = mapped_column(String, nullable=False, server_default="")
    severity: Mapped[str] = mapped_column(String, nullable=False, server_default="info")
    shows_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    shows_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissable: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    # server_default is a defensive fallback only: UpdateBannerSettings
    # always writes this column explicitly on every save (now_utc()),
    # same as every other *_at column in this package that has no default.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
