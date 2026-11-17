"""
Application-wide part-number uniqueness ledger ORM model. Per
docs/FIELD_OWNERSHIP.md principle 2, one row per number ever claimed by a
made-item family or a bought item; part_number is the primary key, so the
two catalogues can never claim the same number.
No config imports.
"""

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.modules.platform.adapters.outbound.persistence.models.base import Base


class PartNumberRegistryOrmModel(Base):
    __tablename__ = "part_number_registry"

    part_number: Mapped[str] = mapped_column(String, primary_key=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)  # "made" | "bought"
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
