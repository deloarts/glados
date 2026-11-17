"""
ORM model for the manual PLC tags of a product. Infrastructure detail,
never imported by the domain or application layers.
"""

from datetime import datetime

from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.sql import false

from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.adapters.outbound.persistence.models.changed_by_columns import (
    ChangedByColumns,
)


class PlcManualTagOrmModel(ChangedByColumns, Base):
    __tablename__ = "plc_manual_tag_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changed: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("product_table.id", name="fk_plc_manual_tag_product_id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    signal_type: Mapped[str] = mapped_column(String, nullable=False)
    safety: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    address: Mapped[str | None] = mapped_column(String, nullable=True)
    comment: Mapped[str] = mapped_column(String, nullable=False, default="", server_default="")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    creator_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_plc_manual_tag_creator_id"),
        nullable=False,
        index=True,
    )
