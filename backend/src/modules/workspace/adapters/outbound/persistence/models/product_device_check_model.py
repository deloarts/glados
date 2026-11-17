"""
ORM model for the plan ticks of devices: one row per device and plan that
is ticked. Infrastructure detail, never imported by the domain or
application layers.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from src.modules.platform.adapters.outbound.persistence.models.base import Base

if TYPE_CHECKING:
    from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel


class ProductDeviceCheckOrmModel(Base):
    __tablename__ = "product_device_check_table"

    __table_args__ = (
        UniqueConstraint("device_id", "plan", name="uq_product_device_check_device_plan"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    device_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("product_device_table.id", name="fk_product_device_check_device_id"),
        nullable=False,
        index=True,
    )
    plan: Mapped[str] = mapped_column(String, nullable=False)
    checked_by_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_product_device_check_checked_by_id"),
        nullable=False,
        index=True,
    )
    checked_by: Mapped["UserOrmModel"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[checked_by_id],
        lazy="raise_on_sql",
    )
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
