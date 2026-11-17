"""
ORM models of the quote request (RFQ) aggregate: the request, its lines with
the demand shares they are for, the suppliers asked, each supplier's offer
per line and the extra costs of each offer.

A line identifies what it asks for exactly as an order line does, by line
type and one of bought item, source item, lot position or free text. A
demand share names a bought or source item demand and is no allocation.
Removing a request removes everything below it; removing a lot position
removes the lines that asked for it, and removing a demand removes the
shares that named it, so a delete never fails on a request. An awarded line
names the supplier row that won it; the order line the award created points
back at the line through order_item.quote_request_line_id. A line replaced by
another names its replacement, and a quote for an alternative item names
that item.
"""

from datetime import date
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean
from sqlalchemy import CheckConstraint
from sqlalchemy import Date
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import UniqueConstraint
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

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
    from src.modules.fulfillment.adapters.outbound.persistence.models.lot_position_model import (
        LotPositionOrmModel,
    )
    from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model import (
        OrderItemOrmModel,
    )
    from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel
    from src.modules.workspace.adapters.outbound.persistence.models.project_model import (
        ProjectOrmModel,
    )


class QuoteRequestOrmModel(ChangedByColumns, Base):
    __tablename__ = "quote_request_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    request_number: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    changes: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(ChangelogType), nullable=False, default=[]
    )
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    note: Mapped[str | None] = mapped_column(String, nullable=True)
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Moves on every user edit and irreversible action; the row version
    # below moves on every write and makes a lost race answer 409.
    edit_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012 - read once by the mapper

    creator_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_quote_request_creator_id"),
        nullable=False,
        index=True,
    )
    creator: Mapped["UserOrmModel"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[creator_id],
        lazy="raise_on_sql",
    )

    lines: Mapped[list["QuoteRequestLineOrmModel"]] = relationship(
        back_populates="quote_request",
        order_by="QuoteRequestLineOrmModel.position",
        cascade="all, delete-orphan",
        lazy="raise_on_sql",
    )
    suppliers: Mapped[list["QuoteRequestSupplierOrmModel"]] = relationship(
        back_populates="quote_request",
        order_by="QuoteRequestSupplierOrmModel.position",
        cascade="all, delete-orphan",
        lazy="raise_on_sql",
    )


