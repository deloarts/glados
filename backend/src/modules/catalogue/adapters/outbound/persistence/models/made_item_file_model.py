"""
SQLAlchemy ORM model for made_item_file_table: one uploaded file attached
to a made item (thumbnail, CAD export, drawing, or similar), storing its
checksum and storage path alongside the uploading user. Infrastructure
detail, never imported by domain or application layers.
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
    from src.modules.catalogue.adapters.outbound.persistence.models.made_item_model import (
        MadeItemOrmModel,
    )


class MadeItemFileOrmModel(Base):
    __tablename__ = "made_item_file_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    made_item_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("made_item_table.id", name="fk_made_item_file_made_item_id"),
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
    )  # MadeItemFileCategory: thumbnail | image | step | mesh | drawing | dxf | pdf
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    uploaded_by_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_made_item_file_uploader_id"),
        nullable=False,
        index=True,
    )

    made_item: Mapped["MadeItemOrmModel"] = relationship(
        "src.modules.catalogue.adapters.outbound.persistence.models.made_item_model.MadeItemOrmModel",
        back_populates="files",
        lazy="raise_on_sql",
    )
