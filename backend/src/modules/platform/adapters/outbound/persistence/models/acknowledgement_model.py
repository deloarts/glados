"""
SQLAlchemy ORM models for the acknowledgements feature: an admin-authored
message every selected user must confirm. AcknowledgementRecipientOrmModel
is a join-table row that carries its own extra column (acknowledged_at),
so it is a full mapped class rather than a bare sa.Table (compare
machine_pool_model.py's machine_pool_machine_table, used when a join
carries no data of its own). Being a mapped class is also what makes it
visible to change_tracking.MODEL_TOPICS, which is keyed by ORM model type
and only sees objects that pass through the ORM unit of work.
Infrastructure detail, never imported by domain or application layers.
"""

from datetime import datetime

from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from sqlalchemy.sql import true

from src.modules.platform.adapters.outbound.persistence.models.base import Base


class AcknowledgementOrmModel(Base):
    __tablename__ = "acknowledgements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    text: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    show_when: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_acknowledgements_created_by_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ORM-level cascade, not just the FK's own ondelete=CASCADE below:
    # SQLite (the test database) does not enforce foreign keys by default
    # (see tests/integration/conftest.py's _clean_tables docstring), so a
    # bare session.delete(ack) would silently leave orphaned recipient
    # rows there even though Postgres would clean them up on its own.
    # passive_deletes is left at its default (False), so SQLAlchemy loads
    # and deletes each recipient row individually rather than trusting the
    # database to cascade, which is also what lets change_tracking see
    # each recipient row leave (see change_tracking.MODEL_TOPICS).
    recipients: Mapped[list["AcknowledgementRecipientOrmModel"]] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.acknowledgement_model."
        "AcknowledgementRecipientOrmModel",
        cascade="all, delete-orphan",
        lazy="raise_on_sql",
    )


class AcknowledgementRecipientOrmModel(Base):
    __tablename__ = "acknowledgement_recipients"

    # Composite primary key: this is a join-table row, not an aggregate
    # root, the natural key is (acknowledgement_id, user_id), see
    # domain/entities/acknowledgement.py's AcknowledgementRecipient, which
    # does not extend Entity for the same reason.
    acknowledgement_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "acknowledgements.id",
            name="fk_acknowledgement_recipients_acknowledgement_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "user_table.id", name="fk_acknowledgement_recipients_user_id", ondelete="CASCADE"
        ),
        primary_key=True,
        # In addition to the composite PK's own (leading-column) index:
        # get_pending_for_user looks up by user_id alone, which the
        # composite index (leading on acknowledgement_id) cannot serve.
        index=True,
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
