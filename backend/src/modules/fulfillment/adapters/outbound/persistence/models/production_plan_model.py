"""
SQLAlchemy ORM models of recorded production plans: one row per plan
version, its order rows and its lot rows. Deleting a plan deletes its rows.
The references to orders, positions and lots are nulled when those are
deleted, and the copied numbers keep the rows readable.
"""

from datetime import date
from datetime import datetime

from sqlalchemy import Date
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import text
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.modules.platform.adapters.outbound.persistence.models.base import Base


class ProductionPlanOrmModel(Base):
    __tablename__ = "production_plan_table"

    # One baseline per tenant day, so a second worker or a retry cannot
    # record the day twice.
    __table_args__ = (
        Index("ix_production_plan_table_plan_day", "plan_day"),
        Index(
            "uq_production_plan_baseline_day",
            "plan_day",
            unique=True,
            postgresql_where=text("kind = 'baseline'"),
            sqlite_where=text("kind = 'baseline'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # PlanKind
    kind: Mapped[str] = mapped_column(String, nullable=False)
    # SchedulerMode
    scheduler_mode: Mapped[str] = mapped_column(String, nullable=False)
    engine: Mapped[str] = mapped_column(String, nullable=False)
    engine_version: Mapped[str] = mapped_column(String, nullable=False)
    plan_day: Mapped[date] = mapped_column(Date, nullable=False)
    # PlanStatus
    status: Mapped[str] = mapped_column(String, nullable=False)


class ProductionPlanEntryOrmModel(Base):
    __tablename__ = "production_plan_entry_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    plan_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "production_plan_table.id", name="fk_production_plan_entry_plan_id", ondelete="CASCADE"
        ),
        nullable=False,
        index=True,
    )
    production_order_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "production_order_table.id",
            name="fk_production_plan_entry_production_order_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    lot_position_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "lot_position_table.id",
            name="fk_production_plan_entry_lot_position_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    # Copied at recording time, so the row reads after a delete.
    lot_id: Mapped[int] = mapped_column(Integer, nullable=False)
    position_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    production_order_number: Mapped[str] = mapped_column(String, nullable=False)
    # The machine and pool the order was queued on, copied like the numbers.
    machine_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    machine_pool_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    queue_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    planned_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    planned_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)


class ProductionPlanLotOrmModel(Base):
    __tablename__ = "production_plan_lot_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    plan_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "production_plan_table.id", name="fk_production_plan_lot_plan_id", ondelete="CASCADE"
        ),
        nullable=False,
        index=True,
    )
    lot_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "production_lot_table.id", name="fk_production_plan_lot_lot_id", ondelete="SET NULL"
        ),
        nullable=True,
        index=True,
    )
    lot_number: Mapped[str] = mapped_column(String, nullable=False)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    planned_finish: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
