"""
SQLAlchemy ORM model for queued email digest entries.
Infrastructure detail, never imported by domain or application layers.
"""

from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.modules.platform.adapters.outbound.persistence.models.base import Base


class EmailNotificationOrmModel(Base):
    __tablename__ = "email_notification_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)  # "delivered" or "meeting"
    receiver_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # The fulfilled demand, and the order item that delivered it when there was one
    demand_item_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    order_item_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # The meeting whose activity the entry sums up, and that sentence
    meeting_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message: Mapped[str | None] = mapped_column(String, nullable=True)
