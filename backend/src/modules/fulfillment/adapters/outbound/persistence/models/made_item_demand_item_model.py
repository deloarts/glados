"""
SQLAlchemy ORM model for made_item_demand_item_table: one demand for a
quantity of a made item within a project, covered over time by
allocations, optionally flagged as an alteration of another made item and
grouped into a display bucket. Infrastructure detail, never imported by
domain or application layers.
"""

from datetime import date
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean
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
from sqlalchemy.sql import false

from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.adapters.outbound.persistence.models.changed_by_columns import (
    ChangedByColumns,
)
from src.modules.platform.adapters.outbound.persistence.models.changelog_type import ChangelogType
from src.modules.platform.adapters.outbound.persistence.models.quantity_type import QuantityType

if TYPE_CHECKING:
    from src.modules.catalogue.adapters.outbound.persistence.models.made_item_model import (
        MadeItemOrmModel,
    )
    from src.modules.fulfillment.adapters.outbound.persistence.models.made_item_allocation_model import (
        MadeItemAllocationOrmModel,
    )
    from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel
    from src.modules.workspace.adapters.outbound.persistence.models.project_model import (
        ProjectOrmModel,
    )


class MadeItemDemandItemOrmModel(ChangedByColumns, Base):
    __tablename__ = "made_item_demand_item_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    changes: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(ChangelogType), nullable=False, default=[]
    )

    status: Mapped[str] = mapped_column(String, nullable=False, default="open", index=True)
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

    # Lifecycle intents, see made_item_demand_item.py's matching field comment.
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

    is_alteration: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )

    creator_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_made_item_demand_item_creator_id"),
        nullable=False,
        index=True,
    )
    creator: Mapped["UserOrmModel"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[creator_id],
        lazy="raise_on_sql",
    )

    made_item_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("made_item_table.id", name="fk_made_item_demand_item_made_item_id"),
        nullable=False,
        index=True,
    )
    item: Mapped["MadeItemOrmModel"] = relationship(
        "src.modules.catalogue.adapters.outbound.persistence.models.made_item_model.MadeItemOrmModel",
        foreign_keys=[made_item_id],
        lazy="raise_on_sql",
    )

    alteration_of_made_item_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "made_item_table.id", name="fk_made_item_demand_item_alteration_of_made_item_id"
        ),
        nullable=True,
        index=True,
    )
    alteration_of_made_item: Mapped["MadeItemOrmModel | None"] = relationship(
        "src.modules.catalogue.adapters.outbound.persistence.models.made_item_model.MadeItemOrmModel",
        foreign_keys=[alteration_of_made_item_id],
        lazy="raise_on_sql",
    )

    project_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("project_table.id", name="fk_made_item_demand_item_project_id"),
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
    # SqlAlchemyMadeItemDemandBucketRepository.delete() nulls this
    # column explicitly before deleting the bucket row.
    bucket_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "made_item_demand_bucket_table.id",
            name="fk_made_item_demand_item_bucket_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    allocations: Mapped[list["MadeItemAllocationOrmModel"]] = relationship(
        "src.modules.fulfillment.adapters.outbound.persistence.models.made_item_allocation_model.MadeItemAllocationOrmModel",
        back_populates="demand_item",
        lazy="raise_on_sql",
    )

    # Association proxies, for get_multi joins only, not for serialization
    item_part_number = association_proxy("item", "part_number")
    item_article_name = association_proxy("item", "article_name")
    project_number = association_proxy("project", "project_number")
    project_customer_id = association_proxy("project", "customer_id")
    project_status = association_proxy("project", "status")
