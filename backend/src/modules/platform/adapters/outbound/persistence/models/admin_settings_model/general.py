"""
ORM model for the admin_general_settings singleton table.
"""

from sqlalchemy import Boolean
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.const import SERVER_DEFAULT_CURRENCY
from src.modules.platform.const import SERVER_DEFAULT_DATE_FORMAT
from src.modules.platform.const import SERVER_DEFAULT_LANGUAGE
from src.modules.platform.const import SERVER_DEFAULT_TIMEZONE


class AdminGeneralSettingsOrmModel(Base):
    __tablename__ = "admin_general_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    company_name: Mapped[str | None] = mapped_column(String, nullable=True)
    company_legal_name: Mapped[str | None] = mapped_column(String, nullable=True)
    company_logo_key: Mapped[str | None] = mapped_column(String, nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String, nullable=True)
    imprint_url: Mapped[str | None] = mapped_column(String, nullable=True)
    privacy_url: Mapped[str | None] = mapped_column(String, nullable=True)
    support_url: Mapped[str | None] = mapped_column(String, nullable=True)
    product_number_pattern: Mapped[str] = mapped_column(String, nullable=False, server_default="")
    project_number_pattern: Mapped[str] = mapped_column(String, nullable=False, server_default="")
    allow_headless_projects: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    empty_value_placeholder: Mapped[str] = mapped_column(String, nullable=False, server_default="-")
    # Office-waffle launcher in the app header. Off by default, so the
    # header shows no button an admin did not ask for.
    office_launcher_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    # SharePoint is the one M365 web app that stays tenant-specific
    # (https://<tenant>.sharepoint.com), so it is the only launcher tile
    # needing admin configuration. "" (the shipped default) hides the tile
    # without disabling the rest of the launcher, see UpdateGeneralSettings.
    office_sharepoint_url: Mapped[str] = mapped_column(String, nullable=False, server_default="")
    # Display currency, presentation only, see AdminGeneralSettings.currency.
    currency: Mapped[str] = mapped_column(
        String, nullable=False, server_default=SERVER_DEFAULT_CURRENCY
    )
    # Tenant-wide fallback for a user's own language and date_format
    # preference. default_timezone is not a fallback but the one timezone
    # the whole app reads calendar days and wall-clock times in. The
    # server_default equals const.py's SERVER_DEFAULT_*, the shipped value.
    default_language: Mapped[str] = mapped_column(
        String, nullable=False, server_default=SERVER_DEFAULT_LANGUAGE
    )
    default_timezone: Mapped[str] = mapped_column(
        String, nullable=False, server_default=SERVER_DEFAULT_TIMEZONE
    )
    default_date_format: Mapped[str] = mapped_column(
        String, nullable=False, server_default=SERVER_DEFAULT_DATE_FORMAT
    )
