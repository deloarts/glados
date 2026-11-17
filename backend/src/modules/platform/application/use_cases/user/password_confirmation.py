"""
Proving the acting user's own password again before a sensitive change on
their account, such as registering a passkey or setting a new password. The
caller already has a session, but whoever finds an unlocked one must not be
able to make such a change. A wrong password counts toward the same throttle
as the login form, so these routes cannot be used to guess around it.

Directory accounts are checked against the directory, like at sign-in.

A wrong password is recorded in the security log, with every throttle scope
it locked, and committed before the refusal is raised.
"""

from collections.abc import Awaitable
from collections.abc import Callable

from src.modules.platform.application.services.login_throttle import LoginThrottle
from src.modules.platform.application.services.security_audit import SecurityAudit
from src.modules.platform.application.use_cases.auth.login_steps import (
    auth_settings_or_directory_off,
)
from src.modules.platform.application.use_cases.user.authenticate_user import AuthenticateUser
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import CredentialsUnverifiableError
from src.modules.platform.domain.exceptions import LdapUnavailableError
from src.modules.platform.domain.exceptions import PasswordConfirmationFailedError
from src.modules.platform.domain.exceptions import UserNotFoundError
from src.modules.platform.domain.value_objects.security_event_type import LoginRefusal
from src.modules.platform.domain.value_objects.security_event_type import SecurityEventOutcome
from src.modules.platform.domain.value_objects.security_event_type import SecurityEventType
from src.modules.platform.ports.outbound.ldap_authenticator_port import ILdapAuthenticator
from src.modules.platform.ports.outbound.login_attempt_tracker_port import ILoginAttemptTracker
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class PasswordConfirmation:
    def __init__(
        self,
        *,
        user_repo: IUserRepository,
        settings_repo: IPlatformSettingsRepository,
        attempts: ILoginAttemptTracker,
        ldap: ILdapAuthenticator | None,
        uow: IUnitOfWork,
        verify_fn: Callable[[str, str], Awaitable[bool]],
        audit: SecurityAudit | None = None,
    ) -> None:
        self._user_repo = user_repo
        self._settings = settings_repo
        self._attempts = attempts
        self._ldap = ldap
        self._uow = uow
        self._verify = verify_fn
        self._audit = audit or SecurityAudit.disabled()

    async def confirm(self, actor: User, password: str, *, client_ip: str | None) -> User:
        """The actor re-read with its password proven. A throttled caller
        gets LoginLockedError, a wrong password raises
        PasswordConfirmationFailedError and counts as a failed login
        attempt, and an unreachable directory raises LdapUnavailableError."""
        security = await self._settings.get_security()
        auth = await auth_settings_or_directory_off(self._settings)
        throttle = LoginThrottle(self._attempts)
        await throttle.assert_allowed(actor.username, client_ip)

        authenticate = AuthenticateUser(
            self._user_repo,
            verify_fn=self._verify,
            ldap=self._ldap,
            ldap_enabled=auth.ldap_enabled,
            uow=self._uow,
        )
        try:
            user = await authenticate.by_password(actor.username, password)
        except CredentialsUnverifiableError as exc:
            # Must precede its parent class UserNotFoundError.
            raise LdapUnavailableError("The directory could not be reached.") from exc
        except UserNotFoundError as exc:
            locked = await throttle.record_failure(actor.username, client_ip, security)
            await self._audit.record(
                SecurityEventType.PASSWORD_CONFIRMATION,
                actor=actor,
                outcome=SecurityEventOutcome.FAILURE,
                target_user=actor,
                detail={"reason": LoginRefusal.INVALID_CREDENTIALS.value},
                client_ip=client_ip,
            )
            await self._audit.record_throttled(actor, locked, client_ip=client_ip)
            await self._uow.commit()
            raise PasswordConfirmationFailedError("The password is not correct.") from exc
        await throttle.record_success(actor.username, client_ip)
        return user
