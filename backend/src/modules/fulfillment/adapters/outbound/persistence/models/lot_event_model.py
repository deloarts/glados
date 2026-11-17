"""
SQLAlchemy ORM model for lot-level audit events. Infrastructure detail,
never imported by domain or application layers.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from typing import Any

from sqlalchemy import JSON
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from src.modules.platform.adapters.outbound.persistence.models.base import Base

if TYPE_CHECKING:
    from src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model import (
        ProductionLotOrmModel,
    )


class LotEventOrmModel(Base):
    __tablename__ = "lot_event_table"

    # No `index=True`/`unique=True` here: the PK already provides both, a
    # bare `ix_<table>_id` would be pure duplication.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    lot_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("production_lot_table.id", name="fk_lot_event_lot_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lot: Mapped["ProductionLotOrmModel"] = relationship(
        "src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model.ProductionLotOrmModel",
        foreign_keys=[lot_id],
        lazy="raise_on_sql",
    )

    # No FK: an audit row must keep meaning after the actor account (or
    # the position/step it names via entity_id) is gone. Mirrors
    # admin_settings_audit.changed_by_id.
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actor_username: Mapped[str | None] = mapped_column(String, nullable=True)
    actor_full_name: Mapped[str] = mapped_column(String, nullable=False)

    event_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    entity: Mapped[str] = mapped_column(String, nullable=False)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    summary: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
