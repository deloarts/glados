"""
The last number drawn per number family and rendered prefix, such as
("lot", "L2026") or ("order", "ORD-26-"). number_counters.py draws from it,
so two creations never compute the same number and a padding that is
outgrown never jams the sequence. The row is locked from the draw until
the transaction ends.
"""

from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.modules.platform.adapters.outbound.persistence.models.base import Base


class NumberCounterOrmModel(Base):
    __tablename__ = "number_counter_table"

    family: Mapped[str] = mapped_column(String(32), primary_key=True)
    prefix: Mapped[str] = mapped_column(String(255), primary_key=True)
    last_value: Mapped[int] = mapped_column(Integer, nullable=False)
