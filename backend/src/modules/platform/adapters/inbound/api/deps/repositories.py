"""Repository factories on the request's session, and the module's settings
store."""

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.inbound.api.deps.database import repo_factory
from src.modules.platform.adapters.outbound.persistence.repositories.acknowledgement_repository import (
    SqlAlchemyAcknowledgementRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.agent_call_repository import (
    SqlAlchemyAgentCallRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.agent_consent_repository import (
    SqlAlchemyAgentConsentRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.api_key_repository import (
    SqlAlchemyApiKeyRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.api_key_usage_log_repository import (
    SqlAlchemyApiKeyUsageLogRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.backup_run_repository import (
    SqlAlchemyBackupRunRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.email_notification_repository import (
    SqlAlchemyEmailNotificationRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.idempotency_key_repository import (
    SqlAlchemyIdempotencyKeyRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.log_repository import (
    SqlAlchemyLogRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.notification_repository import (
    SqlAlchemyNotificationRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.passkey_repository import (
    SqlAlchemyPasskeyRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.pat_repository import (
    SqlAlchemyPatRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.pat_usage_log_repository import (
    SqlAlchemyPatUsageLogRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.platform_settings_repository import (
    SqlAlchemyPlatformSettingsRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.security_event_repository import (
    SqlAlchemySecurityEventRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.trusted_device_repository import (
    SqlAlchemyTrustedDeviceRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.user_group_repository import (
    SqlAlchemyUserGroupRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.user_pdm_link_repository import (
    SqlAlchemyUserPdmLinkRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.user_repository import (
    SqlAlchemyUserRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.user_session_repository import (
    SqlAlchemyUserSessionRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.webhook_repository import (
    SqlAlchemyWebhookDeliveryRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.webhook_repository import (
    SqlAlchemyWebhookSubscriptionRepository,
)
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.repositories.acknowledgement_repository import (
    IAcknowledgementRepository,
)
from src.modules.platform.ports.outbound.repositories.agent_call_repository import (
    IAgentCallRepository,
)
from src.modules.platform.ports.outbound.repositories.agent_consent_repository import (
    IAgentConsentRepository,
)
from src.modules.platform.ports.outbound.repositories.api_key_repository import IApiKeyRepository
from src.modules.platform.ports.outbound.repositories.api_key_usage_log_repository import (
    IApiKeyUsageLogRepository,
)
from src.modules.platform.ports.outbound.repositories.backup_run_repository import (
    IBackupRunRepository,
)
from src.modules.platform.ports.outbound.repositories.email_notification_repository import (
    IEmailNotificationRepository,
)
from src.modules.platform.ports.outbound.repositories.idempotency_key_repository import (
    IIdempotencyKeyRepository,
)
from src.modules.platform.ports.outbound.repositories.log_repository import ILogRepository
from src.modules.platform.ports.outbound.repositories.notification_repository import (
    INotificationRepository,
)
from src.modules.platform.ports.outbound.repositories.passkey_repository import IPasskeyRepository
from src.modules.platform.ports.outbound.repositories.pat_repository import IPatRepository
from src.modules.platform.ports.outbound.repositories.pat_usage_log_repository import (
    IPatUsageLogRepository,
)
from src.modules.platform.ports.outbound.repositories.security_event_repository import (
    ISecurityEventRepository,
)
from src.modules.platform.ports.outbound.repositories.trusted_device_repository import (
    ITrustedDeviceRepository,
)
from src.modules.platform.ports.outbound.repositories.user_group_repository import (
    IUserGroupRepository,
)
from src.modules.platform.ports.outbound.repositories.user_pdm_link_repository import (
    IUserPdmLinkRepository,
)
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.repositories.user_session_repository import (
    IUserSessionRepository,
)
from src.modules.platform.ports.outbound.repositories.webhook_delivery_repository import (
    IWebhookDeliveryRepository,
)
from src.modules.platform.ports.outbound.repositories.webhook_subscription_repository import (
    IWebhookSubscriptionRepository,
)

# ── Repository factories ──────────────────────────────────────────────

get_user_repo: Callable[[AsyncSession], IUserRepository] = repo_factory(SqlAlchemyUserRepository)
get_user_group_repo: Callable[[AsyncSession], IUserGroupRepository] = repo_factory(
    SqlAlchemyUserGroupRepository
)
get_user_pdm_link_repo: Callable[[AsyncSession], IUserPdmLinkRepository] = repo_factory(
    SqlAlchemyUserPdmLinkRepository
)
get_api_key_repo: Callable[[AsyncSession], IApiKeyRepository] = repo_factory(
    SqlAlchemyApiKeyRepository
)
get_api_key_usage_log_repo: Callable[[AsyncSession], IApiKeyUsageLogRepository] = repo_factory(
    SqlAlchemyApiKeyUsageLogRepository
)
get_pat_repo: Callable[[AsyncSession], IPatRepository] = repo_factory(SqlAlchemyPatRepository)
get_agent_call_repo: Callable[[AsyncSession], IAgentCallRepository] = repo_factory(
    SqlAlchemyAgentCallRepository
)
get_agent_consent_repo: Callable[[AsyncSession], IAgentConsentRepository] = repo_factory(
    SqlAlchemyAgentConsentRepository
)
get_user_session_repo: Callable[[AsyncSession], IUserSessionRepository] = repo_factory(
    SqlAlchemyUserSessionRepository
)
get_trusted_device_repo: Callable[[AsyncSession], ITrustedDeviceRepository] = repo_factory(
    SqlAlchemyTrustedDeviceRepository
)
get_passkey_repo: Callable[[AsyncSession], IPasskeyRepository] = repo_factory(
    SqlAlchemyPasskeyRepository
)
get_pat_usage_log_repo: Callable[[AsyncSession], IPatUsageLogRepository] = repo_factory(
    SqlAlchemyPatUsageLogRepository
)
get_security_event_repo: Callable[[AsyncSession], ISecurityEventRepository] = repo_factory(
    SqlAlchemySecurityEventRepository
)
get_notification_repo: Callable[[AsyncSession], IEmailNotificationRepository] = repo_factory(
    SqlAlchemyEmailNotificationRepository
)
get_inapp_notification_repo: Callable[[AsyncSession], INotificationRepository] = repo_factory(
    SqlAlchemyNotificationRepository
)
get_webhook_subscription_repo: Callable[[AsyncSession], IWebhookSubscriptionRepository] = (
    repo_factory(SqlAlchemyWebhookSubscriptionRepository)
)
get_webhook_delivery_repo: Callable[[AsyncSession], IWebhookDeliveryRepository] = repo_factory(
    SqlAlchemyWebhookDeliveryRepository
)


get_backup_run_repo: Callable[[AsyncSession], IBackupRunRepository] = repo_factory(
    SqlAlchemyBackupRunRepository
)
get_idempotency_key_repo: Callable[[AsyncSession], IIdempotencyKeyRepository] = repo_factory(
    SqlAlchemyIdempotencyKeyRepository
)
get_acknowledgement_repo: Callable[[AsyncSession], IAcknowledgementRepository] = repo_factory(
    SqlAlchemyAcknowledgementRepository
)
get_log_repo: Callable[[AsyncSession], ILogRepository] = repo_factory(SqlAlchemyLogRepository)

get_platform_settings_repo: Callable[[AsyncSession], IPlatformSettingsRepository] = repo_factory(
    SqlAlchemyPlatformSettingsRepository
)
