"""
SQLAlchemy ORM model for the transactional event outbox.

A domain event is staged as a row in the SAME transaction as the write that
produced it, and relayed to the Redis stream afterwards by OutboxRelay. That
is what makes delivery as durable as the write: neither a process crash nor a
Redis outage between the two can lose the event, because the event never
existed only in memory.

Infrastructure detail, never imported by domain or application layers.
"""

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.modules.platform.adapters.outbound.persistence.models.base import Base


class EventOutboxOrmModel(Base):
    __tablename__ = "event_outbox_table"

    # The relay reads and publishes a batch by this, but ids are assigned at
    # insert and rows appear at commit, so it is no total order of events.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    # Producer-assigned identity, travels to consumers as the stream's
    # `event_id` field and becomes their `source_event_id`. Stable across a
    # relay re-publish, which is what keeps the consumers' idempotency guards
    # working when a crash between XADD and the published_at mark produces a
    # second stream message for the same event.
    event_id: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[str] = mapped_column(String, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # NULL = not yet on the stream. See the partial index below.
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(String, nullable=True)

    __table_args__ = (
        # Partial index over the backlog only: the relay's poll stays
        # O(unpublished), not O(history), however large the retained table
        # grows (the same partial index technique as the uq_*_active indexes).
        Index(
            "ix_event_outbox_table_unpublished",
            "id",
            postgresql_where=published_at.is_(None),
            sqlite_where=published_at.is_(None),
        ),
    )
