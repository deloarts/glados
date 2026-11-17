"""
SQLAlchemy ORM model for made_item_demand_bucket_table: a named, colored
grouping that made item demand items can be assigned to for display,
unique by name. Infrastructure detail, never imported by domain or
application layers.
"""

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.modules.platform.adapters.outbound.persistence.models.base import Base


class MadeItemDemandBucketOrmModel(Base):
    __tablename__ = "made_item_demand_bucket_table"

    __table_args__ = (UniqueConstraint("name", name="uq_made_item_demand_bucket_name"),)

    # ── Server-managed ────────────────────────────────────────────────
    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # ── Core fields ───────────────────────────────────────────────────
    name: Mapped[str] = mapped_column(String, nullable=False)
    color: Mapped[str] = mapped_column(String, nullable=False)

    # ── Audit ─────────────────────────────────────────────────────────
    creator_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_made_item_demand_bucket_creator_id"),
        nullable=False,
        index=True,
    )
