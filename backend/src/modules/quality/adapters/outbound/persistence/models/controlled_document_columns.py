"""
The columns, constraints and relationships of document control (see
src/modules/quality/domain/entities/controlled_document.py), shared by every table that
holds a controlled document. A model mixes in ControlledDocumentColumns,
names its constraints through CONSTRAINT_PREFIX and adds
controlled_document_table_args() to its __table_args__.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from typing import Any
from typing import ClassVar

from sqlalchemy import JSON
from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import UniqueConstraint
from sqlalchemy import Uuid
from sqlalchemy import text
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import declared_attr
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from src.modules.platform.adapters.outbound.persistence.models.changelog_type import ChangelogType

if TYPE_CHECKING:
    from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel

_USER_MODEL = "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel"


def controlled_document_table_args(prefix: str) -> tuple[Any, ...]:
    """A revision string is unique within its lineage, exactly one revision
    of a lineage is the latest, and a document number names one document,
    which its latest revision stands for."""
    return (
        Index(
            f"uq_{prefix}_document_number_latest",
            "document_number",
            unique=True,
            postgresql_where=text("is_latest IS true"),
            sqlite_where=text("is_latest = 1"),
        ),
        UniqueConstraint("lineage", "revision", name=f"uq_{prefix}_lineage_revision"),
        Index(
            f"uq_{prefix}_lineage_latest",
            "lineage",
            unique=True,
            postgresql_where=text("is_latest IS true"),
            sqlite_where=text("is_latest = 1"),
        ),
    )


def _user_fk(cls: Any, column: str, *, nullable: bool) -> Mapped[Any]:
    return mapped_column(
        Integer,
        ForeignKey("user_table.id", name=f"fk_{cls.CONSTRAINT_PREFIX}_{column}"),
        nullable=nullable,
        index=True,
    )


def _user(cls: Any, column: str) -> Mapped[Any]:
    return relationship(_USER_MODEL, foreign_keys=[getattr(cls, column)], lazy="raise_on_sql")


class ControlledDocumentColumns:
    # The table's own word in constraint names, such as "checklist".
    CONSTRAINT_PREFIX: ClassVar[str]

    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    changes: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(ChangelogType), nullable=False, default=[]
    )

    document_number: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    lineage: Mapped[uuid.UUID] = mapped_column(Uuid(), nullable=False, index=True)
    revision: Mapped[str] = mapped_column(String(16), nullable=False)
    revision_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    is_latest: Mapped[bool] = mapped_column(Boolean, nullable=False)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invalid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invalid_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    editor_ids: Mapped[list[int]] = mapped_column(
        JSON, nullable=False, default=list, server_default=text("'[]'")
    )
    lock_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @declared_attr
    def creator_id(cls) -> Mapped[int]:
        return _user_fk(cls, "creator_id", nullable=False)

    @declared_attr
    def creator(cls) -> Mapped["UserOrmModel"]:
        return _user(cls, "creator_id")

    # Who saved the last change, the person `changed` belongs to.
    @declared_attr
    def changed_by_id(cls) -> Mapped[int | None]:
        return _user_fk(cls, "changed_by_id", nullable=True)

    @declared_attr
    def changed_by(cls) -> Mapped["UserOrmModel | None"]:
        return _user(cls, "changed_by_id")

    @declared_attr
    def released_by_id(cls) -> Mapped[int | None]:
        return _user_fk(cls, "released_by_id", nullable=True)

    @declared_attr
    def released_by(cls) -> Mapped["UserOrmModel | None"]:
        return _user(cls, "released_by_id")

    @declared_attr
    def invalid_by_id(cls) -> Mapped[int | None]:
        return _user_fk(cls, "invalid_by_id", nullable=True)

    @declared_attr
    def invalid_by(cls) -> Mapped["UserOrmModel | None"]:
        return _user(cls, "invalid_by_id")

    @declared_attr
    def locked_by_id(cls) -> Mapped[int | None]:
        return _user_fk(cls, "locked_by_id", nullable=True)

    @declared_attr
    def locked_by(cls) -> Mapped["UserOrmModel | None"]:
        return _user(cls, "locked_by_id")
