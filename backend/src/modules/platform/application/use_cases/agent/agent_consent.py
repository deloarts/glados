"""
A user's own confirmation that their AI agent may process Glados data on
their behalf. A personal access token reaches the MCP surface only while
its owner's confirmation is current (AuthenticateAgent), on top of the
use:mcp permission an admin grants and the company's approval in the agent
settings.

A user confirms the current consent text while agent access is approved and
switched on and they hold use:mcp. Withdrawing deletes the confirmation and
revokes every agent token the user holds, and works at any time, also while
agent access is off, so withdrawing is always possible.
"""

from src.modules.platform.application.dto.agent_dto import AgentConsentStatusResult
from src.modules.platform.application.dto.agent_dto import GiveAgentConsentCommand
from src.modules.platform.application.services.security_audit import SecurityAudit
from src.modules.platform.domain.entities.admin_settings.agents import AdminAgentSettings
from src.modules.platform.domain.entities.agent_consent import AgentConsent
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import AgentAccessDisabledError
from src.modules.platform.domain.exceptions import AgentConsentOutdatedError
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.services.agent_policy import AGENT_CONSENT_VERSION
from src.modules.platform.domain.services.agent_policy import consent_is_current
from src.modules.platform.domain.services.agent_policy import is_agent_token
from src.modules.platform.domain.services.pat_rules import PatRules
from src.modules.platform.domain.value_objects.security_event_type import SecurityEventType
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.repositories.agent_consent_repository import (
    IAgentConsentRepository,
)
from src.modules.platform.ports.outbound.repositories.pat_repository import IPatRepository
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc


def _status(
    actor: User, settings: AdminAgentSettings, consent: AgentConsent | None
) -> AgentConsentStatusResult:
    return AgentConsentStatusResult(
        access_ready=settings.is_ready,
        may_use_agents=is_agent_token(actor.permissions),
        approved_providers=settings.approved_providers,
        ai_policy_url=settings.ai_policy_url,
        include_person_names=settings.include_person_names,
        include_costs=settings.include_costs,
        consent_version=AGENT_CONSENT_VERSION,
        consented_at=consent.consented_at if consent else None,
        consent_current=consent_is_current(consent, settings),
    )


class GetMyAgentConsent:
    def __init__(
        self, settings: IPlatformSettingsRepository, consents: IAgentConsentRepository
    ) -> None:
        self._settings = settings
        self._consents = consents

    async def execute(self, actor: User) -> AgentConsentStatusResult:
        return _status(
            actor, await self._settings.get_agents(), await self._consents.get_for_user(actor.id)
        )


class GiveAgentConsent:
    def __init__(
        self,
        settings: IPlatformSettingsRepository,
        consents: IAgentConsentRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._settings = settings
        self._consents = consents
        self._uow = uow

    async def execute(self, actor: User, cmd: GiveAgentConsentCommand) -> AgentConsentStatusResult:
        # Agents act through personal access tokens, so the accounts that
        # may not hold one have nothing to consent for.
        PatRules.assert_can_create(actor)
        if not is_agent_token(actor.permissions):
            raise InsufficientPermissionsError("Using an AI agent requires use:mcp.")
        settings = await self._settings.get_agents()
        if not settings.is_ready:
            raise AgentAccessDisabledError("Agent access is not approved and switched on.")
        if cmd.consent_version != AGENT_CONSENT_VERSION:
            raise AgentConsentOutdatedError(
                "The consent text changed; read and confirm the current one."
            )

        consent = await self._consents.save(
            AgentConsent(
                id=0,
                user_id=actor.id,
                consent_version=AGENT_CONSENT_VERSION,
                consented_at=now_utc(),
            )
        )
        await self._uow.commit()

        log.info(
            "User %s confirmed the agent consent (version %d).", actor.id, AGENT_CONSENT_VERSION
        )
        return _status(actor, settings, consent)


class WithdrawAgentConsent:
    def __init__(
        self,
        settings: IPlatformSettingsRepository,
        consents: IAgentConsentRepository,
        pats: IPatRepository,
        *,
        uow: IUnitOfWork,
        audit: SecurityAudit | None = None,
    ) -> None:
        self._settings = settings
        self._consents = consents
        self._pats = pats
        self._uow = uow
        self._audit = audit or SecurityAudit.disabled()

    async def execute(self, actor: User) -> AgentConsentStatusResult:
        withdrawn = await self._consents.delete_for_user(actor.id)
        revoked = await self._revoke_agent_tokens(actor)
        await self._uow.commit()

        if withdrawn or revoked:
            log.info(
                "User %s withdrew the agent consent; revoked %d agent token(s).",
                actor.id,
                revoked,
            )
        return _status(actor, await self._settings.get_agents(), None)

    async def _revoke_agent_tokens(self, actor: User) -> int:
        now = now_utc()
        revoked = 0
        for token in await self._pats.list_unrevoked_unexpired(user_id=actor.id):
            if not is_agent_token(token.permissions):
                continue
            token.revoked_at = now
            await self._pats.save(token)
            await self._audit.record(
                SecurityEventType.PAT_REVOKED,
                actor=actor,
                target_user=actor,
                target_id=token.id,
                detail={"name": token.name, "reason": "agent_consent_withdrawn"},
            )
            revoked += 1
        return revoked
