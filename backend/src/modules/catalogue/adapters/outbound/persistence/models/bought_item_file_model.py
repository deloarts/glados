"""
SQLAlchemy ORM model for files attached to bought items. Infrastructure
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
    from src.modules.catalogue.adapters.outbound.persistence.models.bought_item_model import (
        BoughtItemOrmModel,
    )


class BoughtItemFileOrmModel(Base):
    __tablename__ = "bought_item_file_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    bought_item_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("bought_item_table.id", name="fk_bought_item_file_bought_item_id"),
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
    )  # BoughtItemFileCategory: thumbnail | image | step | mesh | pdf
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    uploaded_by_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_bought_item_file_uploader_id"),
        nullable=False,
        index=True,
    )

    bought_item: Mapped["BoughtItemOrmModel"] = relationship(
        "src.modules.catalogue.adapters.outbound.persistence.models.bought_item_model.BoughtItemOrmModel",
        back_populates="files",
        lazy="raise_on_sql",
    )
