"""ORM model for source-item material demands linked to production lots and projects."""

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
from src.modules.platform.adapters.outbound.persistence.models.quantity_type import QuantityType

if TYPE_CHECKING:
    from src.modules.catalogue.adapters.outbound.persistence.models.bought_item_model import (
        BoughtItemOrmModel,
    )
    from src.modules.catalogue.adapters.outbound.persistence.models.source_item_model import (
        SourceItemOrmModel,
    )
    from src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model import (
        ProductionLotOrmModel,
    )
    from src.modules.fulfillment.adapters.outbound.persistence.models.source_item_allocation_model import (
        SourceItemAllocationOrmModel,
    )
    from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel
    from src.modules.workspace.adapters.outbound.persistence.models.project_model import (
        ProjectOrmModel,
    )


class SourceItemDemandItemOrmModel(ChangedByColumns, Base):
    __tablename__ = "source_item_demand_item_table"

    # lot_id is unique only among demands not canceled, because a source
    # switch cancels the lot's demand and inserts its successor for the same
    # lot in one transaction. The index reads the cancel intent, canceled_at,
    # which the cancel records before that insert.
    __table_args__ = (
        Index(
            "uq_source_item_demand_lot_id_active",
            "lot_id",
            unique=True,
            postgresql_where=text("canceled_at IS NULL"),
            sqlite_where=text("canceled_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    changes: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(ChangelogType), nullable=False, default=[]
    )

    status: Mapped[str] = mapped_column(
        String, nullable=False, default="open", server_default="open"
    )
    quantity: Mapped[float] = mapped_column(QuantityType, nullable=False)
    unit: Mapped[str] = mapped_column(String, nullable=False)
    items_per_unit: Mapped[float] = mapped_column(QuantityType, nullable=False, default=1.0)

    high_priority: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    notify_on_delivery: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    note: Mapped[str | None] = mapped_column(String, nullable=True)
    desired_delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Lifecycle intents, see source_item_demand_item.py's matching field comment.
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fulfilled_manually_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Row version for optimistic concurrency control: the mapper's version
    # column, so every ORM update and delete checks the version it read and
    # increments it. A writer whose copy is older than the row gets
    # StaleDataError, which the API answers with 409.
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012 - read once by the mapper

    creator_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_source_item_demand_creator_id"),
        nullable=False,
        index=True,
    )
    creator: Mapped["UserOrmModel"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[creator_id],
        lazy="raise_on_sql",
    )

    bought_item_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("bought_item_table.id", name="fk_source_item_demand_bought_item_id"),
        nullable=True,
        index=True,
    )
    bought_item: Mapped["BoughtItemOrmModel | None"] = relationship(
        "src.modules.catalogue.adapters.outbound.persistence.models.bought_item_model.BoughtItemOrmModel",
        foreign_keys=[bought_item_id],
        lazy="raise_on_sql",
    )

    source_item_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("source_item_table.id", name="fk_source_item_demand_source_item_id"),
        nullable=True,
        index=True,
    )
    source_item: Mapped["SourceItemOrmModel | None"] = relationship(
        "src.modules.catalogue.adapters.outbound.persistence.models.source_item_model.SourceItemOrmModel",
        foreign_keys=[source_item_id],
        lazy="raise_on_sql",
    )

    # Circular FK, intentional: this column and production_lot_table.
    # input_demand_id (production_lot_model.py) form a cycle. This side is
    # NOT NULL, so it is the constrained direction: a demand row cannot
    # precede its lot. See production_lot_model.py's input_demand_id for
    # the full rationale; do not add `use_alter=True`.
    lot_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("production_lot_table.id", name="fk_source_item_demand_lot_id"),
        nullable=False,
    )
    lot: Mapped["ProductionLotOrmModel"] = relationship(
        "src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model.ProductionLotOrmModel",
        foreign_keys=[lot_id],
        lazy="raise_on_sql",
    )

    project_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("project_table.id", name="fk_source_item_demand_project_id"),
        nullable=False,
        index=True,
    )
    project: Mapped["ProjectOrmModel"] = relationship(
        "src.modules.workspace.adapters.outbound.persistence.models.project_model.ProjectOrmModel",
        foreign_keys=[project_id],
        lazy="raise_on_sql",
    )

    # Display state only (see DemandBucketRules), never a
    # business-logic input. SET NULL on delete so removing a bucket
    # un-groups its demands rather than deleting them; SQLite (the test
    # suite) doesn't enforce ondelete itself, so
    # SqlAlchemySourceItemDemandBucketRepository.delete() nulls this
    # column explicitly before deleting the bucket row.
    bucket_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "source_item_demand_bucket_table.id",
            name="fk_source_item_demand_item_bucket_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    allocations: Mapped[list["SourceItemAllocationOrmModel"]] = relationship(
        "src.modules.fulfillment.adapters.outbound.persistence.models.source_item_allocation_model.SourceItemAllocationOrmModel",
        back_populates="demand_item",
        lazy="raise_on_sql",
    )
