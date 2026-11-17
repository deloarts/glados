"""
ORM model for production_order_completion_table, one recorded output event against a
production order: the quantity produced, its accepted/rejected/rework/scrap split, and who
operated and recorded it.
"""

from datetime import date
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint
from sqlalchemy import Date
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.adapters.outbound.persistence.models.quantity_type import QuantityType

if TYPE_CHECKING:
    from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_model import (
        ProductionOrderOrmModel,
    )
    from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel


class ProductionOrderCompletionOrmModel(Base):
    __tablename__ = "production_order_completion_table"
    __table_args__ = (
        # A reversal books the pieces of the completion it takes back
        # negative, so the sums over an order's completions net out.
        CheckConstraint(
            "quantity_accepted >= 0 OR reverses_completion_id IS NOT NULL",
            name="ck_production_order_completion_accepted_nonneg",
        ),
        CheckConstraint(
            "quantity_rejected >= 0", name="ck_production_order_completion_rejected_nonneg"
        ),
        # Float-tolerant, not exact equality: quantity_accepted/rejected are
        # independently-supplied floats whose sum can differ from `quantity`
        # by IEEE-754 rounding even when the application layer's own
        # epsilon-tolerant check (production_order_rules.
        # resolve_completion_split) already accepted it.
        CheckConstraint(
            "ABS((quantity_accepted + quantity_rejected) - quantity) < 0.000001",
            name="ck_production_order_completion_split",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    production_order_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "production_order_table.id",
            name="fk_production_order_completion_production_order_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    production_order: Mapped["ProductionOrderOrmModel"] = relationship(
        "src.modules.fulfillment.adapters.outbound.persistence.models.production_order_model.ProductionOrderOrmModel",
        back_populates="completions",
        foreign_keys=[production_order_id],
        lazy="raise_on_sql",
    )

    quantity: Mapped[float] = mapped_column(QuantityType, nullable=False)
    quantity_accepted: Mapped[float] = mapped_column(QuantityType, nullable=False)
    quantity_rejected: Mapped[float] = mapped_column(QuantityType, nullable=False)
    # QA disposition split of quantity_rejected, for inspection completions only. See
    # production_order_completion.py's matching field docstring.
    quantity_rework: Mapped[float] = mapped_column(QuantityType, nullable=False, server_default="0")
    quantity_scrap: Mapped[float] = mapped_column(QuantityType, nullable=False, server_default="0")
    # Classified reason for the scrapped portion. See production_order_completion.py's
    # matching field docstring.
    scrap_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    reject_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    completion_date: Mapped[date] = mapped_column(Date, nullable=False)
    # Set on a reversal: the completion it takes back, at most once.
    reverses_completion_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "production_order_completion_table.id",
            name="fk_production_order_completion_reverses_completion_id",
        ),
        nullable=True,
        unique=True,
        index=True,
    )
    note: Mapped[str | None] = mapped_column(String, nullable=True)
    # The machine the batch was booked on; kept when the machine is deleted
    # as an empty reference rather than losing the completion.
    machine_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "production_machine_table.id",
            name="fk_production_order_completion_machine_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    operator_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_production_order_completion_operator_id"),
        nullable=False,
        index=True,
    )
    operator: Mapped["UserOrmModel"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[operator_id],
        lazy="raise_on_sql",
    )

    recorded_by_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_production_order_completion_recorded_by_id"),
        nullable=False,
        index=True,
    )
    recorded_by: Mapped["UserOrmModel"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[recorded_by_id],
        lazy="raise_on_sql",
    )
