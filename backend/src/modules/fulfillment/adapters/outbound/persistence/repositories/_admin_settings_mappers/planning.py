"""
Row mapping for the admin_planning_settings singleton. Converts the ORM row
to the domain entity and the entity to the column dict the repository
upserts.
"""

from typing import Any

from src.modules.fulfillment.adapters.outbound.persistence.models.admin_settings_model.planning import (
    AdminPlanningSettingsOrmModel,
)
from src.modules.fulfillment.domain.entities.admin_settings.planning import AdminPlanningSettings


def to_entity(o: AdminPlanningSettingsOrmModel) -> AdminPlanningSettings:
    return AdminPlanningSettings(
        id=o.id,
        public_id=o.public_id,
        commit_horizon_working_days=o.commit_horizon_working_days,
        plan_retention_days=o.plan_retention_days,
        booking_quality_since=o.booking_quality_since,
    )


def to_dict(s: AdminPlanningSettings) -> dict[str, Any]:
    return {
        "commit_horizon_working_days": s.commit_horizon_working_days,
        "plan_retention_days": s.plan_retention_days,
        "booking_quality_since": s.booking_quality_since,
    }
