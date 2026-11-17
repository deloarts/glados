"""
ORM model for the admin_security_settings singleton table.
"""

from sqlalchemy import JSON
from sqlalchemy import Boolean
from sqlalchemy import Integer
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.modules.platform.adapters.outbound.persistence.models.base import Base


class AdminSecuritySettingsOrmModel(Base):
    __tablename__ = "admin_security_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    enforce_totp: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    allow_rfid_login: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    allow_local_login: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    enable_api_key_auth: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    min_password_length: Mapped[int] = mapped_column(Integer, nullable=False, server_default="8")
    session_timeout_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1440"
    )
    totp_trusted_device_days: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="30"
    )
    # 0 means unlimited, for an admin who turns the lockout off.
    max_login_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="5")
    lockout_duration_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="15"
    )
    token_max_lifetime_days: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="365"
    )
    session_max_lifetime_days: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="30"
    )
    enable_terminals: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    enable_infoscreen_weather: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    terminal_allowed_ips: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list, server_default="[]"
    )
