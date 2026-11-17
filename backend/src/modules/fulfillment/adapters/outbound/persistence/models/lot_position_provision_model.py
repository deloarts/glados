"""
SQLAlchemy ORM model for lot_position_provision_table: a manually recorded
quantity provisioned to a lot position on a given date, with an optional
note and the user who recorded it. Infrastructure detail, never imported
by domain or application layers.
"""

from datetime import date
from datetime import datetime
from typing import TYPE_CHECKING

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
    from src.modules.fulfillment.adapters.outbound.persistence.models.lot_position_model import (
        LotPositionOrmModel,
    )
    from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel


class LotPositionProvisionOrmModel(Base):
    __tablename__ = "lot_position_provision_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    lot_position_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "lot_position_table.id",
            name="fk_lot_position_provision_lot_position_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    lot_position: Mapped["LotPositionOrmModel"] = relationship(
        "src.modules.fulfillment.adapters.outbound.persistence.models.lot_position_model.LotPositionOrmModel",
        foreign_keys=[lot_position_id],
        lazy="raise_on_sql",
    )

    quantity: Mapped[float] = mapped_column(QuantityType, nullable=False)
    provision_date: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[str | None] = mapped_column(String, nullable=True)

    creator_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_lot_position_provision_creator_id"),
        nullable=False,
        index=True,
    )
    creator: Mapped["UserOrmModel"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[creator_id],
        lazy="raise_on_sql",
    )
