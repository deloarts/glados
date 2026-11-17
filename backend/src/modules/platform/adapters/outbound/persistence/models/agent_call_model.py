"""
ORM model of the agent call log (domain/entities/agent_call.py).
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON
from sqlalchemy import DateTime
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.modules.platform.adapters.outbound.persistence.models.base import Base


class AgentCallOrmModel(Base):
    __tablename__ = "agent_call_table"
    __table_args__ = (
        Index("ix_agent_call_table_pat_id_called_at", "pat_id", "called_at"),
        Index("ix_agent_call_table_api_key_id_called_at", "api_key_id", "called_at"),
        Index("ix_agent_call_table_user_id_called_at", "user_id", "called_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    called_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    # No foreign keys to the token and user rows: the log outlives a deleted
    # token or user, like the security log, and names them by snapshot.
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    token_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    pat_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    api_key_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_name: Mapped[str] = mapped_column(String, nullable=False)
    tool: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    arguments: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
