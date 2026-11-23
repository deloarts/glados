"""
ORM model for order_table, a purchase order placed with a supplier for one or more
bought/made/source items. Tracks status, delivery dates, and the change log, and links to its
order items and attached files.
"""

from datetime import date
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.adapters.outbound.persistence.models.changed_by_columns import (
    ChangedByColumns,
)
from src.modules.platform.adapters.outbound.persistence.models.changelog_type import ChangelogType
from src.modules.platform.adapters.outbound.persistence.models.string_list_type import (
    StringListType,
)

if TYPE_CHECKING:
    from src.modules.catalogue.adapters.outbound.persistence.models.supplier_model import (
        SupplierOrmModel,
    )
    from src.modules.fulfillment.adapters.outbound.persistence.models.order_extra_cost_model import (
        OrderExtraCostOrmModel,
    )
    from src.modules.fulfillment.adapters.outbound.persistence.models.order_file_model import (
        OrderFileOrmModel,
    )
    from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model import (
        OrderItemOrmModel,
    )
    from src.modules.fulfillment.adapters.outbound.persistence.models.quote_request_model import (
        QuoteRequestOrmModel,
    )
    from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel


class OrderOrmModel(ChangedByColumns, Base):
    __tablename__ = "order_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    order_number: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    changes: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(ChangelogType), nullable=False, default=[]
    )

    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    note: Mapped[str | None] = mapped_column(String, nullable=True)

    ordered_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expected_delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    delivery_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    storage_place: Mapped[str | None] = mapped_column(String, nullable=True)
    # The supplier's own numbers for this order, a JSON list as text, so the
    # order filters and the global search can match an entry with LIKE.
    supplier_order_numbers: Mapped[list[str]] = mapped_column(
        StringListType, nullable=False, default=list, server_default="[]"
    )

    # Lifecycle intents, see order.py's matching field comment.
    requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Row version for optimistic concurrency control: the mapper's version
    # column, so every ORM update and delete checks the version it read and
    # increments it. A writer whose copy is older than the row gets
    # StaleDataError, which the API answers with 409.
    # Moves on every user edit and irreversible action only, never on a
    # derived status or a planned date, so a client can send the value it
    # read and learn of a concurrent edit (expected_edit_version).
    edit_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012 - read once by the mapper

    creator_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_order_creator_id"),
        nullable=False,
        index=True,
    )
    creator: Mapped["UserOrmModel"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[creator_id],
        lazy="raise_on_sql",
    )

    supplier_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("supplier_table.id", name="fk_order_supplier_id"),
        nullable=False,
        index=True,
    )
    supplier: Mapped["SupplierOrmModel"] = relationship(
        "src.modules.catalogue.adapters.outbound.persistence.models.supplier_model.SupplierOrmModel",
        foreign_keys=[supplier_id],
        lazy="raise_on_sql",
    )

    order_items: Mapped[list["OrderItemOrmModel"]] = relationship(
        "src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model.OrderItemOrmModel",
        back_populates="order",
        lazy="raise_on_sql",
    )

    files: Mapped[list["OrderFileOrmModel"]] = relationship(
        "src.modules.fulfillment.adapters.outbound.persistence.models.order_file_model.OrderFileOrmModel",
        back_populates="order",
        lazy="raise_on_sql",
    )

    # Written as a whole by the order repository, which deletes the rows a
    # save leaves out.
    extra_costs: Mapped[list["OrderExtraCostOrmModel"]] = relationship(
        "src.modules.fulfillment.adapters.outbound.persistence.models.order_extra_cost_model.OrderExtraCostOrmModel",
        back_populates="order",
        order_by="OrderExtraCostOrmModel.position",
        cascade="all, delete-orphan",
        lazy="raise_on_sql",
    )

    # The quote requests the order's lines were awarded from, reached
    # through each line's link to its request line; read only.
    quote_requests: Mapped[list["QuoteRequestOrmModel"]] = relationship(
        "src.modules.fulfillment.adapters.outbound.persistence.models.quote_request_model.QuoteRequestOrmModel",
        secondary=(
            "join(OrderItemOrmModel, QuoteRequestLineOrmModel, "
            "OrderItemOrmModel.quote_request_line_id == QuoteRequestLineOrmModel.id)"
        ),
        primaryjoin="OrderOrmModel.id == OrderItemOrmModel.order_id",
        secondaryjoin="QuoteRequestLineOrmModel.quote_request_id == QuoteRequestOrmModel.id",
        order_by="QuoteRequestOrmModel.id",
        viewonly=True,
        lazy="raise_on_sql",
    )

    supplier_name = association_proxy("supplier", "name")
    supplier_vat_id = association_proxy("supplier", "vat_id")
