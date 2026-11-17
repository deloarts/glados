"""
SQLAlchemy ORM model for manufacturing_assessment_table: the operator's
recorded actual setup and per-piece time and complexity for a completed
production order, at most one row per order. Infrastructure detail, never
imported by domain or application layers.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from src.modules.platform.adapters.outbound.persistence.models.base import Base

if TYPE_CHECKING:
    from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_model import (
        ProductionOrderOrmModel,
    )
    from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel


class ManufacturingAssessmentOrmModel(Base):
    __tablename__ = "manufacturing_assessment_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    production_order_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "production_order_table.id",
            name="fk_manufacturing_assessment_production_order_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        unique=True,
        index=True,
    )
    production_order: Mapped["ProductionOrderOrmModel"] = relationship(
        "src.modules.fulfillment.adapters.outbound.persistence.models.production_order_model.ProductionOrderOrmModel",
        foreign_keys=[production_order_id],
        lazy="raise_on_sql",
    )

    operator_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_manufacturing_assessment_operator_id"),
        nullable=False,
        index=True,
    )
    operator: Mapped["UserOrmModel"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[operator_id],
        lazy="raise_on_sql",
    )

    actual_minutes_per_piece: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_setup_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    complexity: Mapped[str] = mapped_column(String, nullable=False)
    note: Mapped[str | None] = mapped_column(String, nullable=True)
