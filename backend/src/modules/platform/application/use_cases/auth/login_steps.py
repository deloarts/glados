"""
The steps PasswordLogin, TotpLogin and PasskeyLogin share: the lockout gate,
the auth settings, the maintenance gate, finishing a login with a session
and recording the login, or its refusal, in the security log. The order in
which each login runs its checks is part of its enumeration resistance and
differs between them, so this class holds the steps and leaves the
sequencing to the use cases.
"""

from src.modules.platform.application.dto.login_dto import SessionIssued
from src.modules.platform.application.dto.login_dto import TrustedDeviceGrant
from src.modules.platform.application.services.login_session import issue_session_token
from src.modules.platform.application.services.login_session import read_session_limits
from src.modules.platform.application.services.login_session import session_cookie_max_age
from src.modules.platform.application.services.login_throttle import LOCKED_MESSAGE
from src.modules.platform.application.services.security_audit import SecurityAudit
from src.modules.platform.application.use_cases.user.authenticate_user import AuthenticateUser
from src.modules.platform.domain.entities.admin_settings.auth import AdminAuthSettings
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import LoginLockedError
from src.modules.platform.domain.services.maintenance_policy import assert_maintenance_allows
from src.modules.platform.domain.value_objects.security_event_type import LoginMethod
from src.modules.platform.domain.value_objects.security_event_type import LoginRefusal
from src.modules.platform.domain.value_objects.security_event_type import SecurityEventOutcome
from src.modules.platform.domain.value_objects.security_event_type import SecurityEventType
from src.modules.platform.ports.outbound.login_attempt_tracker_port import ILoginAttemptTracker
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.repositories.user_session_repository import (
    IUserSessionRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


async def auth_settings_or_directory_off(
    settings: IPlatformSettingsRepository,
) -> AdminAuthSettings:
    """Auth settings, defaulting to LDAP-off if the row was never seeded.

    Login is public and unauthenticated: a missing settings row must degrade
    to "no directory" rather than 500 the way in for everyone. Password
    confirmations on the caller's own account follow the same rule.
    """
    try:
        return await settings.get_auth()
    except RuntimeError:
        return AdminAuthSettings(
            id=1,
            ldap_enabled=False,
            ldap_host="",
            ldap_port=636,
            ldap_use_ssl=True,
            ldap_start_tls=False,
            ldap_verify_certificate=True,
            ldap_domain="",
            ldap_timeout_seconds=5,
        )


class LoginSteps:
    def __init__(
        self,
        *,
        user_repo: IUserRepository,
        settings_repo: IPlatformSettingsRepository,
        attempts: ILoginAttemptTracker,
        session_repo: IUserSessionRepository,
        uow: IUnitOfWork,
        audit: SecurityAudit | None = None,
    ) -> None:
        self._user_repo = user_repo
        self._settings = settings_repo
        self._attempts = attempts
        self._session_repo = session_repo
        self._uow = uow
        self._audit = audit or SecurityAudit.disabled()

    async def assert_not_locked(self, attempt_key: str) -> None:
        """Raises LoginLockedError while `attempt_key` is locked. The TOTP
        step runs this before the code is judged, so a locked login costs
        nothing to reject and reveals nothing about the account."""
        locked_for = await self._attempts.lock_ttl(attempt_key)
        if locked_for > 0:
            raise LoginLockedError(LOCKED_MESSAGE, retry_after_seconds=locked_for)

    async def auth_settings(self) -> AdminAuthSettings:
        """Auth settings, defaulting to LDAP-off if the row was never seeded."""
        return await auth_settings_or_directory_off(self._settings)

    async def check_maintenance(self, user: User, client_ip: str | None) -> None:
        """Raises MaintenanceModeError unless `user` may sign in while
        maintenance mode is on. Both logins run this only after the
        credential was proven, so the setting cannot be probed without it."""
        maintenance = await self._settings.get_maintenance()
        assert_maintenance_allows(user, maintenance, client_ip)

    async def stamp_login(self, user: User) -> None:
        """Records last_logged_in, uncommitted; issue_session commits it."""
        await AuthenticateUser.complete_login(self._user_repo, user)

    async def issue_session(
        self,
        user: User,
        *,
        method: LoginMethod,
        user_agent: str | None,
        client_ip: str | None,
        trusted_device: TrustedDeviceGrant | None = None,
        trusted_device_used: bool = False,
    ) -> SessionIssued:
        """Creates and commits the session row, which also persists the
        login's earlier writes and its security log entry, and returns the
        outcome for the response."""
        detail: dict[str, object] = {"method": method.value}
        if trusted_device_used:
            detail["trusted_device"] = True
        await self._audit.record(
            SecurityEventType.LOGIN,
            actor=user,
            target_user=user,
            detail=detail,
            client_ip=client_ip,
            user_agent=user_agent,
        )
        token = await issue_session_token(
            self._session_repo, self._uow, user, user_agent=user_agent, client_ip=client_ip
        )
        limits = await read_session_limits(self._settings)
        return SessionIssued(
            access_token=token,
            cookie_max_age=session_cookie_max_age(user, limits.max_lifetime_days),
            trusted_device=trusted_device,
        )

    async def record_refusal(
        self,
        user: User | None,
        *,
        method: LoginMethod,
        reason: LoginRefusal,
        client_ip: str | None,
        user_agent: str | None,
        throttled_scopes: list[str] | None = None,
    ) -> None:
        """Records a refused login, and every throttle scope the refusal
        locked, and commits them, since the refusal raises and the request
        writes nothing else. `user` is the account the attempt named, None
        when it named none."""
        await self._audit.record(
            SecurityEventType.LOGIN,
            actor=user,
            outcome=SecurityEventOutcome.FAILURE,
            target_user=user,
            detail={"method": method.value, "reason": reason.value},
            client_ip=client_ip,
            user_agent=user_agent,
        )
        await self._audit.record_throttled(
            user, throttled_scopes or [], client_ip=client_ip, user_agent=user_agent
        )
        await self._uow.commit()
