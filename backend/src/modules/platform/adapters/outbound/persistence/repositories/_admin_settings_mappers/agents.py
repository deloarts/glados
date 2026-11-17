"""
Row mapping for the admin_agent_settings singleton. Converts the ORM row to
the domain entity and the entity to the column dict
SqlAlchemyAdminSettingsRepository upserts.
"""

from typing import Any

from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.agents import (
    AdminAgentSettingsOrmModel,
)
from src.modules.platform.domain.entities.admin_settings.agents import AdminAgentSettings


def to_entity(o: AdminAgentSettingsOrmModel) -> AdminAgentSettings:
    return AdminAgentSettings(
        id=o.id,
        public_id=o.public_id,
        enabled=o.enabled,
        token_max_lifetime_days=o.token_max_lifetime_days,
        token_idle_revoke_days=o.token_idle_revoke_days,
        include_person_names=o.include_person_names,
        include_costs=o.include_costs,
        allowed_origins=list(o.allowed_origins or []),
        calls_per_minute=o.calls_per_minute,
        drafts_per_hour=o.drafts_per_hour,
        approved_providers=o.approved_providers,
        ai_policy_url=o.ai_policy_url,
        processing_approved_at=utc_aware(o.processing_approved_at),
    )


def to_dict(s: AdminAgentSettings) -> dict[str, Any]:
    return {
        "enabled": s.enabled,
        "token_max_lifetime_days": s.token_max_lifetime_days,
        "token_idle_revoke_days": s.token_idle_revoke_days,
        "include_person_names": s.include_person_names,
        "include_costs": s.include_costs,
        "allowed_origins": list(s.allowed_origins),
        "calls_per_minute": s.calls_per_minute,
        "drafts_per_hour": s.drafts_per_hour,
        "approved_providers": s.approved_providers,
        "ai_policy_url": s.ai_policy_url,
        "processing_approved_at": s.processing_approved_at,
    }
