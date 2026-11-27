"""
SQLAlchemy ORM model of a production order interruption: one row per manual
pause or lot hold of an order, closed when the order resumes, is canceled or
is cut back, and deleted with the order.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import text
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from src.modules.fulfillment.domain.value_objects.interruption_reason import InterruptionReason
from src.modules.platform.adapters.outbound.persistence.models.base import Base

if TYPE_CHECKING:
    from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_model import (
        ProductionOrderOrmModel,
    )
    from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel


class ProductionOrderInterruptionOrmModel(Base):
    __tablename__ = "production_order_interruption_table"

    # An order is paused by at most one interruption at a time: a pause and
    # a lot hold both open one only on a running order, and every resume,
    # cancel and forced completion closes the one that is open.
    __table_args__ = (
        Index("ix_production_order_interruption_production_order_id", "production_order_id"),
        Index(
            "uq_production_order_interruption_open",
            "production_order_id",
            unique=True,
            postgresql_where=text("resumed_at IS NULL"),
            sqlite_where=text("resumed_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    production_order_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "production_order_table.id",
            name="fk_production_order_interruption_production_order_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    production_order: Mapped["ProductionOrderOrmModel"] = relationship(
        "src.modules.fulfillment.adapters.outbound.persistence.models.production_order_model.ProductionOrderOrmModel",
        foreign_keys=[production_order_id],
        lazy="raise_on_sql",
    )

    paused_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    paused_by_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_production_order_interruption_paused_by_id"),
        nullable=False,
        index=True,
    )
    paused_by: Mapped["UserOrmModel"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[paused_by_id],
        lazy="raise_on_sql",
    )

    resumed_by_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_production_order_interruption_resumed_by_id"),
        nullable=True,
        index=True,
    )
    resumed_by: Mapped["UserOrmModel | None"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[resumed_by_id],
        lazy="raise_on_sql",
    )

    # The operator who paused the work (production_order_interruption.py).
    paused_operator_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_production_order_interruption_paused_operator_id"),
        nullable=True,
        index=True,
    )

    # The operator who went on with the work when the order's own start
    # resumed it (production_order_interruption.py).
    resumed_operator_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_production_order_interruption_resumed_operator_id"),
        nullable=True,
        index=True,
    )

    # InterruptionEndedBy: a resume, a cancel or a cut; None while open.
    ended_by: Mapped[str | None] = mapped_column(String, nullable=True)

    # PauseCause: the cause picked for a manual pause, if any.
    pause_cause: Mapped[str | None] = mapped_column(String, nullable=True)

    # InterruptionReason: a manual pause or a hold of the order's lot.
    reason: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default=InterruptionReason.default().value,
        server_default=InterruptionReason.default().value,
    )
