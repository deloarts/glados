"""ORM model for demand grouping/display buckets (visual state only). No business logic."""

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.modules.platform.adapters.outbound.persistence.models.base import Base


class SourceItemDemandBucketOrmModel(Base):
    __tablename__ = "source_item_demand_bucket_table"

    __table_args__ = (UniqueConstraint("name", name="uq_source_item_demand_bucket_name"),)

    # ── Server-managed ────────────────────────────────────────────────
    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # ── Core fields ───────────────────────────────────────────────────
    name: Mapped[str] = mapped_column(String, nullable=False)
    color: Mapped[str] = mapped_column(String, nullable=False)

    # ── Audit ─────────────────────────────────────────────────────────
    creator_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_source_item_demand_bucket_creator_id"),
        nullable=False,
        index=True,
    )
