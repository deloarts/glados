"""Replaces the AI agent settings and audits the change.

Recording the company's approval of AI processing stamps the time it was
given. The stamp is renewed whenever the settings change something a user's
consent covers, the approved providers, the AI policy or whether names and
prices leave in results, so every user confirms the new terms before their
agent calls again. Switching agent access on or off and giving, renewing or
withdrawing the approval are named in the audit summary, since they decide
whether agents reach Glados at all."""

from datetime import datetime

from src.modules.platform.application.dto.admin_settings_dto.agents import AdminAgentSettingsResult
from src.modules.platform.application.dto.admin_settings_dto.agents import (
    UpdateAgentSettingsCommand,
)
from src.modules.platform.application.mappers.admin_settings_mapper.agents import (
    AgentSettingsMapper,
)
from src.modules.platform.domain.entities.admin_settings.agents import AdminAgentSettings
from src.modules.platform.domain.entities.admin_settings.audit import AdminSettingsAuditEntry
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.agent_policy import consent_terms_changed
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc


class UpdateAgentSettings:
    def __init__(self, repo: IPlatformSettingsRepository, *, uow: IUnitOfWork) -> None:
        self._repo = repo
        self._uow = uow

    async def execute(
        self, actor: User, cmd: UpdateAgentSettingsCommand
    ) -> AdminAgentSettingsResult:
        SettingsRules.assert_can_write(actor)

        previous = await self._repo.get_agents()
        settings = AdminAgentSettings(
            id=1,
            enabled=cmd.enabled,
            token_max_lifetime_days=cmd.token_max_lifetime_days,
            token_idle_revoke_days=cmd.token_idle_revoke_days,
            include_person_names=cmd.include_person_names,
            include_costs=cmd.include_costs,
            allowed_origins=list(cmd.allowed_origins),
            calls_per_minute=cmd.calls_per_minute,
            drafts_per_hour=cmd.drafts_per_hour,
            approved_providers=cmd.approved_providers,
            ai_policy_url=cmd.ai_policy_url,
        )
        settings.processing_approved_at = self._approval_stamp(
            previous, settings, approved=cmd.processing_approved
        )
        settings.assert_valid()

        saved = await self._repo.save_agents(settings)
        summary = self._summary(previous, saved)
        await self._repo.append_audit(
            AdminSettingsAuditEntry.by_actor(
                actor, settings_domain="agents", summary=f"{summary} by {actor.username}."
            )
        )
        await self._uow.commit()

        log.info(f"{summary}.")
        return AgentSettingsMapper.agents_to_result(saved)

    @staticmethod
    def _approval_stamp(
        previous: AdminAgentSettings, current: AdminAgentSettings, *, approved: bool
    ) -> datetime | None:
        if not approved:
            return None
        if previous.processing_approved_at is None or consent_terms_changed(previous, current):
            return now_utc()
        return previous.processing_approved_at

    @staticmethod
    def _summary(previous: AdminAgentSettings, saved: AdminAgentSettings) -> str:
        parts: list[str] = []
        if not previous.enabled and saved.enabled:
            parts.append("Agent access enabled")
        elif previous.enabled and not saved.enabled:
            parts.append("Agent access disabled")
        if previous.processing_approved_at is None and saved.processing_approved_at is not None:
            parts.append(f"AI processing approved for {saved.approved_providers!r}")
        elif previous.processing_approved_at is not None and saved.processing_approved_at is None:
            parts.append("AI processing approval withdrawn")
        elif previous.processing_approved_at != saved.processing_approved_at:
            parts.append(
                f"AI processing approval renewed for {saved.approved_providers!r}, "
                "users must confirm again"
            )
        return "; ".join(parts) if parts else "Agent settings updated"
