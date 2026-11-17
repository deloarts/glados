"""
ORM model for the admin_data_import_settings singleton table. The import
profiles are one JSON object keyed by import type, each holding header_row,
data_offset, max_rows and column_names.
"""

from typing import Any

from sqlalchemy import JSON
from sqlalchemy import Integer
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.modules.platform.adapters.outbound.persistence.models.base import Base


class AdminDataImportSettingsOrmModel(Base):
    __tablename__ = "admin_data_import_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    profiles: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict, server_default="{}"
    )
