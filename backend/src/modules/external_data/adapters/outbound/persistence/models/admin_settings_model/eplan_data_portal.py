"""
ORM model for the admin_edp_settings singleton table. The personal access
token is an EncryptedString (ADR 0005).
"""

from sqlalchemy import JSON
from sqlalchemy import Boolean
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.modules.platform.adapters.outbound.persistence.encrypted_type import EncryptedString
from src.modules.platform.adapters.outbound.persistence.models.base import Base


class AdminEdpSettingsOrmModel(Base):
    __tablename__ = "admin_edp_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    base_url: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="https://dataportal.eplan.com/api",
        server_default="https://dataportal.eplan.com/api",
    )
    pat: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    default_article_group_ids: Mapped[list[int]] = mapped_column(
        JSON, nullable=False, default=list, server_default="[]"
    )
    language: Mapped[str] = mapped_column(
        String(8), nullable=False, default="de_DE", server_default="de_DE"
    )
