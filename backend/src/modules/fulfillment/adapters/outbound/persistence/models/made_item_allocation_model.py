"""
Mirrors bought_item_allocation_model.py minus substitution (made items
don't support substitution).
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
    from src.modules.fulfillment.adapters.outbound.persistence.models.made_item_demand_item_model import (
        MadeItemDemandItemOrmModel,
    )


class MadeItemAllocationOrmModel(AllocationAudit, Base):
    __tablename__ = "made_item_allocation_table"

    # Surrogate PK: mirrors bought_item_allocation_table's rationale. A
    # unique constraint (a real UNIQUE CONSTRAINT in the DB, hence
    # UniqueConstraint here rather than Index) keeps one row per
    # (demand_item, lot) pair, and a partial unique index keeps at most
    # one stock-sourced row per demand item.
    __table_args__ = (
        UniqueConstraint(
            "demand_item_id",
            "lot_id",
            name="uq_made_item_allocation_demand_lot",
        ),
        Index(
            "uq_made_item_allocation_demand_stock",
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
        ForeignKey("made_item_demand_item_table.id", name="fk_made_item_allocation_demand_item_id"),
        nullable=False,
        index=True,
    )
    lot_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("production_lot_table.id", name="fk_made_item_allocation_lot_id"),
        nullable=True,
        index=True,
    )
    source: Mapped[str] = mapped_column(String, nullable=False, default="lot")
    quantity: Mapped[float] = mapped_column(QuantityType, nullable=False)
    # Who created the row, empty for a system write.
    created_by_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_made_item_allocation_created_by_id"),
        nullable=True,
        index=True,
    )

    demand_item: Mapped["MadeItemDemandItemOrmModel"] = relationship(
        "src.modules.fulfillment.adapters.outbound.persistence.models.made_item_demand_item_model.MadeItemDemandItemOrmModel",
        back_populates="allocations",
        lazy="raise_on_sql",
    )
