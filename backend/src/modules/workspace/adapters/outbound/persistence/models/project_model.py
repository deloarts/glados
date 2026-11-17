"""
SQLAlchemy ORM model. No config imports. No domain imports.
"""

from datetime import date
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean
from sqlalchemy import Date
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
from src.modules.workspace.domain.value_objects.project_status import ProjectStatus

if TYPE_CHECKING:
    from src.modules.catalogue.adapters.outbound.persistence.models.customer_model import (
        CustomerOrmModel,
    )
    from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel
    from src.modules.workspace.adapters.outbound.persistence.models.product_model import (
        ProductOrmModel,
    )


class ProjectOrmModel(ChangedByColumns, Base):
    __tablename__ = "project_table"

    # Uniqueness of project_number is scoped to non-deleted rows, see
    # customer_model.py for the full rationale. A plain UNIQUE column would
    # keep a soft-deleted row's value reserved forever, forcing the
    # repository's uniqueness pre-check to keep reading deleted rows.
    __table_args__ = (
        Index(
            "uq_project_project_number_active",
            "project_number",
            unique=True,
            postgresql_where=text("deleted IS false"),
            sqlite_where=text("deleted = 0"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    changes: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(ChangelogType), nullable=False, default=[]
    )

    project_number: Mapped[str] = mapped_column(String, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)

    customer_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("customer_table.id", name="fk_project_table_customer_id_customer_table"),
        nullable=True,
        index=True,
    )
    customer: Mapped["CustomerOrmModel | None"] = relationship(
        "src.modules.catalogue.adapters.outbound.persistence.models.customer_model.CustomerOrmModel",
        foreign_keys=[customer_id],
        lazy="raise_on_sql",
    )
    status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default=ProjectStatus.default().value,
        server_default=ProjectStatus.default().value,
        index=True,
    )
    deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )

    designated_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_project_table_designated_user_id_user_table"),
        nullable=False,
        index=True,
    )
    designated_user: Mapped["UserOrmModel"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[designated_user_id],
        lazy="raise_on_sql",
    )

    product_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("product_table.id", name="fk_project_table_product_id_product_table"),
        nullable=True,
        index=True,
    )
    product: Mapped["ProductOrmModel | None"] = relationship(
        "src.modules.workspace.adapters.outbound.persistence.models.product_model.ProductOrmModel",
        back_populates="projects",
        foreign_keys=[product_id],
        lazy="raise_on_sql",
    )

    creator_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_project_table_creator_id_user_table"),
        nullable=True,
        index=True,
    )
    creator: Mapped["UserOrmModel | None"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[creator_id],
        lazy="raise_on_sql",
    )

    production_time_budget: Mapped[int | None] = mapped_column(Integer, nullable=True)

    required_delivery_date_made: Mapped[date | None] = mapped_column(Date, nullable=True)
    required_delivery_date_bought: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Moves on every user edit of the project, so a client can send the value
    # it read and learn of a concurrent edit (expected_edit_version).
    edit_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
