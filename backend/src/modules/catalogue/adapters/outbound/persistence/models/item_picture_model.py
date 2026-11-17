"""
SQLAlchemy ORM model for item pictures (made, bought and source items).
One table for all three kinds, since a picture has the same shape whatever
it belongs to: exactly one of the three item foreign keys is set, and each
item holds at most one picture per source. Infrastructure detail, never
imported by domain or application layers.
"""

from datetime import datetime

from sqlalchemy import CheckConstraint
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.modules.platform.adapters.outbound.persistence.models.base import Base


class ItemPictureOrmModel(Base):
    __tablename__ = "item_picture_table"
    __table_args__ = (
        CheckConstraint(
            "(CASE WHEN made_item_id IS NULL THEN 0 ELSE 1 END)"
            " + (CASE WHEN bought_item_id IS NULL THEN 0 ELSE 1 END)"
            " + (CASE WHEN source_item_id IS NULL THEN 0 ELSE 1 END) = 1",
            name="ck_item_picture_one_item",
        ),
        UniqueConstraint("made_item_id", "source", name="uq_item_picture_made_item_source"),
        UniqueConstraint("bought_item_id", "source", name="uq_item_picture_bought_item_source"),
        UniqueConstraint("source_item_id", "source", name="uq_item_picture_source_item_source"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    made_item_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("made_item_table.id", name="fk_item_picture_made_item_id"),
        nullable=True,
    )
    bought_item_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("bought_item_table.id", name="fk_item_picture_bought_item_id"),
        nullable=True,
    )
    source_item_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("source_item_table.id", name="fk_item_picture_source_item_id"),
        nullable=True,
    )
    source: Mapped[str] = mapped_column(String, nullable=False)  # ItemPictureSource
    file_name: Mapped[str] = mapped_column(String, nullable=False)
    image_path: Mapped[str | None] = mapped_column(String, nullable=True)
    image_mime_type: Mapped[str | None] = mapped_column(String, nullable=True)
    image_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    thumbnail_path: Mapped[str | None] = mapped_column(String, nullable=True)
    thumbnail_mime_type: Mapped[str | None] = mapped_column(String, nullable=True)
    thumbnail_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256: Mapped[str] = mapped_column(String, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    uploaded_by_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_item_picture_uploader_id"),
        nullable=False,
        index=True,
    )
