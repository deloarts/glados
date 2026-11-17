"""
SQLAlchemy ORM model for backup_runs: one durable row per due cron slot (or
manual run-now instant). The `slot` UNIQUE constraint is what makes
claiming it exactly-once across the four gunicorn workers, see
IBackupRunRepository.try_claim, which does an INSERT ... ON CONFLICT DO
NOTHING against this constraint so only one worker's insert succeeds.

Infrastructure detail, never imported by domain or application layers.
"""

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.modules.platform.adapters.outbound.persistence.models.base import Base


class BackupRunOrmModel(Base):
    __tablename__ = "backup_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    slot: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, unique=True, index=True
    )
    trigger: Mapped[str] = mapped_column(String, nullable=False)  # BackupRunTrigger
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)  # BackupRunStatus
    db_key: Mapped[str | None] = mapped_column(String, nullable=True)
    files_key: Mapped[str | None] = mapped_column(String, nullable=True)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    worker: Mapped[str] = mapped_column(String, nullable=False)
