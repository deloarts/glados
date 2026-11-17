"""
ORM model for product_file_table, a file (thumbnail, image, or PDF) uploaded and stored
against a product, recording its storage location, checksum, and uploader.
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
    from src.modules.workspace.adapters.outbound.persistence.models.product_model import (
        ProductOrmModel,
    )


class ProductFileOrmModel(Base):
    __tablename__ = "product_file_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("product_table.id", name="fk_product_file_product_id"),
        nullable=False,
        index=True,
    )
    file_name: Mapped[str] = mapped_column(String, nullable=False)
    stored_name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    mime_type: Mapped[str] = mapped_column(String, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_path: Mapped[str] = mapped_column(String, nullable=False)
    sha256: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(
        String, nullable=False
    )  # ProductFileCategory: thumbnail | image | pdf
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    uploaded_by_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_product_file_uploader_id"),
        nullable=False,
        index=True,
    )

    product: Mapped["ProductOrmModel"] = relationship(
        "src.modules.workspace.adapters.outbound.persistence.models.product_model.ProductOrmModel",
        back_populates="files",
        lazy="raise_on_sql",
    )
