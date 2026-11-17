"""
ORM model of the records an agent call created, one row per reference such
as `order:<public id>`. It answers which records an agent created without
searching every call's JSON list, so the web app can mark them in its
lists. Rows go with their call, also when the audit retention purges it.
"""

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.modules.platform.adapters.outbound.persistence.models.base import Base


class AgentCreatedRecordOrmModel(Base):
    __tablename__ = "agent_created_record"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    call_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "agent_call_table.id",
            name="fk_agent_created_record_call_id_agent_call_table",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    ref: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    # The call's time, so the retention purges these rows before their call.
    called_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
