"""
Commands and results for the planning settings.
"""

from datetime import datetime

from pydantic import BaseModel
from pydantic import Field

from src.modules.fulfillment.domain.entities.admin_settings.planning import (
    MAX_COMMIT_HORIZON_WORKING_DAYS,
)
from src.modules.fulfillment.domain.entities.admin_settings.planning import MAX_PLAN_RETENTION_DAYS
from src.modules.fulfillment.domain.entities.admin_settings.planning import MIN_PLAN_RETENTION_DAYS
from src.modules.platform.application.dto.base import ResultBase


class UpdatePlanningSettingsCommand(BaseModel):
    commit_horizon_working_days: int | None = Field(
        default=None, ge=1, le=MAX_COMMIT_HORIZON_WORKING_DAYS
    )
    plan_retention_days: int | None = Field(
        default=None, ge=MIN_PLAN_RETENTION_DAYS, le=MAX_PLAN_RETENTION_DAYS
    )


class AdminPlanningSettingsResult(ResultBase):
    commit_horizon_working_days: int
    plan_retention_days: int
    booking_quality_since: datetime
