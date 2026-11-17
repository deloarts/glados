"""
SQLAlchemy ORM model. No config imports. No domain imports.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean
from sqlalchemy import CheckConstraint
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from sqlalchemy.sql import false

from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.adapters.outbound.persistence.models.changed_by_columns import (
    ChangedByColumns,
)
from src.modules.platform.adapters.outbound.persistence.models.edit_version_column import (
    EditVersionColumn,
)

if TYPE_CHECKING:
    from src.modules.catalogue.adapters.outbound.persistence.models.customer_model import (
        CustomerOrmModel,
    )
    from src.modules.catalogue.adapters.outbound.persistence.models.supplier_model import (
        SupplierOrmModel,
    )
    from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel


class ContactOrmModel(EditVersionColumn, ChangedByColumns, Base):
    """A person of a customer or a supplier, or someone independent. It
    keeps no changelog, because a changelog would keep the personal data an
    anonymisation removes."""

    __tablename__ = "contact_table"
    __table_args__ = (
        CheckConstraint(
            "customer_id IS NULL OR supplier_id IS NULL", name="ck_contact_table_one_organisation"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    anonymised_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    role: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    mobile: Mapped[str | None] = mapped_column(String, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    customer_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "customer_table.id",
            name="fk_contact_table_customer_id_customer_table",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    customer: Mapped["CustomerOrmModel | None"] = relationship(
        "src.modules.catalogue.adapters.outbound.persistence.models.customer_model.CustomerOrmModel",
        foreign_keys=[customer_id],
        lazy="raise_on_sql",
    )
    supplier_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "supplier_table.id",
            name="fk_contact_table_supplier_id_supplier_table",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    supplier: Mapped["SupplierOrmModel | None"] = relationship(
        "src.modules.catalogue.adapters.outbound.persistence.models.supplier_model.SupplierOrmModel",
        foreign_keys=[supplier_id],
        lazy="raise_on_sql",
    )
    receives_request_mails: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    receives_order_mails: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )

    creator_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_contact_table_creator_id_user_table"),
        nullable=False,
        index=True,
    )
    creator: Mapped["UserOrmModel"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[creator_id],
        lazy="raise_on_sql",
    )
