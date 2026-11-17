"""
SQLAlchemy ORM model for notification_table: one in-app notification
delivered to a user, with optional links back to the demand, order,
project, product or meeting it concerns, and the event bus message id that
produced it for redelivery idempotency. Infrastructure detail, never
imported by domain or application layers.
"""

from datetime import datetime

from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.sql import false

from src.modules.platform.adapters.outbound.persistence.models.base import Base


class NotificationOrmModel(Base):
    __tablename__ = "notification_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    type: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(String, nullable=False)
    is_read: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Optional context links
    demand_item_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    order_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    project_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    product_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    meeting_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # The producer's event id that produced this row. Unique per user, so
    # a redelivered or republished event inserts nothing a second time.
    source_event_id: Mapped[str | None] = mapped_column(String, nullable=True)

    __table_args__ = (
        # Rows without an event id never conflict, since NULLs are distinct
        # on both dialects. The leading column also serves the lookup by
        # event id alone.
        Index(
            "uq_notification_table_source_event_id_user_id",
            "source_event_id",
            "user_id",
            unique=True,
        ),
    )
