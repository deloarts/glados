"""
SQLAlchemy ORM model for inspection methods. Infrastructure detail, never
imported by domain or application layers.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON
from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import column
from sqlalchemy import select
from sqlalchemy import table
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import column_property
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from sqlalchemy.sql import false

from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.adapters.outbound.persistence.models.changed_by_columns import (
    ChangedByColumns,
)
from src.modules.platform.adapters.outbound.persistence.models.changelog_type import ChangelogType

# The machine table of Planning & fulfillment, named rather than imported:
# Catalogue sits below it, and the shared database already links the two
# through the default machine's foreign key.
_production_machine_table = table(
    "production_machine_table", column("id", Integer), column("internal_name", String)
)

if TYPE_CHECKING:
    from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel


class InspectionMethodOrmModel(ChangedByColumns, Base):
    __tablename__ = "inspection_method_table"

    # `name` uniqueness is scoped to non-archived rows by a partial unique index.

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
    default_setup_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    default_minutes_per_piece: Mapped[float | None] = mapped_column(Float, nullable=True)
    requires_evidence: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    # Also serves as the soft-delete flag.
    archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    # Position in the hand-kept order of the list, see the entity.
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # Opt-in QA machine pre-filled onto a step's auto-queued production
    # order at lot creation, see the entity's docstring. Nullable: a method
    # has no default machine until an admin picks one.
    default_machine_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("production_machine_table.id", name="fk_inspection_method_default_machine_id"),
        nullable=True,
        index=True,
    )
    default_machine_name: Mapped[str | None] = column_property(
        select(_production_machine_table.c.internal_name)
        .where(_production_machine_table.c.id == default_machine_id)
        .scalar_subquery()
    )

    # ── Audit ─────────────────────────────────────────────────────────
    creator_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_inspection_method_creator_id"),
        nullable=False,
        index=True,
    )
    creator: Mapped["UserOrmModel"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[creator_id],
        lazy="raise_on_sql",
    )
