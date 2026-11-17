"""
SQLAlchemy ORM model for order_item_table: one line of a purchase order,
exactly one of a bought item, source item, lot position, or free-text
virtual name per line_type, enforced by the check constraint below.
Tracks ordering, delivery, and pickup dates plus running delivered and
rejected quantities. Infrastructure detail, never imported by domain or
application layers.
"""

from datetime import date
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint
from sqlalchemy import Date
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import text
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.adapters.outbound.persistence.models.changed_by_columns import (
    ChangedByColumns,
)
from src.modules.platform.adapters.outbound.persistence.models.changelog_type import ChangelogType
from src.modules.platform.adapters.outbound.persistence.models.quantity_type import QuantityType

if TYPE_CHECKING:
    from src.modules.catalogue.adapters.outbound.persistence.models.bought_item_model import (
        BoughtItemOrmModel,
    )
    from src.modules.catalogue.adapters.outbound.persistence.models.source_item_model import (
        SourceItemOrmModel,
    )
    from src.modules.catalogue.adapters.outbound.persistence.models.supplier_model import (
        SupplierOrmModel,
    )
    from src.modules.fulfillment.adapters.outbound.persistence.models.bought_item_allocation_model import (
        BoughtItemAllocationOrmModel,
    )
    from src.modules.fulfillment.adapters.outbound.persistence.models.lot_position_model import (
        LotPositionOrmModel,
    )
    from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_delivery_model import (
        OrderItemDeliveryOrmModel,
    )
    from src.modules.fulfillment.adapters.outbound.persistence.models.order_model import (
        OrderOrmModel,
    )
    from src.modules.fulfillment.adapters.outbound.persistence.models.quote_request_model import (
        QuoteRequestLineOrmModel,
    )
    from src.modules.fulfillment.adapters.outbound.persistence.models.source_item_allocation_model import (
        SourceItemAllocationOrmModel,
    )
    from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel
    from src.modules.workspace.adapters.outbound.persistence.models.project_model import (
        ProjectOrmModel,
    )


