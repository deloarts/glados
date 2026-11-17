"""
Findings written by one ReconcilePdmVault run, cascade-deleted with the
PdmSyncRunOrmModel row that owns them. Mirrors pdm_sync_run_entry_table's
own shape (run_id FK, ondelete="CASCADE", indexed on run_id) since a
reconciliation report's findings are read the same way a poll run's
entries are: everything of one run, paged and filtered.
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


class PdmReconciliationFindingOrmModel(Base):
    __tablename__ = "pdm_reconciliation_finding_table"

    __table_args__ = (Index("ix_pdm_reconciliation_finding_run_id", "run_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)

    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("pdm_sync_run_table.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[str] = mapped_column(String, nullable=False)  # PdmReconciliationCategory
    severity: Mapped[str] = mapped_column(String, nullable=False)  # PdmReconciliationSeverity
    kind: Mapped[str | None] = mapped_column(String, nullable=True)
    item_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    part_number: Mapped[str | None] = mapped_column(String, nullable=True)
    revision: Mapped[str | None] = mapped_column(String, nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
