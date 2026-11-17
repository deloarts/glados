"""
ORM model of a user's agent consent (domain/entities/agent_consent.py).
"""

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.modules.platform.adapters.outbound.persistence.models.base import Base


class AgentConsentOrmModel(Base):
    __tablename__ = "user_agent_consent"
    __table_args__ = (UniqueConstraint("user_id", name="uq_user_agent_consent_user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "user_table.id",
            name="fk_user_agent_consent_user_id_user_table",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    consent_version: Mapped[int] = mapped_column(Integer, nullable=False)
    consented_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