class OrderItemOrmModel(ChangedByColumns, Base):
    __tablename__ = "order_item_table"
    __table_args__ = (
        # Mirrors OrderRules.assert_valid_line_type: exactly one of
        # bought_item_id / source_item_id / lot_position_id / virtual_name
        # identifies the line, matching line_type. Structural exclusivity
        # only, not the denormalized display fields (repository-populated
        # read model), and not virtual_name emptiness (the domain rule's
        # stricter concern).
        CheckConstraint(
            "(line_type = 'BOUGHT' AND bought_item_id IS NOT NULL AND source_item_id IS NULL "
            "AND lot_position_id IS NULL AND virtual_name IS NULL) OR "
            "(line_type = 'SOURCE' AND source_item_id IS NOT NULL AND bought_item_id IS NULL "
            "AND lot_position_id IS NULL AND virtual_name IS NULL) OR "
            "(line_type = 'MADE' AND lot_position_id IS NOT NULL AND bought_item_id IS NULL "
            "AND source_item_id IS NULL AND virtual_name IS NULL) OR "
            "(line_type = 'VIRTUAL' AND virtual_name IS NOT NULL AND bought_item_id IS NULL "
            "AND source_item_id IS NULL AND lot_position_id IS NULL)",
            name="ck_order_item_line_type",
        ),
        # A lot position has at most one open MADE line. Canceled lines stay
        # beside it as history, so the position can be ordered again, and
        # lines closed short stay beside the line that takes the rest.
        Index(
            "uq_order_item_open_lot_position_id",
            "lot_position_id",
            unique=True,
            postgresql_where=text("canceled_at IS NULL AND closed_short_at IS NULL"),
            sqlite_where=text("canceled_at IS NULL AND closed_short_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    changes: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(ChangelogType), nullable=False, default=[]
    )

    status: Mapped[str] = mapped_column(String, nullable=False, default="ordered")
    quantity: Mapped[float] = mapped_column(QuantityType, nullable=False)
    quantity_delivered: Mapped[float] = mapped_column(
        QuantityType, nullable=False, default=0.0, server_default="0"
    )
    # Running totals kept in sync by ProcessOrderItemDelivery; see
    # domain/entities/order_item.py for what each one means.
    quantity_rejected: Mapped[float] = mapped_column(
        QuantityType, nullable=False, default=0.0, server_default="0"
    )
    quantity_rejected_lost: Mapped[float] = mapped_column(
        QuantityType, nullable=False, default=0.0, server_default="0"
    )
    unit: Mapped[str] = mapped_column(String, nullable=False)
    items_per_unit: Mapped[float] = mapped_column(QuantityType, nullable=False, default=1.0)
    price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str | None] = mapped_column(String, nullable=True)

    ordered_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expected_delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    delivery_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    storage_place: Mapped[str | None] = mapped_column(String, nullable=True)

    expected_pickup_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    ready_for_pickup_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Lifecycle intents, see order_item.py's matching field comment.
    requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_short_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_short_from: Mapped[float | None] = mapped_column(QuantityType, nullable=True)
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
        ForeignKey("user_table.id", name="fk_order_item_creator_id"),
        nullable=False,
        index=True,
    )
    creator: Mapped["UserOrmModel"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[creator_id],
        lazy="raise_on_sql",
    )

    orderer_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_order_item_orderer_id"),
        nullable=True,
        index=True,
    )
    orderer: Mapped["UserOrmModel | None"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[orderer_id],
        lazy="raise_on_sql",
    )

    receiver_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_order_item_receiver_id"),
        nullable=True,
        index=True,
    )
    receiver: Mapped["UserOrmModel | None"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[receiver_id],
        lazy="raise_on_sql",
    )

    position: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    # Free-text article name, set ONLY on VIRTUAL lines. Every other line
    # type resolves its display name from its catalogue row instead.
    virtual_name: Mapped[str | None] = mapped_column(String, nullable=True)

    bought_item_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("bought_item_table.id", name="fk_order_item_bought_item_id"),
        nullable=True,
        index=True,
    )
    bought_item: Mapped["BoughtItemOrmModel | None"] = relationship(
        "src.modules.catalogue.adapters.outbound.persistence.models.bought_item_model.BoughtItemOrmModel",
        foreign_keys=[bought_item_id],
        lazy="raise_on_sql",
    )

    order_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("order_table.id", name="fk_order_item_order_id"),
        nullable=False,
        index=True,
    )
    order: Mapped["OrderOrmModel"] = relationship(
        "src.modules.fulfillment.adapters.outbound.persistence.models.order_model.OrderOrmModel",
        back_populates="order_items",
        foreign_keys=[order_id],
        lazy="raise_on_sql",
    )

    supplier_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("supplier_table.id", name="fk_order_item_supplier_id"),
        nullable=False,
        index=True,
    )
    supplier: Mapped["SupplierOrmModel"] = relationship(
        "src.modules.catalogue.adapters.outbound.persistence.models.supplier_model.SupplierOrmModel",
        foreign_keys=[supplier_id],
        lazy="raise_on_sql",
    )

    project_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("project_table.id", name="fk_order_item_project_id"),
        nullable=False,
        index=True,
    )
    project: Mapped["ProjectOrmModel"] = relationship(
        "src.modules.workspace.adapters.outbound.persistence.models.project_model.ProjectOrmModel",
        foreign_keys=[project_id],
        lazy="raise_on_sql",
    )

    line_type: Mapped[str] = mapped_column(
        String, nullable=False, server_default=OrderLineType.default().value
    )
    lot_position_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("lot_position_table.id", name="fk_order_item_lot_position_id"),
        nullable=True,
        index=True,
    )
    lot_position: Mapped["LotPositionOrmModel | None"] = relationship(
        "src.modules.fulfillment.adapters.outbound.persistence.models.lot_position_model.LotPositionOrmModel",
        primaryjoin=(
            "OrderItemOrmModel.lot_position_id == "
            "src.modules.fulfillment.adapters.outbound.persistence.models.lot_position_model.LotPositionOrmModel.id"
        ),
        foreign_keys=[lot_position_id],
        viewonly=True,
        uselist=False,
        # Stays a plain lazy load: change_tracking resolves this row's lot
        # through it inside after_flush, where a lazy load is legal (also
        # under async, which runs flush in a greenlet). Readers that map it
        # load it explicitly.
        lazy="select",
    )

    # The order item's own fixed material identity for a SOURCE line, set
    # once at creation, independent of whichever demands later allocate
    # against it (mirrors bought_item_id's role for BOUGHT lines). A
    # SourceItemDemandAllocation referencing this order item is normally for
    # this same source_item_id, but a source-item-sourced demand may
    # substitute a different one (its allocation row's
    # substitute_source_item_id then equals this source_item_id, see
    # SourceItemAllocationRules.assert_material_matches).
    source_item_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("source_item_table.id", name="fk_order_item_source_item_id"),
        nullable=True,
        index=True,
    )
    # The quote request line an award created this line from; cleared when
    # that line is removed.
    quote_request_line_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "quote_request_line_table.id",
            name="fk_order_item_quote_request_line_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    source_item: Mapped["SourceItemOrmModel | None"] = relationship(
        "src.modules.catalogue.adapters.outbound.persistence.models.source_item_model.SourceItemOrmModel",
        foreign_keys=[source_item_id],
        lazy="raise_on_sql",
    )
    quote_request_line: Mapped["QuoteRequestLineOrmModel | None"] = relationship(
        "src.modules.fulfillment.adapters.outbound.persistence.models.quote_request_model.QuoteRequestLineOrmModel",
        foreign_keys=[quote_request_line_id],
        lazy="raise_on_sql",
    )

    allocations: Mapped[list["BoughtItemAllocationOrmModel"]] = relationship(
        "src.modules.fulfillment.adapters.outbound.persistence.models.bought_item_allocation_model.BoughtItemAllocationOrmModel",
        back_populates="order_item",
        lazy="raise_on_sql",
    )

    source_item_allocations: Mapped[list["SourceItemAllocationOrmModel"]] = relationship(
        "src.modules.fulfillment.adapters.outbound.persistence.models.source_item_allocation_model.SourceItemAllocationOrmModel",
        back_populates="order_item",
        lazy="raise_on_sql",
    )

    delivery_records: Mapped[list["OrderItemDeliveryOrmModel"]] = relationship(
        "src.modules.fulfillment.adapters.outbound.persistence.models.order_item_delivery_model.OrderItemDeliveryOrmModel",
        back_populates="order_item",
        order_by="OrderItemDeliveryOrmModel.id",
        lazy="raise_on_sql",
    )

    # BOUGHT-line shortcuts only. The entity's line-type-agnostic display
    # fields (item_article_name & co.) are resolved in the mapper, which
    # falls back through source_item and made_item, do not confuse the two.
    bought_item_order_code_1 = association_proxy("bought_item", "order_code_1")
    bought_item_order_code_2 = association_proxy("bought_item", "order_code_2")
    bought_item_article_name = association_proxy("bought_item", "article_name")
    bought_item_part_number = association_proxy("bought_item", "part_number")
    supplier_name = association_proxy("supplier", "name")
    project_number = association_proxy("project", "project_number")
    project_status = association_proxy("project", "status")