class QuoteRequestLineOrmModel(Base):
    __tablename__ = "quote_request_line_table"
    __table_args__ = (
        # The same structural exclusivity as ck_order_item_line_type.
        CheckConstraint(
            "(line_type = 'BOUGHT' AND bought_item_id IS NOT NULL AND source_item_id IS NULL "
            "AND lot_position_id IS NULL AND virtual_name IS NULL) OR "
            "(line_type = 'SOURCE' AND source_item_id IS NOT NULL AND bought_item_id IS NULL "
            "AND lot_position_id IS NULL AND virtual_name IS NULL) OR "
            "(line_type = 'MADE' AND lot_position_id IS NOT NULL AND bought_item_id IS NULL "
            "AND source_item_id IS NULL AND virtual_name IS NULL) OR "
            "(line_type = 'VIRTUAL' AND virtual_name IS NOT NULL AND bought_item_id IS NULL "
            "AND source_item_id IS NULL AND lot_position_id IS NULL)",
            name="ck_quote_request_line_line_type",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    quote_request_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "quote_request_table.id", name="fk_quote_request_line_request_id", ondelete="CASCADE"
        ),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    line_type: Mapped[str] = mapped_column(String, nullable=False)
    quantity: Mapped[float] = mapped_column(QuantityType, nullable=False)
    unit: Mapped[str] = mapped_column(String, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    note: Mapped[str | None] = mapped_column(String, nullable=True)
    virtual_name: Mapped[str | None] = mapped_column(String, nullable=True)
    project_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("project_table.id", name="fk_quote_request_line_project_id"),
        nullable=True,
        index=True,
    )
    bought_item_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("bought_item_table.id", name="fk_quote_request_line_bought_item_id"),
        nullable=True,
        index=True,
    )
    source_item_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("source_item_table.id", name="fk_quote_request_line_source_item_id"),
        nullable=True,
        index=True,
    )
    lot_position_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "lot_position_table.id",
            name="fk_quote_request_line_lot_position_id",
            ondelete="CASCADE",
        ),
        nullable=True,
        index=True,
    )
    # Award intents: the supplier row that won the line, at which unit price
    # in cents, when and by whom; dropped_at when nobody gets it.
    awarded_supplier_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "quote_request_supplier_table.id",
            name="fk_quote_request_line_awarded_supplier_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    awarded_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    awarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    awarded_by_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_quote_request_line_awarded_by_id"),
        nullable=True,
        index=True,
    )
    dropped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Why the line asks for another item than its demands, on a line that
    # replaced another; the replaced line names the line that replaced it.
    substitute_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    substituted_by_line_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "quote_request_line_table.id",
            name="fk_quote_request_line_substituted_by_line_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    quote_request: Mapped["QuoteRequestOrmModel"] = relationship(
        back_populates="lines", lazy="raise_on_sql"
    )
    demands: Mapped[list["QuoteRequestLineDemandOrmModel"]] = relationship(
        back_populates="line",
        order_by="QuoteRequestLineDemandOrmModel.id",
        cascade="all, delete-orphan",
        lazy="raise_on_sql",
    )
    bought_item: Mapped["BoughtItemOrmModel | None"] = relationship(
        "src.modules.catalogue.adapters.outbound.persistence.models.bought_item_model.BoughtItemOrmModel",
        lazy="raise_on_sql",
    )
    source_item: Mapped["SourceItemOrmModel | None"] = relationship(
        "src.modules.catalogue.adapters.outbound.persistence.models.source_item_model.SourceItemOrmModel",
        lazy="raise_on_sql",
    )
    lot_position: Mapped["LotPositionOrmModel | None"] = relationship(
        "src.modules.fulfillment.adapters.outbound.persistence.models.lot_position_model.LotPositionOrmModel",
        lazy="raise_on_sql",
    )
    project: Mapped["ProjectOrmModel | None"] = relationship(
        "src.modules.workspace.adapters.outbound.persistence.models.project_model.ProjectOrmModel",
        lazy="raise_on_sql",
    )
    # The order lines an award created for the line; read only, the order
    # line owns the link.
    order_items: Mapped[list["OrderItemOrmModel"]] = relationship(
        "src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model.OrderItemOrmModel",
        primaryjoin=(
            "QuoteRequestLineOrmModel.id == foreign(OrderItemOrmModel.quote_request_line_id)"
        ),
        viewonly=True,
        lazy="raise_on_sql",
    )


class QuoteRequestLineDemandOrmModel(Base):
    __tablename__ = "quote_request_line_demand_table"
    __table_args__ = (
        CheckConstraint(
            "(bought_demand_item_id IS NOT NULL AND source_demand_item_id IS NULL) OR "
            "(source_demand_item_id IS NOT NULL AND bought_demand_item_id IS NULL)",
            name="ck_quote_request_line_demand_one_family",
        ),
        UniqueConstraint(
            "line_id", "bought_demand_item_id", name="uq_quote_request_line_demand_bought"
        ),
        UniqueConstraint(
            "line_id", "source_demand_item_id", name="uq_quote_request_line_demand_source"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    line_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "quote_request_line_table.id",
            name="fk_quote_request_line_demand_line_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    bought_demand_item_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "bought_item_demand_item_table.id",
            name="fk_quote_request_line_demand_bought_id",
            ondelete="CASCADE",
        ),
        nullable=True,
        index=True,
    )
    source_demand_item_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "source_item_demand_item_table.id",
            name="fk_quote_request_line_demand_source_id",
            ondelete="CASCADE",
        ),
        nullable=True,
        index=True,
    )
    quantity: Mapped[float] = mapped_column(QuantityType, nullable=False)

    line: Mapped["QuoteRequestLineOrmModel"] = relationship(
        back_populates="demands", lazy="raise_on_sql"
    )


