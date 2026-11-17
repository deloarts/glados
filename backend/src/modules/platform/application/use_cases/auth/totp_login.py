"""
Step two of a 2FA login: the partial token from PasswordLogin plus a TOTP
code yield a session, and optionally a trusted-device grant.

The lockout gate runs as soon as the token names a user, before any of the
account's state is looked at. Local login and maintenance are re-checked
only after the code verified, the completed second factor being the proof
of identity here. Refusals the route answers without an error code are
raised as InactiveUserError, TOTPNotEnabledError and LoginLockedError.

A wrong code, an inactive account and the refusals after the code are
recorded in the security log, the lock a wrong code triggers too. Attempts
refused while the lock holds are not.
"""

from src.modules.platform.application.dto.login_dto import SessionIssued
from src.modules.platform.application.dto.login_dto import TotpLoginCommand
from src.modules.platform.application.dto.login_dto import TrustedDeviceGrant
from src.modules.platform.application.services.security_audit import SecurityAudit
from src.modules.platform.application.use_cases.auth.login_steps import LoginSteps
from src.modules.platform.domain.entities.trusted_device import make_trusted_device
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InactiveUserError
from src.modules.platform.domain.exceptions import InvalidTOTPCodeError
from src.modules.platform.domain.exceptions import LocalLoginDisabledError
from src.modules.platform.domain.exceptions import MaintenanceModeError
from src.modules.platform.domain.exceptions import TOTPChallengeInvalidError
from src.modules.platform.domain.exceptions import TOTPNotEnabledError
from src.modules.platform.domain.services.login_policy import TOTP_LOCK_SECONDS
from src.modules.platform.domain.services.login_policy import assert_local_login_allowed
from src.modules.platform.domain.services.login_policy import effective_trusted_device_days
from src.modules.platform.domain.services.login_policy import totp_lockout_triggered
from src.modules.platform.domain.value_objects import token_scope
from src.modules.platform.domain.value_objects.security_event_type import LoginMethod
from src.modules.platform.domain.value_objects.security_event_type import LoginRefusal
from src.modules.platform.infrastructure.security.token import get_token_payload
from src.modules.platform.infrastructure.security.totp import TOTP_REPLAY_TTL_SECONDS
from src.modules.platform.infrastructure.security.totp import verify_totp_once
from src.modules.platform.infrastructure.security.trusted_device import (
    generate_trusted_device_secret,
)
from src.modules.platform.infrastructure.security.trusted_device import hash_trusted_device
from src.modules.platform.ports.outbound.login_attempt_tracker_port import ILoginAttemptTracker
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.replay_guard_port import IReplayGuard
from src.modules.platform.ports.outbound.repositories.trusted_device_repository import (
    ITrustedDeviceRepository,
)
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.repositories.user_session_repository import (
    IUserSessionRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc

SECONDS_PER_DAY = 86400

# The throttle scope a TOTP lock is recorded under in the security log.
TOTP_SCOPE = "totp"


class TotpLogin:
    def __init__(
        self,
        *,
        user_repo: IUserRepository,
        settings_repo: IPlatformSettingsRepository,
        attempts: ILoginAttemptTracker,
        replay_guard: IReplayGuard,
        session_repo: IUserSessionRepository,
        trusted_device_repo: ITrustedDeviceRepository,
        uow: IUnitOfWork,
        audit: SecurityAudit | None = None,
    ) -> None:
        self._user_repo = user_repo
        self._settings = settings_repo
        self._attempts = attempts
        self._replay_guard = replay_guard
        self._trusted_devices = trusted_device_repo
        self._steps = LoginSteps(
            user_repo=user_repo,
            settings_repo=settings_repo,
            attempts=attempts,
            session_repo=session_repo,
            uow=uow,
            audit=audit,
        )

    async def execute(self, cmd: TotpLoginCommand) -> SessionIssued:
        payload = get_token_payload(cmd.partial_token, persistent=False)
        if not payload or not payload.sub or payload.scope != token_scope.TOTP_PENDING:
            raise TOTPChallengeInvalidError("Invalid or expired TOTP challenge token")

        # A missing user (deleted mid-flow) means this challenge can no longer
        # complete, same as an expired/malformed token, both put the client
        # back at the credentials form, not at "retry the code".
        user = await self._user_repo.get_by_id(int(str(payload.sub)))
        if not user:
            raise TOTPChallengeInvalidError("User not found")

        # Checked as soon as we have a user id, before is_active/totp_enabled,
        # same "reject for free, don't leak state while locked" posture as
        # PasswordLogin's lockout check.
        attempt_key = f"totp:{user.id}"
        await self._steps.assert_not_locked(attempt_key)

        if not user.is_active:
            await self._refuse(cmd, user, LoginRefusal.INACTIVE)
            raise InactiveUserError("Account is inactive")
        if not user.totp_enabled or not user.totp_secret:
            raise TOTPNotEnabledError("2FA is not enabled for this account")

        user_id = user.id

        async def _consume(counter: str) -> bool:
            # Scoped to this flow ("login") as well as the user: confirming
            # and disabling 2FA claim counters under their own flow names
            # (see _replay_protected_verify in deps/auth.py), so a code used
            # to, say, confirm enrolment a moment ago does not spuriously
            # block an unrelated login attempt in the same 30-second step.
            return await self._replay_guard.consume_once(
                f"glados:totp:used:login:{user_id}:{counter}", ttl_seconds=TOTP_REPLAY_TTL_SECONDS
            )

        if not await verify_totp_once(user.totp_secret, cmd.totp_code, consume=_consume):
            count = await self._attempts.record_failure(attempt_key)
            locked: list[str] = []
            if totp_lockout_triggered(count):
                await self._attempts.lock(attempt_key, TOTP_LOCK_SECONDS)
                locked.append(TOTP_SCOPE)
            await self._refuse(cmd, user, LoginRefusal.INVALID_TOTP, throttled_scopes=locked)
            raise InvalidTOTPCodeError("Invalid TOTP code")

        await self._attempts.reset(attempt_key)

        # Re-checked here too: the challenge token lives for five minutes, and
        # the setting may have been switched off inside that window.
        security = await self._settings.get_security()
        try:
            assert_local_login_allowed(user, security.allow_local_login)
        except LocalLoginDisabledError:
            await self._refuse(cmd, user, LoginRefusal.LOCAL_LOGIN_DISABLED)
            raise

        # After the code is verified, not before: same "cannot be probed
        # without proof of identity" reasoning as PasswordLogin, but here that
        # proof is the completed second factor, not just the partial_token
        # (which only proves the password was right).
        try:
            await self._steps.check_maintenance(user, cmd.client_ip)
        except MaintenanceModeError:
            await self._refuse(cmd, user, LoginRefusal.MAINTENANCE)
            raise

        # The partial token proves the password was right minutes ago.
        user.password_verified_at = now_utc()
        await self._steps.stamp_login(user)

        # "Trust this device": only after the code verified, and only while
        # the feature is enabled, a client sending trust_device=true against
        # a 0-day setting gets a session but no trust. Always 0 for the
        # system user, regardless of the setting: a session that already
        # hard-expires in 15 minutes must not be skippable by a 30-day cookie.
        grant: TrustedDeviceGrant | None = None
        trust_days = effective_trusted_device_days(user, security.totp_trusted_device_days)
        if cmd.trust_device and trust_days > 0:
            secret = generate_trusted_device_secret()
            await self._trusted_devices.save(
                make_trusted_device(
                    user_id=user.id,
                    token_hash=hash_trusted_device(secret),
                    trust_days=trust_days,
                    user_agent=cmd.user_agent,
                )
            )
            grant = TrustedDeviceGrant(secret=secret, max_age_seconds=trust_days * SECONDS_PER_DAY)

        return await self._steps.issue_session(
            user,
            method=LoginMethod.TOTP,
            user_agent=cmd.user_agent,
            client_ip=cmd.client_ip,
            trusted_device=grant,
        )

    async def _refuse(
        self,
        cmd: TotpLoginCommand,
        user: User,
        reason: LoginRefusal,
        *,
        throttled_scopes: list[str] | None = None,
    ) -> None:
        await self._steps.record_refusal(
            user,
            method=LoginMethod.TOTP,
            reason=reason,
            client_ip=cmd.client_ip,
            user_agent=cmd.user_agent,
            throttled_scopes=throttled_scopes,
        )
