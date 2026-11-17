"""
SQLAlchemy ORM model. No config imports. No domain imports.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from sqlalchemy.sql import false
from sqlalchemy.sql import text

from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.adapters.outbound.persistence.models.changed_by_columns import (
    ChangedByColumns,
)
from src.modules.platform.adapters.outbound.persistence.models.changelog_type import ChangelogType
from src.modules.platform.adapters.outbound.persistence.models.edit_version_column import (
    EditVersionColumn,
)

if TYPE_CHECKING:
    from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel


class CustomerOrmModel(EditVersionColumn, ChangedByColumns, Base):
    __tablename__ = "customer_table"

    # Uniqueness of vat_id is scoped to non-archived rows. A plain UNIQUE
    # column would keep an archived customer's VAT id reserved forever,
    # so the repository's uniqueness pre-check had to keep querying
    # archived rows just to avoid an IntegrityError, which in turn leaked
    # archived records back through get_by_vat_id. A partial unique
    # index frees the value on archive and lets every read filter
    # `archived IS false` consistently.
    __table_args__ = (
        Index(
            "uq_customer_vat_id_active",
            "vat_id",
            unique=True,
            postgresql_where=text("archived IS false"),
            sqlite_where=text("archived = 0"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    changes: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(ChangelogType), nullable=False, default=[]
    )
    archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )

    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    legal_name: Mapped[str | None] = mapped_column(String, nullable=True)
    vat_id: Mapped[str | None] = mapped_column(String, nullable=True)
    level: Mapped[str] = mapped_column(
        String, nullable=False, default="B", server_default="B"
    )  # A | B | C

    street: Mapped[str | None] = mapped_column(String, nullable=True)
    city: Mapped[str | None] = mapped_column(String, nullable=True)
    country: Mapped[str | None] = mapped_column(String, nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String, nullable=True)

    email: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    weblink: Mapped[str | None] = mapped_column(String, nullable=True)

    creator_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_customer_table_creator_id_user_table"),
        nullable=False,
        index=True,
    )
    creator: Mapped["UserOrmModel"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[creator_id],
        lazy="raise_on_sql",
    )
