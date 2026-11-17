"""
SQLAlchemy ORM models for webhook subscriptions and their delivery log.
Infrastructure detail, never imported by domain or application layers.
"""

from datetime import datetime

from sqlalchemy import JSON
from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.sql import true

from src.modules.platform.adapters.outbound.persistence.encrypted_type import EncryptedString
from src.modules.platform.adapters.outbound.persistence.models.base import Base


class WebhookSubscriptionOrmModel(Base):
    __tablename__ = "webhook_subscription_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str] = mapped_column(String, nullable=False)
    # HMAC signing key for deliveries, encrypted at rest rather than hashed
    # because every delivery has to sign with it.
    secret: Mapped[str] = mapped_column(EncryptedString, nullable=False)
    event_types: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list, server_default="[]"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    creator_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_webhook_subscription_table_creator_id_user_table"),
        nullable=False,
        index=True,
    )


class WebhookDeliveryOrmModel(Base):
    __tablename__ = "webhook_delivery_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    subscription_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "webhook_subscription_table.id",
            name="fk_webhook_delivery_table_subscription_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    source_event_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    payload: Mapped[str] = mapped_column(String, nullable=False)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
