"""
Catalogue record ORM model. No config imports.
"""

from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from sqlalchemy.sql import false

from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.adapters.outbound.persistence.models.changed_by_columns import (
    ChangedByColumns,
)
from src.modules.platform.adapters.outbound.persistence.models.changelog_type import ChangelogType

if TYPE_CHECKING:
    from src.modules.catalogue.adapters.outbound.persistence.models.fabrication_method_model import (
        FabricationMethodOrmModel,
    )
    from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel

# Many-to-many: a machine may support multiple fabrication method variants.
machine_fabrication_method_table = sa.Table(
    "machine_fabrication_method_table",
    Base.metadata,
    sa.Column(
        "machine_id",
        Integer,
        ForeignKey(
            "production_machine_table.id",
            name="fk_machine_fabrication_method_machine_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    ),
    sa.Column(
        "fabrication_method_id",
        Integer,
        ForeignKey(
            "fabrication_method_table.id",
            name="fk_machine_fabrication_method_fabrication_method_id",
        ),
        primary_key=True,
        index=True,
    ),
)


class ProductionMachineOrmModel(ChangedByColumns, Base):
    __tablename__ = "production_machine_table"

    # ── Server-managed ────────────────────────────────────────────────
    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    changes: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(ChangelogType), nullable=False, default=[]
    )
    archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    # Position in the hand-kept order of the machines, see the entity.
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    # ── Core fields ───────────────────────────────────────────────────
    internal_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    vendor: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    max_part_dimension: Mapped[str | None] = mapped_column(String, nullable=True)
    note: Mapped[str | None] = mapped_column(String, nullable=True)
    # Dedicated measuring/QA machine, only selectable for inspection-role
    # positions, never for fabrication (see assert_capability_match).
    is_qa_machine: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )

    # ── Relations ─────────────────────────────────────────────────────
    creator_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_production_machine_creator_id"),
        nullable=False,
        index=True,
    )
    creator: Mapped["UserOrmModel"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[creator_id],
        lazy="raise_on_sql",
    )

    fabrication_methods: Mapped[list["FabricationMethodOrmModel"]] = relationship(
        "src.modules.catalogue.adapters.outbound.persistence.models.fabrication_method_model.FabricationMethodOrmModel",
        secondary=machine_fabrication_method_table,
        order_by="FabricationMethodOrmModel.id",
        lazy="raise_on_sql",
    )
