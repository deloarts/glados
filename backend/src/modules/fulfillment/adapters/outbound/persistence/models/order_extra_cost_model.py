"""
ORM model for order_extra_cost_table: one extra cost of a supplier order,
such as shipping, packaging or a surcharge, in net cents. The rows of an
order are written as a whole by the order repository. A cost that names a
line falls back to the whole order when that line is removed.
"""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from src.modules.platform.adapters.outbound.persistence.models.base import Base

if TYPE_CHECKING:
    from src.modules.fulfillment.adapters.outbound.persistence.models.order_model import (
        OrderOrmModel,
    )


class OrderExtraCostOrmModel(Base):
    __tablename__ = "order_extra_cost_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    order_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("order_table.id", name="fk_order_extra_cost_order_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # ExtraCostKind wire value.
    kind: Mapped[str] = mapped_column(String, nullable=False)
    label: Mapped[str | None] = mapped_column(String, nullable=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str | None] = mapped_column(String, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    order_item_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "order_item_table.id", name="fk_order_extra_cost_order_item_id", ondelete="SET NULL"
        ),
        nullable=True,
        index=True,
    )

    order: Mapped["OrderOrmModel"] = relationship(
        "src.modules.fulfillment.adapters.outbound.persistence.models.order_model.OrderOrmModel",
        back_populates="extra_costs",
        lazy="raise_on_sql",
    )
