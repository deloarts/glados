"""
ORM models for product devices and their components. Names are unique per
product over all rows, archived ones included, so a device's name and
number never come back for a different device. Infrastructure detail,
never imported by the domain or application layers.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from typing import Any

from sqlalchemy import JSON
from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import UniqueConstraint
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
    from src.modules.catalogue.adapters.outbound.persistence.models.bought_item_model import (
        BoughtItemOrmModel,
    )
    from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel
    from src.modules.workspace.adapters.outbound.persistence.models.product_device_resource_model import (
        ProductDeviceOptionOrmModel,
    )
    from src.modules.workspace.adapters.outbound.persistence.models.product_model import (
        ProductOrmModel,
    )


class ProductDeviceOrmModel(EditVersionColumn, ChangedByColumns, Base):
    __tablename__ = "product_device_table"
    # The edit dialog uploads the images on their own while it is open, so
    # they leave the edit version alone.
    __edit_version_ignored__ = frozenset({"rendering_file_id", "assembly_file_id"})

    # Unlike the live-row indexes of other archivable tables, the name
    # constraints cover archived devices too. A device's name goes into its
    # PLC tags and is frozen into released calculation revisions, so its
    # number never comes back for a different device.
    __table_args__ = (
        UniqueConstraint("product_id", "name_utf8", name="uq_product_device_name_utf8"),
        UniqueConstraint("product_id", "name_ascii_key", name="uq_product_device_name_ascii_key"),
        Index("ix_product_device_group_key", "product_id", "group_key"),
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

    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("product_table.id", name="fk_product_device_product_id"),
        nullable=False,
        index=True,
    )

    location: Mapped[str] = mapped_column(String, nullable=False, default="")
    name: Mapped[str] = mapped_column(String, nullable=False)
    driving_medium_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("product_device_option_table.id", name="fk_product_device_driving_medium_id"),
        nullable=True,
        index=True,
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)

    name_utf8: Mapped[str] = mapped_column(String, nullable=False)
    name_ascii: Mapped[str] = mapped_column(String, nullable=False)
    name_ascii_key: Mapped[str] = mapped_column(String, nullable=False)
    group_key: Mapped[str] = mapped_column(String, nullable=False)

    kind_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("product_device_kind_table.id", name="fk_product_device_kind_id"),
        nullable=False,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(String, nullable=True)

    initial_position_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "product_device_kind_position_table.id",
            name="fk_product_device_initial_position_id",
        ),
        nullable=True,
        index=True,
    )
    initial_position_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    energy_loss_behaviour_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "product_device_option_table.id", name="fk_product_device_energy_loss_behaviour_id"
        ),
        nullable=True,
        index=True,
    )
    energy_restoration_behaviour_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "product_device_option_table.id",
            name="fk_product_device_energy_restoration_behaviour_id",
        ),
        nullable=True,
        index=True,
    )
    monitoring_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    driven_by_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("product_device_table.id", name="fk_product_device_driven_by_id"),
        nullable=True,
        index=True,
    )
    # Driver position id to own position id, for a driver of another kind.
    driven_position_map: Mapped[dict[str, str]] = mapped_column(
        JSON, nullable=False, default=dict, server_default=text("'{}'")
    )
    safety_relevant: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    position_labels: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False, default=dict)
    # Kind position id to the nominal time in ms to reach it.
    travel_times_ms: Mapped[dict[str, int]] = mapped_column(
        JSON, nullable=False, default=dict, server_default=text("'{}'")
    )

    rendering_file_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "product_file_table.id",
            name="fk_product_device_rendering_file_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    assembly_file_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "product_file_table.id",
            name="fk_product_device_assembly_file_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    marker_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    marker_y: Mapped[float | None] = mapped_column(Float, nullable=True)

    creator_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_product_device_creator_id"),
        nullable=False,
        index=True,
    )
    creator: Mapped["UserOrmModel"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[creator_id],
        lazy="raise_on_sql",
    )
    product: Mapped["ProductOrmModel"] = relationship(
        "src.modules.workspace.adapters.outbound.persistence.models.product_model.ProductOrmModel",
        foreign_keys=[product_id],
        lazy="raise_on_sql",
    )
    driving_medium: Mapped["ProductDeviceOptionOrmModel | None"] = relationship(
        "src.modules.workspace.adapters.outbound.persistence.models.product_device_resource_model."
        "ProductDeviceOptionOrmModel",
        foreign_keys=[driving_medium_id],
        lazy="raise_on_sql",
    )
    components: Mapped[list["ProductDeviceComponentOrmModel"]] = relationship(
        back_populates="device",
        lazy="raise_on_sql",
        order_by="ProductDeviceComponentOrmModel.sort_order",
    )


class ProductDeviceComponentOrmModel(Base):
    __tablename__ = "product_device_component_table"

    # Product id is kept on the component so the EPLAN tag can be unique per
    # product in the database, not only in the use case.
    __table_args__ = (
        Index(
            "uq_product_device_component_eplan_tag",
            "product_id",
            "eplan_tag",
            unique=True,
            postgresql_where=text("eplan_tag IS NOT NULL"),
            sqlite_where=text("eplan_tag IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    device_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("product_device_table.id", name="fk_product_device_component_device_id"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("product_table.id", name="fk_product_device_component_product_id"),
        nullable=False,
        index=True,
    )
    role_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("product_device_option_table.id", name="fk_product_device_component_role_id"),
        nullable=False,
        index=True,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    bought_item_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("bought_item_table.id", name="fk_product_device_component_bought_item_id"),
        nullable=True,
        index=True,
    )
    eplan_tag: Mapped[str | None] = mapped_column(String, nullable=True)
    b10d_cycles: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mttfd_years: Mapped[float | None] = mapped_column(Float, nullable=True)
    note: Mapped[str | None] = mapped_column(String, nullable=True)
    # [{"signal_type", "meaning", "confirms_position_id", "drives_position_id",
    # "safety", "address", "tag_suffix", "tag_name", "kind_signal_id"}]; the
    # position ids refer to product_device_kind_position_table and the kind
    # signal id to product_device_kind_signal_table, without a foreign key.
    signals: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)

    device: Mapped["ProductDeviceOrmModel"] = relationship(
        back_populates="components", lazy="raise_on_sql"
    )
    bought_item: Mapped["BoughtItemOrmModel | None"] = relationship(
        "src.modules.catalogue.adapters.outbound.persistence.models.bought_item_model.BoughtItemOrmModel",
        foreign_keys=[bought_item_id],
        lazy="raise_on_sql",
    )
