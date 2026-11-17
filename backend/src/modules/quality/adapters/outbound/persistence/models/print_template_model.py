"""
Settings-style ORM model: one row per PrintClassifier, created at startup.
No config imports.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON
from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from sqlalchemy.sql import false
from sqlalchemy.sql import true

from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.adapters.outbound.persistence.models.changed_by_columns import (
    ChangedByColumns,
)
from src.modules.platform.adapters.outbound.persistence.models.changelog_type import ChangelogType

if TYPE_CHECKING:
    from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel
    from src.modules.quality.adapters.outbound.persistence.models.printer_model import (
        PrinterOrmModel,
    )


class PrintTemplateOrmModel(ChangedByColumns, Base):
    __tablename__ = "print_template_table"

    # A named unique index rather than `unique=True` on the column, which
    # would render an unnamed table-level UniqueConstraint instead.
    __table_args__ = (Index("uq_print_template_classifier", "classifier", unique=True),)

    # ── Server-managed ────────────────────────────────────────────────
    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    changes: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(ChangelogType), nullable=False, default=[]
    )

    # ── Identity ──────────────────────────────────────────────────────
    classifier: Mapped[str] = mapped_column(String, nullable=False)

    # ── Configurable ──────────────────────────────────────────────────
    trigger: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_map: Mapped[dict[str, str]] = mapped_column(
        MutableDict.as_mutable(JSON), nullable=False, default=dict
    )
    printer_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("printer_table.id", name="fk_print_template_printer_id"),
        nullable=True,
        index=True,
    )
    auto_print: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    copies_rule: Mapped[str] = mapped_column(
        String, nullable=False, default="fixed", server_default="fixed"
    )
    copies_fixed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    max_copies: Mapped[int] = mapped_column(
        Integer, nullable=False, default=50, server_default="50"
    )
    design_dpi: Mapped[int | None] = mapped_column(Integer, nullable=True)
    label_width_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    label_height_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    paper: Mapped[str | None] = mapped_column(String, nullable=True)
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    note: Mapped[str | None] = mapped_column(String, nullable=True)

    # ── Relations ─────────────────────────────────────────────────────
    creator_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_print_template_creator_id"),
        nullable=True,
        index=True,
    )
    creator: Mapped["UserOrmModel | None"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[creator_id],
        lazy="raise_on_sql",
    )
    printer: Mapped["PrinterOrmModel | None"] = relationship(
        "src.modules.quality.adapters.outbound.persistence.models.printer_model.PrinterOrmModel",
        foreign_keys=[printer_id],
        lazy="raise_on_sql",
    )
