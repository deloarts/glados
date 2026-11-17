"""
ORM model for the export journal. Append only. The record an entry names
is kept by type and id without a foreign key, so the entry outlives it.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from typing import Any

from sqlalchemy import JSON
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from src.modules.platform.adapters.outbound.persistence.models.base import Base

if TYPE_CHECKING:
    from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel


class ReportJournalOrmModel(Base):
    __tablename__ = "report_journal_table"
    __table_args__ = (Index("ix_report_journal_table_root_lineage", "root_type", "lineage"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_report_journal_actor_id"),
        nullable=False,
        index=True,
    )
    actor: Mapped["UserOrmModel"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[actor_id],
        lazy="raise_on_sql",
    )
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    document: Mapped[str] = mapped_column(String(64), nullable=False)
    root_type: Mapped[str] = mapped_column(String(32), nullable=False)
    root_id: Mapped[int] = mapped_column(Integer, nullable=False)
    lineage: Mapped[uuid.UUID] = mapped_column(Uuid(), nullable=False)
    revision: Mapped[str] = mapped_column(String(16), nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    options: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    report_version: Mapped[str] = mapped_column(String(64), nullable=False)
    engine_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    print_job_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "print_job_table.id", name="fk_report_journal_print_job_id", ondelete="SET NULL"
        ),
        nullable=True,
        index=True,
    )
    copies: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # The addresses a mailed report went to, To first and then Cc; None for
    # a download or a print.
    recipients: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
