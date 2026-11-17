"""
SQLAlchemy ORM model for allocations linking bought item demands to orders
or stock. Infrastructure detail, never imported by domain or application
layers.
"""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from sqlalchemy.sql import text

from src.modules.fulfillment.adapters.outbound.persistence.models._allocation_audit import (
    AllocationAudit,
)
from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.adapters.outbound.persistence.models.quantity_type import QuantityType

if TYPE_CHECKING:
    from src.modules.fulfillment.adapters.outbound.persistence.models.bought_item_demand_item_model import (
        BoughtItemDemandItemOrmModel,
    )
    from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model import (
        OrderItemOrmModel,
    )


class BoughtItemAllocationOrmModel(AllocationAudit, Base):
    __tablename__ = "bought_item_allocation_table"

    # Surrogate PK: order_item_id is nullable (stock-sourced rows have none),
    # so it cannot be part of the primary key. A unique constraint (a real
    # UNIQUE CONSTRAINT in the DB, hence UniqueConstraint here rather than
    # Index) keeps one row per (demand_item, order_item) pair, and a
    # partial unique index keeps at most one stock-sourced row per demand
    # item.
    __table_args__ = (
        UniqueConstraint(
            "demand_item_id",
            "order_item_id",
            name="uq_allocation_demand_order_item",
        ),
        Index(
            "uq_allocation_demand_stock",
            "demand_item_id",
            unique=True,
            postgresql_where=text("source = 'stock'"),
            sqlite_where=text("source = 'stock'"),
        ),
    )

    # No `index=True` here: the PK already provides one, a bare
    # `ix_<table>_id` would be pure duplication.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    demand_item_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("bought_item_demand_item_table.id", name="fk_allocation_demand_item_id"),
        nullable=False,
    )
    order_item_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("order_item_table.id", name="fk_allocation_order_item_id"),
        nullable=True,
        index=True,
    )
    source: Mapped[str] = mapped_column(
        String, nullable=False, default="order", server_default="order"
    )
    quantity: Mapped[float] = mapped_column(QuantityType, nullable=False)
    # Who created the row, empty for a system write.
    created_by_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_bought_item_allocation_created_by_id"),
        nullable=True,
        index=True,
    )
    substitute_item_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("bought_item_table.id", name="fk_allocation_substitute_item_id"),
        nullable=True,
        index=True,
    )
    substitute_reason: Mapped[str | None] = mapped_column(String, nullable=True)

    demand_item: Mapped["BoughtItemDemandItemOrmModel"] = relationship(
        "src.modules.fulfillment.adapters.outbound.persistence.models.bought_item_demand_item_model.BoughtItemDemandItemOrmModel",
        back_populates="allocations",
        lazy="raise_on_sql",
    )
    order_item: Mapped["OrderItemOrmModel"] = relationship(
        "src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model.OrderItemOrmModel",
        back_populates="allocations",
        lazy="raise_on_sql",
    )
