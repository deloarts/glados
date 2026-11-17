"""
SQLAlchemy ORM model for the security log. Rows are only ever inserted, and
the log retention never purges this table.
Infrastructure detail, never imported by domain or application layers.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.domain.entities.security_event import CLIENT_IP_MAX_LENGTH
from src.modules.platform.domain.entities.security_event import USER_AGENT_MAX_LENGTH
from src.modules.platform.domain.entities.security_event import USERNAME_MAX_LENGTH


class SecurityEventOrmModel(Base):
    __tablename__ = "security_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    # Users are deactivated rather than deleted, but should a row ever go,
    # the entry keeps the name it copied.
    actor_user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_security_event_actor_user_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_username: Mapped[str | None] = mapped_column(String(USERNAME_MAX_LENGTH), nullable=True)
    target_user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_security_event_target_user_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    target_username: Mapped[str | None] = mapped_column(String(USERNAME_MAX_LENGTH), nullable=True)
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    client_ip: Mapped[str | None] = mapped_column(String(CLIENT_IP_MAX_LENGTH), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(USER_AGENT_MAX_LENGTH), nullable=True)
    detail: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict, server_default="{}"
    )
