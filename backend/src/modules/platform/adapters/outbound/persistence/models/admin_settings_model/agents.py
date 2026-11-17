"""
ORM model for the admin_agent_settings singleton table.
"""

from datetime import datetime

from sqlalchemy import JSON
from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.modules.platform.adapters.outbound.persistence.models.base import Base


class AdminAgentSettingsOrmModel(Base):
    __tablename__ = "admin_agent_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    token_max_lifetime_days: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="30"
    )
    token_idle_revoke_days: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="14"
    )
    include_person_names: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    include_costs: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    allowed_origins: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list, server_default="[]"
    )
    calls_per_minute: Mapped[int] = mapped_column(Integer, nullable=False, server_default="120")
    drafts_per_hour: Mapped[int] = mapped_column(Integer, nullable=False, server_default="20")
    approved_providers: Mapped[str] = mapped_column(String, nullable=False, server_default="")
    ai_policy_url: Mapped[str | None] = mapped_column(String, nullable=True)
    processing_approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
