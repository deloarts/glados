"""
SourceItem catalogue record ORM model. No config imports.
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
from src.modules.platform.adapters.outbound.persistence.models.edit_version_column import (
    EditVersionColumn,
)
from src.modules.platform.adapters.outbound.persistence.models.percent_type import PercentType

if TYPE_CHECKING:
    from src.modules.catalogue.adapters.outbound.persistence.models.source_item_file_model import (
        SourceItemFileOrmModel,
    )
    from src.modules.catalogue.adapters.outbound.persistence.models.source_item_type_model import (
        SourceItemTypeOrmModel,
    )
    from src.modules.catalogue.adapters.outbound.persistence.models.supplier_model import (
        SupplierOrmModel,
    )
    from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel


class SourceItemOrmModel(EditVersionColumn, ChangedByColumns, Base):
    __tablename__ = "source_item_table"

    # A live (non-archived) source item's material spec
    # (dimension, type_id, material[, manufacturer_id]) must be unique,
    # split into two partial indexes because a plain UNIQUE treats NULL
    # manufacturer_id as distinct every time, so two "no manufacturer"
    # specs would never collide.
    __table_args__ = (
        Index(
            "uq_source_item_spec_with_manufacturer",
            "dimension",
            "type_id",
            "material",
            "manufacturer_id",
            unique=True,
            postgresql_where=text("manufacturer_id IS NOT NULL AND archived IS FALSE"),
            sqlite_where=text("manufacturer_id IS NOT NULL AND archived = 0"),
        ),
        Index(
            "uq_source_item_spec_without_manufacturer",
            "dimension",
            "type_id",
            "material",
            unique=True,
            postgresql_where=text("manufacturer_id IS NULL AND archived IS FALSE"),
            sqlite_where=text("manufacturer_id IS NULL AND archived = 0"),
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

    # ── Core fields ─────────────────────────────────────────────────────
    type_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("source_item_type_table.id", name="fk_source_item_type_id"),
        nullable=False,
        index=True,
    )
    type: Mapped["SourceItemTypeOrmModel"] = relationship(
        "src.modules.catalogue.adapters.outbound.persistence.models.source_item_type_model.SourceItemTypeOrmModel",
        foreign_keys=[type_id],
        lazy="raise_on_sql",
    )
    dimension: Mapped[str | None] = mapped_column(String, nullable=True)
    material: Mapped[str] = mapped_column(String, nullable=False)
    mass: Mapped[int | None] = mapped_column(Integer, nullable=True)  # in grams
    note: Mapped[str | None] = mapped_column(String, nullable=True)
    order_code_1: Mapped[str | None] = mapped_column(String, nullable=True)
    order_code_2: Mapped[str | None] = mapped_column(String, nullable=True)
    # The item's own delivery tolerances in percent, replacing the ones of
    # the order settings; None takes those.
    over_delivery_tolerance_percent: Mapped[float | None] = mapped_column(
        PercentType, nullable=True
    )
    under_delivery_tolerance_percent: Mapped[float | None] = mapped_column(
        PercentType, nullable=True
    )

    # ── Internal core fields ────────────────────────────────────────────
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")

    successor_item_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("source_item_table.id", name="fk_source_item_successor_id"),
        nullable=True,
        index=True,
    )

    # ── Relations ─────────────────────────────────────────────────────
    creator_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_source_item_creator_id"),
        nullable=False,
        index=True,
    )
    creator: Mapped["UserOrmModel"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[creator_id],
        lazy="raise_on_sql",
    )

    approver_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_source_item_approver_id"),
        nullable=True,
        index=True,
    )
    approver: Mapped["UserOrmModel | None"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[approver_id],
        lazy="raise_on_sql",
    )

    manufacturer_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("supplier_table.id", name="fk_source_item_manufacturer_id"),
        nullable=True,
        index=True,
    )
    manufacturer: Mapped["SupplierOrmModel | None"] = relationship(
        "src.modules.catalogue.adapters.outbound.persistence.models.supplier_model.SupplierOrmModel",
        foreign_keys=[manufacturer_id],
        lazy="raise_on_sql",
    )

    files: Mapped[list["SourceItemFileOrmModel"]] = relationship(
        "src.modules.catalogue.adapters.outbound.persistence.models.source_item_file_model.SourceItemFileOrmModel",
        back_populates="source_item",
        lazy="raise_on_sql",
    )
