"""
ORM model for the admin_planning_settings singleton table.
"""

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import Integer
from sqlalchemy import func
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.modules.fulfillment.domain.entities.admin_settings.planning import (
    DEFAULT_COMMIT_HORIZON_WORKING_DAYS,
)
from src.modules.fulfillment.domain.entities.admin_settings.planning import (
    DEFAULT_PLAN_RETENTION_DAYS,
)
from src.modules.platform.adapters.outbound.persistence.models.base import Base


class AdminPlanningSettingsOrmModel(Base):
    __tablename__ = "admin_planning_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    commit_horizon_working_days: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=str(DEFAULT_COMMIT_HORIZON_WORKING_DAYS)
    )
    plan_retention_days: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=str(DEFAULT_PLAN_RETENTION_DAYS)
    )
    # The moment the row was created, so bookings from before the planning
    # features existed are not judged by them.
    booking_quality_since: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
