"""
ORM model for the admin_stock_settings singleton table: the stock service
Glados calls and the API key it calls it with (encrypted at rest with
SECURITY__ENCRYPTION_KEY and re-encrypted on key rotation like every
EncryptedString column).
"""

from sqlalchemy import Boolean
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.modules.platform.adapters.outbound.persistence.encrypted_type import EncryptedString
from src.modules.platform.adapters.outbound.persistence.models.base import Base


class AdminStockSettingsOrmModel(Base):
    __tablename__ = "admin_stock_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    service_url: Mapped[str] = mapped_column(String, nullable=False, server_default="")
    api_key: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
