"""
ORM models for the hand-maintained lists product devices pick from: the
plain option lists (driving media, component roles, energy behaviours) and
the device kinds with their positions, parameters and signals. Labels are JSON maps
from language code to text. Infrastructure detail, never imported by the
domain or application layers.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON
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

if TYPE_CHECKING:
    from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel


class ProductDeviceOptionOrmModel(ChangedByColumns, Base):
    __tablename__ = "product_device_option_table"

    # Letters stay unique across archived rows too, so an archived medium's
    # letter in existing device names never means two things.
    __table_args__ = (
        Index(
            "uq_product_device_option_letter",
            "letter",
            unique=True,
            postgresql_where=text("letter IS NOT NULL"),
            sqlite_where=text("letter IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changed: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changes: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(ChangelogType), nullable=False, default=[]
    )

    category: Mapped[str] = mapped_column(String, nullable=False, index=True)
    label: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False)
    letter: Mapped[str | None] = mapped_column(String, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )

    creator_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_product_device_option_creator_id"),
        nullable=False,
        index=True,
    )
    creator: Mapped["UserOrmModel"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[creator_id],
        lazy="raise_on_sql",
    )


class ProductDeviceKindOrmModel(ChangedByColumns, Base):
    __tablename__ = "product_device_kind_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changed: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changes: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(ChangelogType), nullable=False, default=[]
    )

    label: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    without_driving_medium: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )

    creator_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_product_device_kind_creator_id"),
        nullable=False,
        index=True,
    )
    creator: Mapped["UserOrmModel"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[creator_id],
        lazy="raise_on_sql",
    )

    positions: Mapped[list["ProductDeviceKindPositionOrmModel"]] = relationship(
        back_populates="kind",
        lazy="raise_on_sql",
        order_by="ProductDeviceKindPositionOrmModel.sort_order",
    )
    parameters: Mapped[list["ProductDeviceKindParameterOrmModel"]] = relationship(
        back_populates="kind",
        lazy="raise_on_sql",
        order_by="ProductDeviceKindParameterOrmModel.sort_order",
    )
    signals: Mapped[list["ProductDeviceKindSignalOrmModel"]] = relationship(
        back_populates="kind",
        lazy="raise_on_sql",
        order_by="ProductDeviceKindSignalOrmModel.sort_order",
    )


class ProductDeviceKindPositionOrmModel(Base):
    __tablename__ = "product_device_kind_position_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    kind_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("product_device_kind_table.id", name="fk_product_device_kind_position_kind_id"),
        nullable=False,
        index=True,
    )
    label: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False)
    takes_value: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    unit: Mapped[str | None] = mapped_column(String, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    plc_state_name: Mapped[str | None] = mapped_column(String, nullable=True)
    plc_command_name: Mapped[str | None] = mapped_column(String, nullable=True)

    kind: Mapped["ProductDeviceKindOrmModel"] = relationship(
        back_populates="positions", lazy="raise_on_sql"
    )


class ProductDeviceKindParameterOrmModel(Base):
    __tablename__ = "product_device_kind_parameter_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    kind_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("product_device_kind_table.id", name="fk_product_device_kind_parameter_kind_id"),
        nullable=False,
        index=True,
    )
    label: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False)
    unit: Mapped[str | None] = mapped_column(String, nullable=True)
    value_type: Mapped[str] = mapped_column(String, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )

    kind: Mapped["ProductDeviceKindOrmModel"] = relationship(
        back_populates="parameters", lazy="raise_on_sql"
    )


class ProductDeviceKindSignalOrmModel(Base):
    __tablename__ = "product_device_kind_signal_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    kind_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("product_device_kind_table.id", name="fk_product_device_kind_signal_kind_id"),
        nullable=False,
        index=True,
    )
    label: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False)
    signal_type: Mapped[str] = mapped_column(String, nullable=False)
    plc_name: Mapped[str] = mapped_column(String, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )

    kind: Mapped["ProductDeviceKindOrmModel"] = relationship(
        back_populates="signals", lazy="raise_on_sql"
    )
