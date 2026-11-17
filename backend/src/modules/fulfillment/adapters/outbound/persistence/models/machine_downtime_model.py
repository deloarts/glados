"""
ORM model for MachineDowntime. The partial unique index that allows at
most one open row per machine lives on the model, so the SQLite
integration suite enforces the same constraint as Postgres.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import text
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

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


class MachineDowntimeOrmModel(ChangedByColumns, Base):
    __tablename__ = "machine_downtime_table"
    __table_args__ = (
        Index(
            "uq_machine_downtime_open_per_machine",
            "machine_id",
            unique=True,
            postgresql_where=text("ended_at IS NULL"),
            sqlite_where=text("ended_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    changes: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(ChangelogType), nullable=False, default=[]
    )

    machine_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "production_machine_table.id",
            name="fk_machine_downtime_machine_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    machine: Mapped["ProductionMachineOrmModel"] = relationship(
        "src.modules.fulfillment.adapters.outbound.persistence.models.production_machine_model.ProductionMachineOrmModel",
        foreign_keys=[machine_id],
        lazy="raise_on_sql",
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    reason: Mapped[str] = mapped_column(String, nullable=False)
    note: Mapped[str | None] = mapped_column(String, nullable=True)

    reported_by_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_machine_downtime_reported_by_id"),
        nullable=False,
        index=True,
    )
    reported_by: Mapped["UserOrmModel"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[reported_by_id],
        lazy="raise_on_sql",
    )

    ended_by_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_machine_downtime_ended_by_id"),
        nullable=True,
        index=True,
    )
    ended_by: Mapped["UserOrmModel | None"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[ended_by_id],
        lazy="raise_on_sql",
    )
