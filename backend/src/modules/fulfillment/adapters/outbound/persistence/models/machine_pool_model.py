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
    from src.modules.fulfillment.adapters.outbound.persistence.models.production_machine_model import (
        ProductionMachineOrmModel,
    )
    from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel

# Many-to-many: a pool may group multiple machines.
machine_pool_machine_table = sa.Table(
    "machine_pool_machine_table",
    Base.metadata,
    sa.Column(
        "pool_id",
        Integer,
        ForeignKey(
            "machine_pool_table.id",
            name="fk_machine_pool_machine_pool_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    ),
    sa.Column(
        "machine_id",
        Integer,
        ForeignKey(
            "production_machine_table.id",
            name="fk_machine_pool_machine_machine_id",
        ),
        primary_key=True,
        index=True,
    ),
)


class MachinePoolOrmModel(ChangedByColumns, Base):
    __tablename__ = "machine_pool_table"

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
    # Position in the hand-kept order of the pools, see the entity.
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    # ── Core fields ───────────────────────────────────────────────────
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    note: Mapped[str | None] = mapped_column(String, nullable=True)

    # ── Relations ─────────────────────────────────────────────────────
    creator_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_machine_pool_creator_id"),
        nullable=False,
        index=True,
    )
    creator: Mapped["UserOrmModel"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[creator_id],
        lazy="raise_on_sql",
    )

    machines: Mapped[list["ProductionMachineOrmModel"]] = relationship(
        "src.modules.fulfillment.adapters.outbound.persistence.models.production_machine_model.ProductionMachineOrmModel",
        secondary=machine_pool_machine_table,
        order_by="ProductionMachineOrmModel.id",
        lazy="raise_on_sql",
    )
