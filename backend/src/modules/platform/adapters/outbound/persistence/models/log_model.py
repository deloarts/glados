"""
SQLAlchemy ORM model. Infrastructure detail, never imported by domain or application.
"""

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.modules.platform.adapters.outbound.persistence.models.base import Base


class LogOrmModel(Base):
    __tablename__ = "log_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    username: Mapped[str | None] = mapped_column(String, nullable=True)
    level: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    message: Mapped[str | None] = mapped_column(String, nullable=True)
    # HTTP-specific, null for app-level log entries
    method: Mapped[str | None] = mapped_column(String(10), nullable=True)
    path: Mapped[str | None] = mapped_column(String, nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Request correlation, set for all log entries emitted inside an HTTP request
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
