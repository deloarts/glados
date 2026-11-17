"""
ORM model for idempotency keys. Infrastructure detail, never imported by
domain or application layers.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.modules.platform.adapters.outbound.persistence.models.base import Base


class IdempotencyKeyOrmModel(Base):
    __tablename__ = "idempotency_key_table"
    # One row per user and key: a second insert of the pair waits on this
    # index until the first transaction ends and then fails, which is how a
    # concurrent retry learns of the first request.
    __table_args__ = (
        UniqueConstraint("user_id", "key", name="uq_idempotency_key_table_user_id_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "user_table.id",
            name="fk_idempotency_key_table_user_id_user_table",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    route: Mapped[str] = mapped_column(String, nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    resources: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list, server_default="[]"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
