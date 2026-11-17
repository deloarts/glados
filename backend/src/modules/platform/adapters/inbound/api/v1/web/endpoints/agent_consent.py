"""
The caller's own agent consent: their confirmation that an AI agent may
process Glados data on their behalf, which their agent tokens need. Mounted
at /users/me/agent-consent.
"""

from fastapi import Depends
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.deps.agents import get_give_agent_consent_use_case
from src.modules.platform.adapters.inbound.api.deps.agents import get_my_agent_consent_use_case
from src.modules.platform.adapters.inbound.api.deps.agents import (
    get_withdraw_agent_consent_use_case,
)
from src.modules.platform.adapters.inbound.api.schemas.agent_schema import AgentConsentStatusResult
from src.modules.platform.adapters.inbound.api.schemas.agent_schema import GiveAgentConsentRequest
from src.modules.platform.application.dto.agent_dto import GiveAgentConsentCommand
from src.modules.platform.application.use_cases.agent.agent_consent import GetMyAgentConsent
from src.modules.platform.application.use_cases.agent.agent_consent import GiveAgentConsent
from src.modules.platform.application.use_cases.agent.agent_consent import WithdrawAgentConsent
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("", response_model=AgentConsentStatusResult)
async def get_my_agent_consent(
    actor: User = Depends(get_current_active_user),
    use_case: GetMyAgentConsent = Depends(get_my_agent_consent_use_case),
) -> AgentConsentStatusResult:
    """The terms the consent dialog shows and whether the caller confirmed
    the current ones."""
    return await use_case.execute(actor=actor)


@router.put("", response_model=AgentConsentStatusResult)
async def give_agent_consent(
    body: GiveAgentConsentRequest,
    actor: User = Depends(get_current_active_user),
    use_case: GiveAgentConsent = Depends(get_give_agent_consent_use_case),
) -> AgentConsentStatusResult:
    """Confirm the current consent text. Requires use:mcp and approved,
    switched on agent access."""
    cmd = GiveAgentConsentCommand(consent_version=body.consent_version)
    return await use_case.execute(actor=actor, cmd=cmd)


@router.delete("", response_model=AgentConsentStatusResult)
async def withdraw_agent_consent(
    actor: User = Depends(get_current_active_user),
    use_case: WithdrawAgentConsent = Depends(get_withdraw_agent_consent_use_case),
) -> AgentConsentStatusResult:
    """Withdraw the consent and revoke every agent token of the caller."""
    return await use_case.execute(actor=actor)
