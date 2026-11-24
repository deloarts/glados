"""
SQLAlchemy ORM model for lot positions (batch groups executed by one
party). Infrastructure detail, never imported by domain or application
layers.
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
from sqlalchemy import UniqueConstraint
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.adapters.outbound.persistence.models.changed_by_columns import (
    ChangedByColumns,
)
from src.modules.platform.adapters.outbound.persistence.models.changelog_type import ChangelogType
from src.modules.platform.adapters.outbound.persistence.models.quantity_type import QuantityType

if TYPE_CHECKING:
    from src.modules.fulfillment.adapters.outbound.persistence.models.lot_step_model import (
        LotStepOrmModel,
    )
    from src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model import (
        ProductionLotOrmModel,
    )
    from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel


class LotPositionOrmModel(ChangedByColumns, Base):
    __tablename__ = "lot_position_table"
    __table_args__ = (
        UniqueConstraint("lot_id", "sequence", name="uq_lot_position_lot_id_sequence"),
        CheckConstraint(
            "quantity_completed <= quantity", name="ck_lot_position_quantity_completed_le_quantity"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    changes: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(ChangelogType), nullable=False, default=[]
    )

    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(
        String, nullable=False, default=LotPositionKind.default().value
    )
    status: Mapped[str] = mapped_column(
        String, nullable=False, default=LotPositionStatus.default().value
    )
    quantity: Mapped[float] = mapped_column(QuantityType, nullable=False)
    quantity_completed: Mapped[float] = mapped_column(QuantityType, nullable=False, default=0.0)
    note: Mapped[str | None] = mapped_column(String, nullable=True)
    # EXTERNAL/MIXED lead-time forecast, written only by the scheduler's
    # recompute (RecomputeMachineSchedule), NULL while the chain feeding
    # this position isn't known yet. See scheduling.ExternalForecast.
    planned_pickup_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    planned_delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # The latest day an external work position can leave for the supplier
    # without making the lot miss its target date, counted back by the same
    # recompute. NULL without a target date. See scheduling.external_work.
    latest_pickup_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # The day it is back at the latest when it leaves on latest_pickup_date,
    # that day plus the position's lead days.
    latest_delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    creator_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_lot_position_creator_id"),
        nullable=False,
        index=True,
    )
    creator: Mapped["UserOrmModel"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[creator_id],
        lazy="raise_on_sql",
    )

    lot_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("production_lot_table.id", name="fk_lot_position_lot_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lot: Mapped["ProductionLotOrmModel"] = relationship(
        "src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model.ProductionLotOrmModel",
        back_populates="positions",
        lazy="raise_on_sql",
    )

    steps: Mapped[list["LotStepOrmModel"]] = relationship(
        "src.modules.fulfillment.adapters.outbound.persistence.models.lot_step_model.LotStepOrmModel",
        back_populates="position",
        foreign_keys="src.modules.fulfillment.adapters.outbound.persistence.models.lot_step_model.LotStepOrmModel.position_id",
        order_by="LotStepOrmModel.sequence",
        cascade="all, delete-orphan",
        lazy="raise_on_sql",
    )
