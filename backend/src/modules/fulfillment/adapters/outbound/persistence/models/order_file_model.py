"""
SQLAlchemy ORM model for order_file_table: one uploaded file attached to a
purchase order (proposal, order confirmation, delivery note, invoice, or
similar), storing its checksum and storage path alongside the uploading
user. Infrastructure detail, never imported by domain or application
layers.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from src.modules.platform.adapters.outbound.persistence.models.base import Base

if TYPE_CHECKING:
    from src.modules.fulfillment.adapters.outbound.persistence.models.order_model import (
        OrderOrmModel,
    )


class OrderFileOrmModel(Base):
    __tablename__ = "order_file_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    order_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("order_table.id", name="fk_order_file_order_id"),
        nullable=False,
        index=True,
    )
    file_name: Mapped[str] = mapped_column(String, nullable=False)
    stored_name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    mime_type: Mapped[str] = mapped_column(String, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_path: Mapped[str] = mapped_column(String, nullable=False)
    sha256: Mapped[str] = mapped_column(String, nullable=False)
    # OrderFileCategory wire value: proposal | order_confirmation |
    # delivery_note | invoice | general | picture
    category: Mapped[str] = mapped_column(String, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    uploaded_by_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_order_file_uploader_id"),
        nullable=False,
        index=True,
    )
    # The delivery row a picture taken at goods receipt documents; see
    # domain/entities/order_file.py.
    delivery_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("order_item_delivery_table.id", name="fk_order_file_delivery_id"),
        nullable=True,
        index=True,
    )

    order: Mapped["OrderOrmModel"] = relationship(
        "src.modules.fulfillment.adapters.outbound.persistence.models.order_model.OrderOrmModel",
        back_populates="files",
        lazy="raise_on_sql",
    )
