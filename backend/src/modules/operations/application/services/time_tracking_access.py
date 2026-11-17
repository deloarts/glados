"""Shared steps of the time tracking use cases: the guards that run before
any request reaches the time tracking service, the per-user rate limits,
and the bookkeeping after the service rejected stored credentials.

Order of the guards: time tracking must be available (enabled, configured,
key confirmed), the actor must be a personal account, and stored
credentials must be usable (see domain/services/time_tracking_rules.py).
Only then is a rate limit consumed, so a request that would be refused
anyway costs nothing.

When the service rejects stored credentials, the rejection is recorded
before it is raised: a rejected sign-in marks them, so repeated page loads
cannot lock the account on the time tracking system after the user changed
their password, and a changed binding drops the sealed value, which Glados
cannot re-seal.

Rate limits use the login attempt tracker with key prefixes of their own:
failed credential checks lock further checks for a while, and month and
year fetches are spaced per user.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime

from src.modules.operations.application.services.time_tracking_service import (
    is_time_tracking_available,
)
from src.modules.operations.application.services.time_tracking_service import service_connection
from src.modules.operations.domain.entities.admin_settings.time_tracking import (
    AdminTimeTrackingSettings,
)
from src.modules.operations.domain.errors import TimeTrackingAuthenticationFailedError
from src.modules.operations.domain.errors import TimeTrackingBindingChangedError
from src.modules.operations.domain.errors import TimeTrackingNotEnabledError
from src.modules.operations.domain.errors import TimeTrackingRateLimitedError
from src.modules.operations.domain.services.time_tracking_rules import FETCH_COOLDOWN_SECONDS
from src.modules.operations.domain.services.time_tracking_rules import VERIFY_LOCK_SECONDS
from src.modules.operations.domain.services.time_tracking_rules import verify_limit_exceeded
from src.modules.operations.ports.outbound.operations_settings_repository import (
    IOperationsSettingsRepository,
)
from src.modules.operations.ports.outbound.repositories.user_time_tracking_credentials_repository import (
    IUserTimeTrackingCredentialsRepository,
)
from src.modules.operations.ports.outbound.time_tracking_provider_port import (
    TimeTrackingServiceConnection,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.user_rules import UserRules
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.login_attempt_tracker_port import ILoginAttemptTracker
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


@dataclass(frozen=True)
class TimeTrackingSetup:
    settings: AdminTimeTrackingSettings
    connection: TimeTrackingServiceConnection
    timezone: str


async def load_enabled_settings(
    actor: User, settings_repo: IOperationsSettingsRepository
) -> AdminTimeTrackingSettings:
    """The time tracking settings, when time tracking is available and
    `actor` is a personal account; raises otherwise."""
    settings = await settings_repo.get_time_tracking()
    if not is_time_tracking_available(settings):
        raise TimeTrackingNotEnabledError("Time tracking is not enabled.")
    UserRules.assert_time_tracking_credentials_allowed(actor, has_credentials=True)
    return settings


async def load_time_tracking_setup(
    actor: User, settings_repo: IOperationsSettingsRepository
) -> TimeTrackingSetup:
    """The available settings plus the connection to the service and the
    instance's time zone, which decides what "today" is."""
    settings = await load_enabled_settings(actor, settings_repo)
    return TimeTrackingSetup(
        settings=settings,
        connection=service_connection(settings),
        timezone=(await settings_repo.get_general()).default_timezone,
    )


@asynccontextmanager
async def recording_rejections(
    credentials_repo: IUserTimeTrackingCredentialsRepository,
    uow: IUnitOfWork,
    user_id: int,
    now: datetime,
) -> AsyncIterator[None]:
    """Wraps a call with the user's stored credentials. A rejected sign-in
    marks them as rejected, and a changed binding drops the sealed value;
    either is committed before the error is raised on."""
    try:
        yield
    except TimeTrackingAuthenticationFailedError:
        await credentials_repo.mark_auth_failed(user_id, now)
        await uow.commit()
        log.warning("The time tracking system rejected the stored credentials; calls are paused.")
        raise
    except TimeTrackingBindingChangedError:
        await credentials_repo.clear_sealed(user_id)
        await uow.commit()
        log.warning(
            "The time tracking service reported a changed binding; the user has to enter "
            "the password again."
        )
        raise


def _verify_key(user_id: int) -> str:
    return f"time-tracking-verify:{user_id}"


async def assert_verify_not_locked(tracker: ILoginAttemptTracker, user_id: int) -> None:
    if await tracker.lock_ttl(_verify_key(user_id)) > 0:
        raise TimeTrackingRateLimitedError(
            "Too many failed time tracking sign-ins. Try again later."
        )


async def record_verify_failure(tracker: ILoginAttemptTracker, user_id: int) -> None:
    """Counts one rejected credential check and locks further checks once
    the limit is reached."""
    failures = await tracker.record_failure(_verify_key(user_id))
    if verify_limit_exceeded(failures):
        await tracker.lock(_verify_key(user_id), VERIFY_LOCK_SECONDS)
        log.warning(
            "Time tracking credential checks locked for %s minutes after %s failures.",
            VERIFY_LOCK_SECONDS // 60,
            failures,
        )


async def claim_fetch(tracker: ILoginAttemptTracker, kind: str, user_id: int) -> None:
    """At most one `kind` ("month" or "year") fetch per user per cooldown."""
    if not await tracker.claim(f"time-tracking-{kind}:{user_id}", FETCH_COOLDOWN_SECONDS):
        raise TimeTrackingRateLimitedError(
            f"Time tracking data was just loaded. Wait {FETCH_COOLDOWN_SECONDS} seconds "
            "before loading it again."
        )
