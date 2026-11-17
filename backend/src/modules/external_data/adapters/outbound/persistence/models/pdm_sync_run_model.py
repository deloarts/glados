"""
The PDM sync run log: one row per poll tick or single-file refresh, and
one child row per file it touched. No config imports.
"""

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.modules.platform.adapters.outbound.persistence.models.base import Base


class PdmSyncRunOrmModel(Base):
    __tablename__ = "pdm_sync_run_table"

    __table_args__ = (Index("ix_pdm_sync_run_started_at", "started_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    trigger: Mapped[str] = mapped_column(String, nullable=False)  # PdmSyncTrigger
    files_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    changed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ingested: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    conflicts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    missing: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    folders_walked: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    # Cold-folder poll cadence (domain.services.pdm_poll_cadence): folders a
    # scheduled run skipped because they were not yet due.
    folders_skipped_cold: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    # Live progress of a running poll (see PdmSyncRun).
    phase: Mapped[str | None] = mapped_column(String, nullable=True)
    current_path: Mapped[str | None] = mapped_column(String, nullable=True)
    files_queued: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    files_processed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    progress_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Requester and reason of a single-file refresh (see PdmSyncRun).
    change_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    change_state: Mapped[str | None] = mapped_column(String, nullable=True)
    requested_by_name: Mapped[str | None] = mapped_column(String, nullable=True)


class PdmSyncRunEntryOrmModel(Base):
    __tablename__ = "pdm_sync_run_entry_table"

    # Indexed on run_id for the entries list (the run's own detail view) and
    # on (vault_id, file_id) for one file's history across runs (the vault
    # add-in's file history); ondelete="CASCADE" so pruning a run
    # (SqlAlchemyPdmSyncRunRepository.prune) never has to delete entries in a
    # second statement.
    __table_args__ = (
        Index("ix_pdm_sync_run_entry_run_id", "run_id"),
        Index("ix_pdm_sync_run_entry_vault_file", "vault_id", "file_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)

    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("pdm_sync_run_table.id", ondelete="CASCADE"), nullable=False
    )
    vault_id: Mapped[str] = mapped_column(String, nullable=False)
    file_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    path: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[str | None] = mapped_column(String, nullable=True)  # "made" | "bought" | None
    action: Mapped[str] = mapped_column(String, nullable=False)
    item_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
