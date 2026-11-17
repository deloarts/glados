"""
ORM models for the machine calendar aggregate: a machine's own
weekly-hours override, plus per-date calendar exceptions. No config
imports.
"""

from datetime import date
from datetime import datetime
from typing import TYPE_CHECKING
from typing import Any

from sqlalchemy import JSON
from sqlalchemy import Date
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import UniqueConstraint
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
    from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel


class MachineWorkingHoursOrmModel(ChangedByColumns, Base):
    __tablename__ = "machine_working_hours_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    changes: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(ChangelogType), nullable=False, default=[]
    )

    # weekday (str "0"=Monday..str "6"=Sunday) -> working intervals
    # (repositories/_calendar_hours.py)
    weekly_hours: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    creator_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_machine_working_hours_creator_id"),
        nullable=False,
        index=True,
    )
    creator: Mapped["UserOrmModel"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[creator_id],
        lazy="raise_on_sql",
    )

    machine_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "production_machine_table.id",
            name="fk_machine_working_hours_machine_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        unique=True,
    )


class MachineCalendarExceptionOrmModel(ChangedByColumns, Base):
    __tablename__ = "machine_calendar_exception_table"
    __table_args__ = (
        UniqueConstraint(
            "machine_id", "exception_date", name="uq_machine_calendar_exception_machine_date"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    changes: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(ChangelogType), nullable=False, default=[]
    )

    exception_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    available_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    # Local minutes after midnight the available minutes start at.
    start_minute: Mapped[int] = mapped_column(Integer, nullable=False, server_default="480")
    note: Mapped[str | None] = mapped_column(String, nullable=True)

    creator_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_machine_calendar_exception_creator_id"),
        nullable=False,
        index=True,
    )
    creator: Mapped["UserOrmModel"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[creator_id],
        lazy="raise_on_sql",
    )

    machine_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "production_machine_table.id",
            name="fk_machine_calendar_exception_machine_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
