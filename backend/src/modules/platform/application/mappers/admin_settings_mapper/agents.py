"""
Maps the AI agent settings entity to its result DTO.
"""

from src.modules.platform.application.dto.admin_settings_dto.agents import AdminAgentSettingsResult
from src.modules.platform.domain.entities.admin_settings.agents import AdminAgentSettings


class AgentSettingsMapper:
    @staticmethod
    def agents_to_result(e: AdminAgentSettings) -> AdminAgentSettingsResult:
        return AdminAgentSettingsResult(
            id=e.id,
            public_id=e.public_id,
            enabled=e.enabled,
            token_max_lifetime_days=e.token_max_lifetime_days,
            token_idle_revoke_days=e.token_idle_revoke_days,
            include_person_names=e.include_person_names,
            include_costs=e.include_costs,
            allowed_origins=list(e.allowed_origins),
            calls_per_minute=e.calls_per_minute,
            drafts_per_hour=e.drafts_per_hour,
            approved_providers=e.approved_providers,
            ai_policy_url=e.ai_policy_url,
            processing_approved_at=e.processing_approved_at,
        )