class QuoteRequestSupplierOrmModel(Base):
    __tablename__ = "quote_request_supplier_table"
    __table_args__ = (
        UniqueConstraint(
            "quote_request_id", "supplier_id", name="uq_quote_request_supplier_request_supplier"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    quote_request_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "quote_request_table.id",
            name="fk_quote_request_supplier_request_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    supplier_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("supplier_table.id", name="fk_quote_request_supplier_supplier_id"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    declined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    note: Mapped[str | None] = mapped_column(String, nullable=True)

    quote_request: Mapped["QuoteRequestOrmModel"] = relationship(
        back_populates="suppliers", lazy="raise_on_sql"
    )
    supplier: Mapped["SupplierOrmModel"] = relationship(
        "src.modules.catalogue.adapters.outbound.persistence.models.supplier_model.SupplierOrmModel",
        lazy="raise_on_sql",
    )
    quotes: Mapped[list["QuoteOrmModel"]] = relationship(
        back_populates="supplier_row",
        order_by="QuoteOrmModel.line_id",
        cascade="all, delete-orphan",
        lazy="raise_on_sql",
    )
    extra_costs: Mapped[list["QuoteExtraCostOrmModel"]] = relationship(
        back_populates="supplier_row",
        order_by="QuoteExtraCostOrmModel.position",
        cascade="all, delete-orphan",
        lazy="raise_on_sql",
    )


class QuoteOrmModel(Base):
    __tablename__ = "quote_table"
    __table_args__ = (
        UniqueConstraint("supplier_row_id", "line_id", name="uq_quote_supplier_row_line"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    supplier_row_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "quote_request_supplier_table.id",
            name="fk_quote_supplier_row_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    line_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("quote_request_line_table.id", name="fk_quote_line_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    unit_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    no_offer: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_quantity: Mapped[float | None] = mapped_column(QuantityType, nullable=True)
    note: Mapped[str | None] = mapped_column(String, nullable=True)
    # The alternative item the supplier offered for the line, of the line's
    # kind, and the reason it gave.
    substitute_bought_item_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("bought_item_table.id", name="fk_quote_substitute_bought_item_id"),
        nullable=True,
        index=True,
    )
    substitute_source_item_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("source_item_table.id", name="fk_quote_substitute_source_item_id"),
        nullable=True,
        index=True,
    )
    substitute_reason: Mapped[str | None] = mapped_column(String, nullable=True)

    supplier_row: Mapped["QuoteRequestSupplierOrmModel"] = relationship(
        back_populates="quotes", lazy="raise_on_sql"
    )
    substitute_bought_item: Mapped["BoughtItemOrmModel | None"] = relationship(
        "src.modules.catalogue.adapters.outbound.persistence.models.bought_item_model.BoughtItemOrmModel",
        lazy="raise_on_sql",
    )
    substitute_source_item: Mapped["SourceItemOrmModel | None"] = relationship(
        "src.modules.catalogue.adapters.outbound.persistence.models.source_item_model.SourceItemOrmModel",
        lazy="raise_on_sql",
    )


class QuoteExtraCostOrmModel(Base):
    __tablename__ = "quote_extra_cost_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    supplier_row_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "quote_request_supplier_table.id",
            name="fk_quote_extra_cost_supplier_row_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    # ExtraCostKind wire value.
    kind: Mapped[str] = mapped_column(String, nullable=False)
    label: Mapped[str | None] = mapped_column(String, nullable=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str | None] = mapped_column(String, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    line_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "quote_request_line_table.id",
            name="fk_quote_extra_cost_line_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    supplier_row: Mapped["QuoteRequestSupplierOrmModel"] = relationship(
        back_populates="extra_costs", lazy="raise_on_sql"
    )
