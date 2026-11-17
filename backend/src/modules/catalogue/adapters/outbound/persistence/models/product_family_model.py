"""
SQLAlchemy ORM model for product families. A bought item references at
most one through bought_item_table.product_family_id.
Infrastructure detail, never imported by domain or application layers.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from sqlalchemy.sql import false
from sqlalchemy.sql import text

from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.adapters.outbound.persistence.models.changed_by_columns import (
    ChangedByColumns,
)
from src.modules.platform.adapters.outbound.persistence.models.changelog_type import ChangelogType

if TYPE_CHECKING:
    from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel


class ProductFamilyOrmModel(ChangedByColumns, Base):
    __tablename__ = "product_family_table"

    # `name` uniqueness is scoped to non-archived rows, like article groups.
    __table_args__ = (
        Index(
            "uq_product_family_name_active",
            "name",
            unique=True,
            postgresql_where=text("archived IS false"),
            sqlite_where=text("archived = 0"),
        ),
    )

    # ── Server-managed ────────────────────────────────────────────────
    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changed: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changes: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(ChangelogType), nullable=False, default=[]
    )
    archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    # Position in the hand-kept order of the list, see the entity.
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    # ── Core fields ───────────────────────────────────────────────────
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    label_color: Mapped[str] = mapped_column(
        String, nullable=False, default="#999999", server_default="#999999"
    )
    label_font_color: Mapped[str] = mapped_column(
        String, nullable=False, default="#000000", server_default="#000000"
    )
    description: Mapped[str] = mapped_column(String, nullable=False, default="", server_default="")

    # ── Audit ─────────────────────────────────────────────────────────
    creator_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_product_family_creator_id"),
        nullable=False,
        index=True,
    )
    creator: Mapped["UserOrmModel"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[creator_id],
        lazy="raise_on_sql",
    )
