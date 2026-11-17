"""
Step one of the web login: username or e-mail plus password. The outcome is
a session, a TOTP challenge, or a forced 2FA enrolment.

The order of the checks is the security contract. The throttle runs
before the password (application/services/login_throttle.py), every wrong
password counts whether or not the name exists, and every setting-dependent refusal (local login off, maintenance)
comes only after the password was proven, so none of them can be probed
without valid credentials.

A wrong password raises UserNotFoundError, which the route answers with a
uniform 401, as it does for CredentialsUnverifiableError (directory
outage, not counted). A lock raises LoginLockedError.

Every refusal after the throttle is recorded in the security log with its
reason, and so is every throttle scope a failure locks. An attempt the
throttle refuses is not recorded, so a flood of them cannot grow the log.
A login waiting for its TOTP code is recorded by the TOTP step.
"""

from collections.abc import Awaitable
from collections.abc import Callable

from src.modules.platform.application.dto.login_dto import PasswordLoginCommand
from src.modules.platform.application.dto.login_dto import PasswordLoginResult
from src.modules.platform.application.dto.login_dto import TotpChallengeIssued
from src.modules.platform.application.dto.login_dto import TotpSetupRequired
from src.modules.platform.application.services.login_throttle import LoginThrottle
from src.modules.platform.application.services.security_audit import SecurityAudit
from src.modules.platform.application.use_cases.auth.login_steps import LoginSteps
from src.modules.platform.application.use_cases.user.authenticate_user import AuthenticateUser
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import CredentialsUnverifiableError
from src.modules.platform.domain.exceptions import InactiveUserError
from src.modules.platform.domain.exceptions import LocalLoginDisabledError
from src.modules.platform.domain.exceptions import MaintenanceModeError
from src.modules.platform.domain.exceptions import UserNotFoundError
from src.modules.platform.domain.services.login_policy import assert_local_login_allowed
from src.modules.platform.domain.services.login_policy import effective_trusted_device_days
from src.modules.platform.domain.services.login_policy import resolves_to_ldap
from src.modules.platform.domain.services.login_policy import totp_enrolment_required
from src.modules.platform.domain.value_objects.security_event_type import LoginMethod
from src.modules.platform.domain.value_objects.security_event_type import LoginRefusal
from src.modules.platform.infrastructure.security.token import create_partial_token
from src.modules.platform.infrastructure.security.token import create_setup_token
from src.modules.platform.infrastructure.security.trusted_device import hash_trusted_device
from src.modules.platform.ports.outbound.ldap_authenticator_port import ILdapAuthenticator
from src.modules.platform.ports.outbound.login_attempt_tracker_port import ILoginAttemptTracker
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.repositories.trusted_device_repository import (
    ITrustedDeviceRepository,
)
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.repositories.user_session_repository import (
    IUserSessionRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc


class PasswordLogin:
    def __init__(
        self,
        *,
        user_repo: IUserRepository,
        settings_repo: IPlatformSettingsRepository,
        attempts: ILoginAttemptTracker,
        ldap: ILdapAuthenticator | None,
        session_repo: IUserSessionRepository,
        trusted_device_repo: ITrustedDeviceRepository,
        uow: IUnitOfWork,
        verify_fn: Callable[[str, str], Awaitable[bool]],
        audit: SecurityAudit | None = None,
    ) -> None:
        self._user_repo = user_repo
        self._settings = settings_repo
        self._attempts = attempts
        self._ldap = ldap
        self._trusted_devices = trusted_device_repo
        self._uow = uow
        self._verify = verify_fn
        self._steps = LoginSteps(
            user_repo=user_repo,
            settings_repo=settings_repo,
            attempts=attempts,
            session_repo=session_repo,
            uow=uow,
            audit=audit,
        )

    async def execute(self, cmd: PasswordLoginCommand) -> PasswordLoginResult:
        security = await self._settings.get_security()
        auth = await self._steps.auth_settings()

        # Checked before the password so a locked login cannot be probed by
        # timing, so brute-forcing costs nothing to reject, and, with LDAP on,
        # so a guess never reaches the directory at all. The throttle keys on
        # the normalised name, see normalise_username for why.
        throttle = LoginThrottle(self._attempts)
        await throttle.assert_allowed(cmd.username, cmd.client_ip)

        authenticate = AuthenticateUser(
            self._user_repo,
            verify_fn=self._verify,
            ldap=self._ldap,
            ldap_enabled=auth.ldap_enabled,
            uow=self._uow,
        )
        try:
            user = await authenticate.by_password(cmd.username, cmd.password)
        except CredentialsUnverifiableError:
            # A directory outage, not a guess: answered like a wrong
            # password, but the counter stays untouched. Must precede its
            # parent class UserNotFoundError.
            await self._refuse(
                cmd, authenticate.candidate, auth.ldap_enabled, LoginRefusal.DIRECTORY_UNAVAILABLE
            )
            raise
        except UserNotFoundError:
            # Counted even for names that do not exist: skipping them would
            # make an unknown username measurably cheaper than a wrong
            # password, which is a user-enumeration oracle.
            locked = await throttle.record_failure(cmd.username, cmd.client_ip, security)
            await self._refuse(
                cmd,
                authenticate.candidate,
                auth.ldap_enabled,
                LoginRefusal.INVALID_CREDENTIALS,
                throttled_scopes=locked,
            )
            raise
        except InactiveUserError:
            await self._refuse(
                cmd, authenticate.candidate, auth.ldap_enabled, LoginRefusal.INACTIVE
            )
            raise
        method = self._method(user, auth.ldap_enabled)

        # After the password check, so this cannot be used to probe the
        # setting without valid credentials; before the TOTP branch, so a
        # blocked user is not handed a challenge token they can never redeem.
        try:
            assert_local_login_allowed(user, security.allow_local_login)
        except LocalLoginDisabledError:
            await self._refuse(cmd, user, auth.ldap_enabled, LoginRefusal.LOCAL_LOGIN_DISABLED)
            raise

        # Credentials were right, forget any earlier failures for this name.
        await throttle.record_success(cmd.username, cmd.client_ip)
        # Persisted with the session below; a pending TOTP step stamps it again.
        user.password_verified_at = now_utc()

        # After the password check (same reasoning as assert_local_login_allowed
        # above) and after the reset, so a blocked user's valid attempt still
        # clears their lockout counter; before the TOTP branch, so a blocked
        # user is never handed a challenge token they can't redeem.
        try:
            await self._steps.check_maintenance(user, cmd.client_ip)
        except MaintenanceModeError:
            await self._refuse(cmd, user, auth.ldap_enabled, LoginRefusal.MAINTENANCE)
            raise

        if user.totp_enabled:
            # "Trust this device": a live trusted-device cookie skips the
            # second factor only, the password above was still required.
            # Gated on the setting first so an admin turning the feature off
            # also disarms every previously issued cookie at once. Always 0
            # for the system user, regardless of the setting.
            trust_days = effective_trusted_device_days(user, security.totp_trusted_device_days)
            if (
                trust_days > 0
                and cmd.trusted_device_secret
                and await self._redeem_trusted_device(user, cmd.trusted_device_secret)
            ):
                await self._steps.stamp_login(user)
                return await self._steps.issue_session(
                    user,
                    method=method,
                    user_agent=cmd.user_agent,
                    client_ip=cmd.client_ip,
                    trusted_device_used=True,
                )
            return TotpChallengeIssued(
                partial_token=create_partial_token(user.id),
                trusted_device_days=trust_days,
            )

        # 2FA is required for this user but never set up. Rather than refusing
        # the login outright, which would lock out every user the moment an
        # admin flips the switch, hand back a token good only for the
        # enrolment endpoints and walk them through it.
        if totp_enrolment_required(user, enforce_totp=security.enforce_totp):
            return TotpSetupRequired(
                setup_token=create_setup_token(user.id, user.token_version),
                username=user.username,
            )

        await self._steps.stamp_login(user)
        return await self._steps.issue_session(
            user, method=method, user_agent=cmd.user_agent, client_ip=cmd.client_ip
        )

    def _method(self, user: User, ldap_enabled: bool) -> LoginMethod:
        """Which authority checked the password, as AuthenticateUser chose."""
        if self._ldap is not None and resolves_to_ldap(user, ldap_enabled):
            return LoginMethod.LDAP
        return LoginMethod.PASSWORD

    async def _refuse(
        self,
        cmd: PasswordLoginCommand,
        user: User | None,
        ldap_enabled: bool,
        reason: LoginRefusal,
        *,
        throttled_scopes: list[str] | None = None,
    ) -> None:
        method = self._method(user, ldap_enabled) if user is not None else LoginMethod.PASSWORD
        await self._steps.record_refusal(
            user,
            method=method,
            reason=reason,
            client_ip=cmd.client_ip,
            user_agent=cmd.user_agent,
            throttled_scopes=throttled_scopes,
        )

    async def _redeem_trusted_device(self, user: User, secret: str) -> bool:
        """Whether `secret` names a live grant of this user's. A redeemed
        grant has its last_used_at stamped, uncommitted."""
        device = await self._trusted_devices.get_by_token_hash(hash_trusted_device(secret))
        if device is None or device.user_id != user.id or not device.is_usable:
            return False
        device.last_used_at = now_utc()
        await self._trusted_devices.save(device)
        return True
