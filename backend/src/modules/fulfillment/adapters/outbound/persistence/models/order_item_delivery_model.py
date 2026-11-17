"""
SQLAlchemy ORM model for order_item_delivery_table: one recorded delivery
event against an order item, capturing the quantity delivered and, when
part of it was rejected, the rejection reason, note, and outcome.
Infrastructure detail, never imported by domain or application layers.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import false
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.adapters.outbound.persistence.models.quantity_type import QuantityType

if TYPE_CHECKING:
    from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model import (
        OrderItemOrmModel,
    )
    from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel


class OrderItemDeliveryOrmModel(Base):
    __tablename__ = "order_item_delivery_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    order_item_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("order_item_table.id", name="fk_order_item_delivery_order_item_id"),
        nullable=False,
        index=True,
    )
    order_item: Mapped["OrderItemOrmModel"] = relationship(
        "src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model.OrderItemOrmModel",
        back_populates="delivery_records",
        lazy="raise_on_sql",
    )

    quantity: Mapped[float] = mapped_column(QuantityType, nullable=False)
    delivery_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    storage_place: Mapped[str | None] = mapped_column(String, nullable=True)

    # Rejection booked alongside this delivery event, see
    # domain/entities/order_item_delivery.py. Nullable/zero-default since
    # most delivery rows reject nothing.
    quantity_rejected: Mapped[float] = mapped_column(
        QuantityType, nullable=False, default=0.0, server_default="0"
    )
    rejection_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    rejection_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    rejection_outcome: Mapped[str | None] = mapped_column(String, nullable=True)

    # A correction row names the delivery row it corrects and why; see
    # domain/entities/order_item_delivery.py.
    corrects_delivery_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "order_item_delivery_table.id", name="fk_order_item_delivery_corrects_delivery_id"
        ),
        nullable=True,
        index=True,
    )
    correction_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # The received material's origin (domain/entities/order_item_delivery.py).
    supplier_batch: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    delivery_note_number: Mapped[str | None] = mapped_column(String, nullable=True)
    certificate_reference: Mapped[str | None] = mapped_column(String, nullable=True)
    damage_noted_on_delivery_note: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )

    receiver_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_order_item_delivery_receiver_id"),
        nullable=True,
        index=True,
    )
    receiver: Mapped["UserOrmModel | None"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[receiver_id],
        lazy="raise_on_sql",
    )
