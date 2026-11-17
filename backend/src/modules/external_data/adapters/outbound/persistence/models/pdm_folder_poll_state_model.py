"""
Per-watched-folder poll cadence state for the PDM poller's cold-folder
backoff. No config imports.
"""

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.modules.platform.adapters.outbound.persistence.models.base import Base


class PdmFolderPollStateOrmModel(Base):
    __tablename__ = "pdm_folder_poll_state_table"

    # (vault_id, folder_key) is the row's identity, one row per watched
    # folder a scheduled run has actually walked.
    __table_args__ = (
        Index(
            "uq_pdm_folder_poll_state_vault_folder",
            "vault_id",
            "folder_key",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)

    vault_id: Mapped[str] = mapped_column(String, nullable=False)
    folder_key: Mapped[str] = mapped_column(String, nullable=False)
    consecutive_unchanged_runs: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    next_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
