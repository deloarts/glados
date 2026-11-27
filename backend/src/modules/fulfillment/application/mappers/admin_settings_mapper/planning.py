"""
Maps the planning settings entity to its result DTO.
"""

from src.modules.fulfillment.application.dto.admin_settings_dto.planning import (
    AdminPlanningSettingsResult,
)
from src.modules.fulfillment.domain.entities.admin_settings.planning import AdminPlanningSettings


class PlanningSettingsMapper:
    @staticmethod
    def planning_to_result(e: AdminPlanningSettings) -> AdminPlanningSettingsResult:
        return AdminPlanningSettingsResult(
            id=e.id,
            public_id=e.public_id,
            commit_horizon_working_days=e.commit_horizon_working_days,
            plan_retention_days=e.plan_retention_days,
            booking_quality_since=e.booking_quality_since,
        )
