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
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from sqlalchemy.sql import false
from sqlalchemy.sql import text
from sqlalchemy.sql import true

from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.adapters.outbound.persistence.models.edit_version_column import (
    EditVersionColumn,
)

if TYPE_CHECKING:
    from src.modules.catalogue.adapters.outbound.persistence.models.customer_model import (
        CustomerOrmModel,
    )
    from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel
    from src.modules.workspace.adapters.outbound.persistence.models.product_file_model import (
        ProductFileOrmModel,
    )
    from src.modules.workspace.adapters.outbound.persistence.models.project_model import (
        ProjectOrmModel,
    )


class ProductOrmModel(EditVersionColumn, Base):
    __tablename__ = "product_table"

    # Uniqueness of product_number is scoped to non-archived rows, see
    # customer_model.py for the full rationale. A plain UNIQUE column would
    # keep an archived row's value reserved forever, forcing the
    # repository's uniqueness pre-check to keep reading archived rows.
    __table_args__ = (
        Index(
            "uq_product_product_number_active",
            "product_number",
            unique=True,
            postgresql_where=text("archived IS false"),
            sqlite_where=text("archived = 0"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    product_number: Mapped[str] = mapped_column(String, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)

    # Machine data for the CE assessment, copied into the product's checklists.
    designation: Mapped[str | None] = mapped_column(String(200), nullable=True)
    machine_type: Mapped[str | None] = mapped_column(String(200), nullable=True)
    installation_site: Mapped[str | None] = mapped_column(String(200), nullable=True)
    installation_location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    planned_placing_on_market: Mapped[date | None] = mapped_column(Date, nullable=True)
    legal_basis: Mapped[str | None] = mapped_column(String(16), nullable=True)
    contains_pneumatics: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    contains_hydraulics: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    contains_electrics: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    contains_robotics: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    plc_environment_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("plc_environment_table.id", name="fk_product_plc_environment_id"),
        nullable=True,
        index=True,
    )

    customer_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("customer_table.id", name="fk_product_table_customer_id_customer_table"),
        nullable=True,
        index=True,
    )
    customer: Mapped["CustomerOrmModel | None"] = relationship(
        "src.modules.catalogue.adapters.outbound.persistence.models.customer_model.CustomerOrmModel",
        foreign_keys=[customer_id],
        lazy="raise_on_sql",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )

    designated_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_product_table_designated_user_id_user_table"),
        nullable=False,
        index=True,
    )
    designated_user: Mapped["UserOrmModel"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[designated_user_id],
        lazy="raise_on_sql",
    )

    creator_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_product_table_creator_id_user_table"),
        nullable=True,
        index=True,
    )
    creator: Mapped["UserOrmModel | None"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[creator_id],
        lazy="raise_on_sql",
    )

    projects: Mapped[list["ProjectOrmModel"]] = relationship(
        "src.modules.workspace.adapters.outbound.persistence.models.project_model.ProjectOrmModel",
        back_populates="product",
        foreign_keys="ProjectOrmModel.product_id",
        lazy="raise_on_sql",
    )

    files: Mapped[list["ProductFileOrmModel"]] = relationship(
        "src.modules.workspace.adapters.outbound.persistence.models.product_file_model.ProductFileOrmModel",
        back_populates="product",
        lazy="raise_on_sql",
    )
