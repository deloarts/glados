"""
ORM model for the admin_auth_settings singleton table.
"""

from sqlalchemy import Boolean
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.modules.platform.adapters.outbound.persistence.models.base import Base


class AdminAuthSettingsOrmModel(Base):
    __tablename__ = "admin_auth_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    ldap_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    ldap_host: Mapped[str] = mapped_column(String, nullable=False, server_default="")
    ldap_port: Mapped[int] = mapped_column(Integer, nullable=False, server_default="636")
    ldap_use_ssl: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    ldap_start_tls: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    # Verifies the directory server's certificate unless an admin turns it
    # off, for a server bound against an internal CA.
    ldap_verify_certificate: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    ldap_domain: Mapped[str] = mapped_column(String, nullable=False, server_default="")
    ldap_timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, server_default="5")
