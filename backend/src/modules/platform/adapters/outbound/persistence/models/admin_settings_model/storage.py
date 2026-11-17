"""
ORM model for the admin_storage_settings singleton table.
"""

from sqlalchemy import Boolean
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.modules.platform.adapters.outbound.persistence.encrypted_type import EncryptedString
from src.modules.platform.adapters.outbound.persistence.models.base import Base


class AdminStorageSettingsOrmModel(Base):
    __tablename__ = "admin_storage_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    provider: Mapped[str] = mapped_column(String, nullable=False, server_default="local")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    endpoint_url: Mapped[str | None] = mapped_column(String, nullable=True)
    public_endpoint_url: Mapped[str | None] = mapped_column(String, nullable=True)
    bucket_name: Mapped[str | None] = mapped_column(String, nullable=True)
    # Both credentials are encrypted at rest, see encrypted_type.py: together
    # they open the bucket, which also holds the database backups.
    access_key: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    secret_key: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    region: Mapped[str | None] = mapped_column(String, nullable=True)
    use_ssl: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    backup_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    backup_path: Mapped[str | None] = mapped_column(String, nullable=True)
    backup_cron: Mapped[str | None] = mapped_column(String, nullable=True)
    backup_retention_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="7")
    disk_warning_percent: Mapped[int] = mapped_column(Integer, nullable=False, server_default="90")
