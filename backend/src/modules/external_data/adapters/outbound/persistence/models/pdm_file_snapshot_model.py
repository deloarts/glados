"""
Diff base for the PDM poller: one row per watched vault file. No config
imports.
"""

from datetime import datetime

from sqlalchemy import JSON
from sqlalchemy import DateTime
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import func
from sqlalchemy import text
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.modules.platform.adapters.outbound.persistence.models.base import Base


class PdmFileSnapshotOrmModel(Base):
    __tablename__ = "pdm_file_snapshot_table"

    # (vault_id, file_id) is the row's identity, mirroring the item link
    # columns' key (docs/reference/field-ownership.md section 1.2).
    # sync_state and last_seen_at are indexed for the pending-list
    # filter/sort and the PdmFileSnapshotResult ordering respectively.
    __table_args__ = (
        Index(
            "uq_pdm_file_snapshot_vault_file",
            "vault_id",
            "file_id",
            unique=True,
        ),
        Index("ix_pdm_file_snapshot_sync_state", "sync_state"),
        Index("ix_pdm_file_snapshot_last_seen_at", "last_seen_at"),
        # find_by_path_suffix's file name prefilter.
        Index("ix_pdm_file_snapshot_vault_name_lower", "vault_id", func.lower(text("name"))),
        # The poller loads snapshots by the folders it walked.
        Index("ix_pdm_file_snapshot_vault_parent_folder", "vault_id", "parent_folder_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)

    vault_id: Mapped[str] = mapped_column(String, nullable=False)
    file_id: Mapped[int] = mapped_column(Integer, nullable=False)
    # "made" | "bought" | None (unresolved, by_kind folder); see the
    # entity's docstring.
    kind: Mapped[str | None] = mapped_column(String, nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    path: Mapped[str] = mapped_column(String, nullable=False)
    parent_folder_id: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    state_id: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String, nullable=False)
    modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_ingested_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sync_state: Mapped[str] = mapped_column(String, nullable=False)  # PdmFileSyncState
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    part_number: Mapped[str | None] = mapped_column(String, nullable=True)
    revision: Mapped[str | None] = mapped_column(String, nullable=True)
    item_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Variables of a parked conflict, so the retry at the end of every poll
    # run can re-attempt IngestPdmFile without re-reading them from PDM.
    parked_payload: Mapped[dict[str, str] | None] = mapped_column(JSON, nullable=True)
    article_name: Mapped[str | None] = mapped_column(String, nullable=True)
