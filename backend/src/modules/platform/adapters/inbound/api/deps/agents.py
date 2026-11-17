"""
Use case factories of the MCP surface: authenticating an agent's request,
the users' agent consent, the agent call log and the scheduled sweep of
agent tokens.
"""

from fastapi import Depends

from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.adapters.inbound.api.deps.repositories import get_agent_call_repo
from src.modules.platform.adapters.inbound.api.deps.repositories import get_agent_consent_repo
from src.modules.platform.adapters.inbound.api.deps.repositories import get_api_key_repo
from src.modules.platform.adapters.inbound.api.deps.repositories import get_inapp_notification_repo
from src.modules.platform.adapters.inbound.api.deps.repositories import get_pat_repo
from src.modules.platform.adapters.inbound.api.deps.repositories import get_platform_settings_repo
from src.modules.platform.adapters.inbound.api.deps.repositories import get_user_repo
from src.modules.platform.adapters.inbound.api.deps.services import get_security_audit
from src.modules.platform.application.services.security_audit import SecurityAudit
from src.modules.platform.application.use_cases.agent.agent_consent import GetMyAgentConsent
from src.modules.platform.application.use_cases.agent.agent_consent import GiveAgentConsent
from src.modules.platform.application.use_cases.agent.agent_consent import WithdrawAgentConsent
from src.modules.platform.application.use_cases.agent.authenticate_agent import AuthenticateAgent
from src.modules.platform.application.use_cases.agent.find_agent_created_records import (
    FindAgentCreatedRecords,
)
from src.modules.platform.application.use_cases.agent.list_agent_calls import ListAgentCalls
from src.modules.platform.application.use_cases.agent.sweep_agent_tokens import SweepAgentTokens
from src.modules.platform.infrastructure.security.api_key import hash_api_key
from src.modules.platform.infrastructure.security.pat import hash_pat
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.repositories.agent_call_repository import (
    IAgentCallRepository,
)
from src.modules.platform.ports.outbound.repositories.agent_consent_repository import (
    IAgentConsentRepository,
)
from src.modules.platform.ports.outbound.repositories.api_key_repository import IApiKeyRepository
from src.modules.platform.ports.outbound.repositories.notification_repository import (
    INotificationRepository,
)
from src.modules.platform.ports.outbound.repositories.pat_repository import IPatRepository
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


def get_authenticate_agent_use_case(
    settings: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    pats: IPatRepository = Depends(get_pat_repo),
    api_keys: IApiKeyRepository = Depends(get_api_key_repo),
    users: IUserRepository = Depends(get_user_repo),
    consents: IAgentConsentRepository = Depends(get_agent_consent_repo),
) -> AuthenticateAgent:
    return AuthenticateAgent(
        settings, pats, api_keys, users, consents, hash_pat=hash_pat, hash_api_key=hash_api_key
    )


def get_my_agent_consent_use_case(
    settings: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    consents: IAgentConsentRepository = Depends(get_agent_consent_repo),
) -> GetMyAgentConsent:
    return GetMyAgentConsent(settings, consents)


def get_give_agent_consent_use_case(
    settings: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    consents: IAgentConsentRepository = Depends(get_agent_consent_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> GiveAgentConsent:
    return GiveAgentConsent(settings, consents, uow=uow)


def get_withdraw_agent_consent_use_case(
    settings: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    consents: IAgentConsentRepository = Depends(get_agent_consent_repo),
    pats: IPatRepository = Depends(get_pat_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    audit: SecurityAudit = Depends(get_security_audit),
) -> WithdrawAgentConsent:
    return WithdrawAgentConsent(settings, consents, pats, uow=uow, audit=audit)


def get_list_agent_calls_use_case(
    calls: IAgentCallRepository = Depends(get_agent_call_repo),
) -> ListAgentCalls:
    return ListAgentCalls(calls)


def get_find_agent_created_records_use_case(
    calls: IAgentCallRepository = Depends(get_agent_call_repo),
) -> FindAgentCreatedRecords:
    return FindAgentCreatedRecords(calls)


def get_sweep_agent_tokens_use_case(
    settings: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    pats: IPatRepository = Depends(get_pat_repo),
    api_keys: IApiKeyRepository = Depends(get_api_key_repo),
    users: IUserRepository = Depends(get_user_repo),
    calls: IAgentCallRepository = Depends(get_agent_call_repo),
    notifications: INotificationRepository = Depends(get_inapp_notification_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    audit: SecurityAudit = Depends(get_security_audit),
) -> SweepAgentTokens:
    return SweepAgentTokens(
        settings, pats, api_keys, users, calls, notifications, uow=uow, audit=audit
    )
