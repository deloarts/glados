"""
SQLAlchemy ORM model for quote_request_file_table: one document a supplier
sent with its offer on a quote request, storing its checksum and storage path
beside the uploading user. Removing the supplier entry removes its files.
"""

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.modules.platform.adapters.outbound.persistence.models.base import Base


class QuoteRequestFileOrmModel(Base):
    __tablename__ = "quote_request_file_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    supplier_row_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "quote_request_supplier_table.id",
            name="fk_quote_request_file_supplier_row_id",
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
    # QuoteFileCategory wire value: offer | general
    category: Mapped[str] = mapped_column(String, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    uploaded_by_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_quote_request_file_uploader_id"),
        nullable=False,
        index=True,
    )
