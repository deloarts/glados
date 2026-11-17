"""ORM model for production order file metadata (uploaded measurements, reports). No domain
imports."""

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
    from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_model import (
        ProductionOrderOrmModel,
    )


class ProductionOrderFileOrmModel(Base):
    __tablename__ = "production_order_file_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    production_order_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "production_order_table.id",
            name="fk_production_order_file_production_order_id",
            ondelete="CASCADE",
        ),
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
    )  # ProductionOrderFileCategory: measurement_report
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    uploaded_by_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_production_order_file_uploader_id"),
        nullable=False,
        index=True,
    )

    production_order: Mapped["ProductionOrderOrmModel"] = relationship(
        "src.modules.fulfillment.adapters.outbound.persistence.models.production_order_model.ProductionOrderOrmModel",
        back_populates="files",
        lazy="raise_on_sql",
    )
