"""
ORM model for PLC environments. The prefixes, conversions and export
columns are JSON. Names are unique among the live environments, compared
case-insensitively through `name_key`. Infrastructure detail, never imported by the domain or
application layers.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON
from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.sql import false
from sqlalchemy.sql import text

from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.adapters.outbound.persistence.models.changed_by_columns import (
    ChangedByColumns,
)
from src.modules.platform.adapters.outbound.persistence.models.changelog_type import ChangelogType


class PlcEnvironmentOrmModel(ChangedByColumns, Base):
    __tablename__ = "plc_environment_table"

    __table_args__ = (
        Index(
            "uq_plc_environment_name_active",
            "name_key",
            unique=True,
            postgresql_where=text("archived IS false"),
            sqlite_where=text("archived = 0"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changed: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changes: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(ChangelogType), nullable=False, default=[]
    )

    name: Mapped[str] = mapped_column(String, nullable=False)
    # The name lower-cased, for the case-insensitive uniqueness.
    name_key: Mapped[str] = mapped_column(String, nullable=False)
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    prefixes: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False)
    max_tag_length: Mapped[int] = mapped_column(Integer, nullable=False)
    conversions: Mapped[list[dict[str, str]]] = mapped_column(JSON, nullable=False)
    tag_table: Mapped[str] = mapped_column(String, nullable=False)
    safety_tag_table: Mapped[str | None] = mapped_column(String, nullable=True)
    export_sheet: Mapped[str] = mapped_column(String, nullable=False)
    export_columns: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    creator_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_plc_environment_creator_id"),
        nullable=True,
        index=True,
    )
