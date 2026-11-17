"""Adapter and service factories, and the services one process shares
between requests."""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.inbound.api.deps.database import get_db
from src.modules.platform.adapters.inbound.api.deps.repositories import get_platform_settings_repo
from src.modules.platform.adapters.inbound.api.deps.repositories import get_security_event_repo
from src.modules.platform.adapters.outbound.external.ldap.factory import create_ldap_authenticator
from src.modules.platform.adapters.outbound.external.login_attempts.in_memory_login_attempt_tracker import (
    InMemoryLoginAttemptTracker,
)
from src.modules.platform.adapters.outbound.external.login_attempts.redis_login_attempt_tracker import (
    RedisLoginAttemptTracker,
)
from src.modules.platform.adapters.outbound.external.login_attempts.redis_replay_guard import (
    RedisReplayGuard,
)
from src.modules.platform.adapters.outbound.external.mail.smtp_mail_service import SmtpMailService
from src.modules.platform.adapters.outbound.external.schedules.backup_jobs import (
    ScheduledBackupJobs,
)
from src.modules.platform.adapters.outbound.external.storage.factory import create_storage_adapter
from src.modules.platform.adapters.outbound.external.system.psutil_stats_reader import (
    PsutilSystemStatsReader,
)
from src.modules.platform.adapters.outbound.external.webhook.factory import (
    create_webhook_dispatcher,
)
from src.modules.platform.adapters.outbound.external.webhook.factory import (
    create_webhook_target_guard,
)
from src.modules.platform.adapters.outbound.persistence.repositories.platform_settings_repository import (
    SqlAlchemyPlatformSettingsRepository,
)
from src.modules.platform.adapters.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.modules.platform.application.services.security_audit import SecurityAudit
from src.modules.platform.domain.exceptions import StorageMigrationError
from src.modules.platform.infrastructure.redis_client import get_async_redis_client
from src.modules.platform.ports.outbound.backup_jobs_port import IBackupJobsFactory
from src.modules.platform.ports.outbound.ldap_authenticator_port import ILdapAuthenticator
from src.modules.platform.ports.outbound.ldap_authenticator_port import ILdapAuthenticatorFactory
from src.modules.platform.ports.outbound.login_attempt_tracker_port import ILoginAttemptTracker
from src.modules.platform.ports.outbound.mail_service_port import IMailService
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.replay_guard_port import IReplayGuard
from src.modules.platform.ports.outbound.repositories.security_event_repository import (
    ISecurityEventRepository,
)
from src.modules.platform.ports.outbound.storage_port import IStorageAdapterFactory
from src.modules.platform.ports.outbound.storage_port import IStoragePort
from src.modules.platform.ports.outbound.system_stats_port import ISystemStatsReader
from src.modules.platform.ports.outbound.webhook_dispatcher_port import IWebhookDispatcher
from src.modules.platform.ports.outbound.webhook_target_guard_port import IWebhookTargetGuard


def get_webhook_dispatcher() -> IWebhookDispatcher:
    return create_webhook_dispatcher()


def get_webhook_target_guard() -> IWebhookTargetGuard:
    return create_webhook_target_guard()


# One per process, so the counters it keeps while Redis is down span requests.
_login_attempt_fallback = InMemoryLoginAttemptTracker()


def get_login_attempt_tracker() -> ILoginAttemptTracker:
    return RedisLoginAttemptTracker(get_async_redis_client(), fallback=_login_attempt_fallback)


def get_replay_guard() -> IReplayGuard:
    return RedisReplayGuard(get_async_redis_client())


# ── External service factories ────────────────────────────────────────

# Stateless and cheap to construct, but psutil.cpu_percent(interval=None)
# reports load since its previous call *in the same process*, so one shared
# instance is what makes the polled reading meaningful rather than always 0.
_system_stats_reader = PsutilSystemStatsReader()


def get_system_stats_reader() -> ISystemStatsReader:
    return _system_stats_reader


async def get_mail_service(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    db: AsyncSession = Depends(get_db, scope="function"),
) -> IMailService:
    return SmtpMailService(await repo.get_mail(), settings_repo=repo, uow=SqlAlchemyUnitOfWork(db))


async def get_optional_ldap_authenticator(
    db: AsyncSession = Depends(get_db, scope="function"),
) -> ILdapAuthenticator | None:
    """The configured directory authenticator, or None when LDAP is off.

    Returns None rather than raising when the settings row is missing. This
    sits on the unauthenticated login endpoint, so a 500 there would take
    sign-in down for a row that has simply never been seeded, and the
    integration suite builds its schema from ORM metadata without ever running
    InitDatabase, so get_auth() genuinely does raise in that environment.
    """
    try:
        settings = await SqlAlchemyPlatformSettingsRepository(db).get_auth()
    except RuntimeError:
        return None
    if not settings.ldap_enabled:
        return None
    return create_ldap_authenticator(settings)


def get_ldap_authenticator_factory() -> ILdapAuthenticatorFactory:
    """The factory itself, for the admin test-connection endpoint, which must
    bind against settings that are not the persisted ones."""
    return create_ldap_authenticator


async def get_optional_storage_adapter(
    db: AsyncSession = Depends(get_db, scope="function"),
) -> IStoragePort | None:
    settings = await SqlAlchemyPlatformSettingsRepository(db).get_storage()
    if not settings.enabled:
        return None
    try:
        return create_storage_adapter(settings)
    except StorageMigrationError:
        return None


def get_backup_jobs_factory() -> IBackupJobsFactory:
    """The backup-job factory itself, for callers that only learn the storage
    settings to build it from after the request has been answered (the run-now
    endpoint's background task). Injected rather than constructed inline so
    tests can substitute jobs that touch neither pg_dump nor real storage."""
    return ScheduledBackupJobs


def get_storage_adapter_factory() -> IStorageAdapterFactory:
    """The factory itself, for use cases that must build an adapter from
    settings other than the currently-active ones (migration, connection
    testing), see get_optional_storage_adapter() for the common case of
    just needing the current provider's adapter."""
    return create_storage_adapter


def get_security_audit(
    repo: ISecurityEventRepository = Depends(get_security_event_repo),
) -> SecurityAudit:
    """Records security events in the request's transaction."""
    return SecurityAudit(repo)
