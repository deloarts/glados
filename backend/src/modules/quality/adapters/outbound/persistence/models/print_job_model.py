"""
Append-only audit row. No config imports.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from sqlalchemy.sql import text

from src.modules.platform.adapters.outbound.persistence.models.base import Base

if TYPE_CHECKING:
    from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel


class PrintJobOrmModel(Base):
    __tablename__ = "print_job_table"

    # `created` speeds the audit log's default recency ordering; the
    # partial unique keeps at most one job per (classifier, source_event)
    # pair when a source event is known, so a webhook/event retry can't
    # double-print. Both are DB-only objects (hand-written migration, not
    # `--autogenerate`), declared here so `alembic check` doesn't see
    # them as orphans to drop.
    __table_args__ = (
        Index("ix_print_job_table_created", "created"),
        Index(
            "uq_print_job_classifier_source_event",
            "classifier",
            "source_event_id",
            unique=True,
            postgresql_where=text("source_event_id IS NOT NULL"),
            sqlite_where=text("source_event_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    template_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("print_template_table.id", name="fk_print_job_template_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    printer_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("printer_table.id", name="fk_print_job_printer_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    classifier: Mapped[str] = mapped_column(String, nullable=False)
    root_type: Mapped[str] = mapped_column(String, nullable=False)
    root_id: Mapped[int] = mapped_column(Integer, nullable=False)
    copies: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    rendered_zpl: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trigger: Mapped[str] = mapped_column(String, nullable=False)
    source_event_id: Mapped[str | None] = mapped_column(String, nullable=True)

    actor_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_print_job_actor_id"),
        nullable=False,
        index=True,
    )
    actor: Mapped["UserOrmModel"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[actor_id],
        lazy="raise_on_sql",
    )
