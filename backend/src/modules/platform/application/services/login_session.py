"""
The one way a full web session comes into existence: persist the
server-side row, then mint the JWT naming it. Shared by every flow that
completes a login (password, TOTP, forced enrolment) so no path can forget
the row, a session token whose `sid` points nowhere is rejected on its
first request.

Issuing the session is the last write of every login flow, so its commit
also persists the flow's earlier writes: last_logged_in and a new or
re-used trusted device.
"""

from dataclasses import dataclass
from datetime import timedelta

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.entities.user_session import make_user_session
from src.modules.platform.domain.services.session_rules import DEFAULT_SESSION_MAX_LIFETIME_DAYS
from src.modules.platform.domain.services.session_rules import SYSTEM_USER_SESSION_LIFETIME_MINUTES
from src.modules.platform.domain.services.session_rules import session_hard_expiry
from src.modules.platform.infrastructure.security.token import create_access_token
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.repositories.user_session_repository import (
    IUserSessionRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc


@dataclass(frozen=True)
class SessionLimits:
    """The security settings that end a session: the idle timeout in
    minutes and the absolute lifetime in days."""

    idle_timeout_minutes: int
    max_lifetime_days: int


async def read_session_limits(settings: IPlatformSettingsRepository) -> SessionLimits:
    """The configured session limits. A missing settings row must not lock
    everyone out, so it degrades to no idle expiry and the shipped absolute
    lifetime, which still bounds every session."""
    try:
        security = await settings.get_security()
    except RuntimeError:
        return SessionLimits(
            idle_timeout_minutes=0, max_lifetime_days=DEFAULT_SESSION_MAX_LIFETIME_DAYS
        )
    return SessionLimits(
        idle_timeout_minutes=security.session_timeout_minutes,
        max_lifetime_days=security.session_max_lifetime_days,
    )


async def issue_session_token(
    session_repo: IUserSessionRepository,
    uow: IUnitOfWork,
    user: User,
    *,
    user_agent: str | None,
    client_ip: str | None,
) -> str:
    """Create the session row and return its bearer token.

    No exp claim for an ordinary user: the row is the authority on
    liveness (revocation, idle timeout and absolute lifetime, see
    domain/services/session_rules.py). The system user gets one anyway, a
    defence-in-depth mirror of its row-level hard expiry, so the
    token dies even if a row check were ever bypassed. user_agent/ip are
    display metadata for the sessions list, never used for auth.
    """
    session = await session_repo.save(
        make_user_session(user_id=user.id, user_agent=user_agent, ip=client_ip)
    )
    # Committed before the token exists, so no token can name a row that
    # was never persisted.
    await uow.commit()
    expires_delta = (
        timedelta(minutes=SYSTEM_USER_SESSION_LIFETIME_MINUTES) if user.is_systemuser else None
    )
    return create_access_token(
        subject=user.id,
        persistent=False,
        expires_delta=expires_delta,
        token_version=user.token_version,
        sid=str(session.public_id),
    )


def session_cookie_max_age(user: User, max_lifetime_days: int) -> int:
    """The cookie's browser-side lifetime: as long as the session can live
    at most, so the cookie never outlasts its session row. That is the
    system user's short hard lifetime, a defence-in-depth mirror of its
    JWT's own exp claim, or the configured absolute lifetime for everyone
    else."""
    now = now_utc()
    expiry = session_hard_expiry(
        now, is_systemuser=user.is_systemuser, max_lifetime_days=max_lifetime_days
    )
    return int((expiry - now).total_seconds())
