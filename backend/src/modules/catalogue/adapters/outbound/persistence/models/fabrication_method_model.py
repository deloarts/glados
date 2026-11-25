"""
SQLAlchemy ORM model for fabrication methods. Infrastructure detail, never
imported by domain or application layers.
"""

from datetime import datetime
from typing import TYPE_CHECKING

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
from sqlalchemy.orm import relationship
from sqlalchemy.sql import false
from sqlalchemy.sql import text
from sqlalchemy.sql import true

from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.adapters.outbound.persistence.models.changed_by_columns import (
    ChangedByColumns,
)
from src.modules.platform.adapters.outbound.persistence.models.changelog_type import ChangelogType

if TYPE_CHECKING:
    from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel


class FabricationMethodOrmModel(ChangedByColumns, Base):
    __tablename__ = "fabrication_method_table"

    # `name` uniqueness is scoped to non-archived rows by a partial unique index.
    # A second one over the flagged rows keeps at most one method the default
    # for assemblies. Archived methods never carry that flag, so it needs no
    # archived clause.
    __table_args__ = (
        Index(
            "uq_fabrication_method_default_for_assemblies",
            "default_for_assemblies",
            unique=True,
            postgresql_where=text("default_for_assemblies IS true"),
            sqlite_where=text("default_for_assemblies = 1"),
        ),
    )

    # ── Server-managed ────────────────────────────────────────────────
    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changed: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changes: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(ChangelogType), nullable=False, default=[]
    )

    # ── Core fields ───────────────────────────────────────────────────
    # Text per language code (LocalizedText). Names are unique per language
    # among live rows, enforced by the use cases (label_name_rules.py).
    name: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False)
    label_color: Mapped[str] = mapped_column(String, nullable=False, default="#999999")
    label_font_color: Mapped[str] = mapped_column(String, nullable=False, default="#000000")
    description: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False, default=dict)
    requires_machine: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    required_external: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    default_supplier_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("supplier_table.id", name="fk_fabrication_method_default_supplier_id"),
        nullable=True,
        index=True,
    )
    lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Clock minutes the pieces wait after the step, such as curing; None
    # waits nothing.
    wait_after_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    default_for_assemblies: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    # Also serves as the soft-delete flag.
    archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    # Position in the hand-kept order of the list, see the entity.
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    # ── Audit ─────────────────────────────────────────────────────────
    creator_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_fabrication_method_creator_id"),
        nullable=False,
        index=True,
    )
    creator: Mapped["UserOrmModel"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[creator_id],
        lazy="raise_on_sql",
    )
