"""ORM model for supplier master data: contact, capabilities, article groups, and
fabrication methods."""

from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
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
    from src.modules.catalogue.adapters.outbound.persistence.models.article_group_model import (
        ArticleGroupOrmModel,
    )
    from src.modules.catalogue.adapters.outbound.persistence.models.fabrication_method_model import (
        FabricationMethodOrmModel,
    )
    from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel


supplier_article_group_table = sa.Table(
    "supplier_article_group_table",
    Base.metadata,
    sa.Column(
        "supplier_id",
        Integer,
        ForeignKey("supplier_table.id", name="fk_supplier_article_group_supplier_id"),
        primary_key=True,
    ),
    sa.Column(
        "article_group_id",
        Integer,
        ForeignKey(
            "article_group_table.id",
            name="fk_supplier_article_group_article_group_id",
        ),
        primary_key=True,
        index=True,
    ),
)


supplier_fabrication_method_table = sa.Table(
    "supplier_fabrication_method_table",
    Base.metadata,
    sa.Column(
        "supplier_id",
        Integer,
        ForeignKey("supplier_table.id", name="fk_supplier_fabrication_method_supplier_id"),
        primary_key=True,
    ),
    sa.Column(
        "fabrication_method_id",
        Integer,
        ForeignKey(
            "fabrication_method_table.id",
            name="fk_supplier_fabrication_method_fabrication_method_id",
        ),
        primary_key=True,
        index=True,
    ),
)


class SupplierOrmModel(EditVersionColumn, ChangedByColumns, Base):
    __tablename__ = "supplier_table"

    # Uniqueness of vat_id is scoped to non-archived rows, see
    # customer_model.py for the full rationale. This table is the reason
    # the partial index is needed rather than optional: get_by_vat_id here
    # filters `archived IS false`, so with a globally UNIQUE column,
    # re-using an archived supplier's VAT id would pass the application
    # check and then fail with an IntegrityError.
    __table_args__ = (
        Index(
            "uq_supplier_vat_id_active",
            "vat_id",
            unique=True,
            postgresql_where=text("archived IS false"),
            sqlite_where=text("archived = 0"),
        ),
        Index(
            "uq_supplier_edp_code_active",
            "edp_code",
            unique=True,
            postgresql_where=text("archived IS false"),
            sqlite_where=text("archived = 0"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changed: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changes: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(ChangelogType), nullable=False, default=[]
    )
    archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )

    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    legal_name: Mapped[str | None] = mapped_column(String, nullable=True)
    vat_id: Mapped[str | None] = mapped_column(String, nullable=True)
    level: Mapped[str] = mapped_column(String, nullable=False, default="B")  # A | B | C
    external_lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    edp_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    edp_type_number_first: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    capabilities: Mapped[list["FabricationMethodOrmModel"]] = relationship(
        "src.modules.catalogue.adapters.outbound.persistence.models.fabrication_method_model.FabricationMethodOrmModel",
        secondary=supplier_fabrication_method_table,
        lazy="raise_on_sql",
    )
    article_groups: Mapped[list["ArticleGroupOrmModel"]] = relationship(
        "src.modules.catalogue.adapters.outbound.persistence.models.article_group_model.ArticleGroupOrmModel",
        secondary=supplier_article_group_table,
        lazy="raise_on_sql",
    )

    street: Mapped[str | None] = mapped_column(String, nullable=True)
    city: Mapped[str | None] = mapped_column(String, nullable=True)
    country: Mapped[str | None] = mapped_column(String, nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String, nullable=True)

    email: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    weblink: Mapped[str | None] = mapped_column(String, nullable=True)

    order_email: Mapped[str | None] = mapped_column(String, nullable=True)
    order_language: Mapped[str | None] = mapped_column(String, nullable=True)
    order_template: Mapped[str | None] = mapped_column(String, nullable=True)
    request_email: Mapped[str | None] = mapped_column(String, nullable=True)
    request_language: Mapped[str | None] = mapped_column(String, nullable=True)
    request_template: Mapped[str | None] = mapped_column(String, nullable=True)

    creator_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_supplier_creator_id"),
        nullable=False,
        index=True,
    )
    creator: Mapped["UserOrmModel"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[creator_id],
        lazy="raise_on_sql",
    )
