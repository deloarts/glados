"""
The passkey login: options for the browser's prompt, then the signed
answer yields a session. A verified passkey stands in for the password and
the TOTP code together, because the authenticator proved both the device
and the user (PIN or biometric), so no second step follows and enforced
2FA counts as satisfied.

Every refusal before the signature is verified (expired or replayed
challenge, unknown credential, deleted user) raises the same
PasskeyRejectedError, so the public route reveals nothing about which
credentials exist. Account state is looked at only once the signature
verified: inactive accounts, the directory recheck and maintenance.

There is no lockout gate: a signature cannot be guessed, and a passkey
that still works while someone hammers the password form is the point.

The security log records every passkey login and the refusals that name a
known passkey, at most one such refusal per account and minute, because no
throttle bounds how often someone holding a credential id can try.
Refusals before a known passkey is found are only logged.
"""

from src.modules.platform.application.dto.login_dto import SessionIssued
from src.modules.platform.application.dto.passkey_dto import PasskeyChallenge
from src.modules.platform.application.dto.passkey_dto import PasskeyLoginCommand
from src.modules.platform.application.services.passkey_challenge import issue_passkey_challenge
from src.modules.platform.application.services.passkey_challenge import redeem_passkey_challenge
from src.modules.platform.application.services.security_audit import SecurityAudit
from src.modules.platform.application.use_cases.auth.login_steps import LoginSteps
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InactiveUserError
from src.modules.platform.domain.exceptions import MaintenanceModeError
from src.modules.platform.domain.exceptions import PasskeyPasswordRequiredError
from src.modules.platform.domain.exceptions import PasskeyRejectedError
from src.modules.platform.domain.services.login_policy import passkey_needs_password
from src.modules.platform.domain.value_objects import token_scope
from src.modules.platform.domain.value_objects.security_event_type import LoginMethod
from src.modules.platform.domain.value_objects.security_event_type import LoginRefusal
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.login_attempt_tracker_port import ILoginAttemptTracker
from src.modules.platform.ports.outbound.passkey_verifier_port import IPasskeyVerifier
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.replay_guard_port import IReplayGuard
from src.modules.platform.ports.outbound.repositories.passkey_repository import IPasskeyRepository
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.repositories.user_session_repository import (
    IUserSessionRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc

# At most one refused passkey login per account is recorded in this many
# seconds.
REFUSAL_RECORD_INTERVAL_SECONDS = 60


class BeginPasskeyLogin:
    def __init__(self, verifier: IPasskeyVerifier) -> None:
        self._verifier = verifier

    def execute(self) -> PasskeyChallenge:
        options = self._verifier.authentication_options()
        return PasskeyChallenge(
            options=options.options,
            challenge_token=issue_passkey_challenge(options.challenge, token_scope.PASSKEY_LOGIN),
        )


class PasskeyLogin:
    def __init__(
        self,
        *,
        user_repo: IUserRepository,
        settings_repo: IPlatformSettingsRepository,
        attempts: ILoginAttemptTracker,
        session_repo: IUserSessionRepository,
        passkey_repo: IPasskeyRepository,
        replay_guard: IReplayGuard,
        verifier: IPasskeyVerifier,
        uow: IUnitOfWork,
        audit: SecurityAudit | None = None,
    ) -> None:
        self._user_repo = user_repo
        self._attempts = attempts
        self._audit = audit or SecurityAudit.disabled()
        self._passkeys = passkey_repo
        self._replay_guard = replay_guard
        self._verifier = verifier
        self._steps = LoginSteps(
            user_repo=user_repo,
            settings_repo=settings_repo,
            attempts=attempts,
            session_repo=session_repo,
            uow=uow,
            audit=audit,
        )

    async def execute(self, cmd: PasskeyLoginCommand) -> SessionIssued:
        challenge = await redeem_passkey_challenge(
            cmd.challenge_token, scope=token_scope.PASSKEY_LOGIN, replay_guard=self._replay_guard
        )
        if challenge is None:
            raise PasskeyRejectedError("Invalid or expired passkey challenge.")

        credential_id = self._verifier.credential_id_of(cmd.credential)
        passkey = (
            await self._passkeys.get_by_credential_id(credential_id) if credential_id else None
        )
        if passkey is None:
            log.warning("Passkey login with an unknown credential.")
            raise PasskeyRejectedError("Unknown passkey.")
        user = await self._user_repo.get_by_id(passkey.user_id)
        if user is None:
            raise PasskeyRejectedError("Unknown passkey.")

        try:
            new_sign_count = self._verifier.verify_authentication(
                credential=cmd.credential,
                challenge=challenge,
                public_key=passkey.public_key,
                sign_count=passkey.sign_count,
            )
        except PasskeyRejectedError:
            await self._refuse(cmd, user, LoginRefusal.PASSKEY_REJECTED)
            raise

        if not user.is_active:
            log.warning("Login blocked, inactive account: %r (id=%s).", user.username, user.id)
            await self._refuse(cmd, user, LoginRefusal.INACTIVE)
            raise InactiveUserError("Account is inactive.")
        # Registration refuses both, so such a passkey can only be a leftover
        # from before the account changed kind.
        if user.is_systemuser or user.is_service_account:
            await self._refuse(cmd, user, LoginRefusal.PASSKEY_REJECTED)
            raise PasskeyRejectedError("This account cannot use passkeys.")

        now = now_utc()
        auth = await self._steps.auth_settings()
        if passkey_needs_password(user, ldap_enabled=auth.ldap_enabled, now=now):
            await self._refuse(cmd, user, LoginRefusal.PASSWORD_REQUIRED)
            raise PasskeyPasswordRequiredError(
                "Sign in with your password once to confirm your directory account."
            )
        try:
            await self._steps.check_maintenance(user, cmd.client_ip)
        except MaintenanceModeError:
            await self._refuse(cmd, user, LoginRefusal.MAINTENANCE)
            raise

        passkey.sign_count = new_sign_count
        passkey.last_used_at = now
        await self._passkeys.save(passkey)
        await self._steps.stamp_login(user)
        log.info(
            "User %r (id=%s) authenticated via passkey %s.",
            user.username,
            user.id,
            passkey.public_id,
        )
        return await self._steps.issue_session(
            user, method=LoginMethod.PASSKEY, user_agent=cmd.user_agent, client_ip=cmd.client_ip
        )

    async def _refuse(self, cmd: PasskeyLoginCommand, user: User, reason: LoginRefusal) -> None:
        """Records the refusal unless one for this account was recorded
        within the interval."""
        if not self._audit.records or not await self._attempts.claim(
            f"audit:passkey:{user.id}", REFUSAL_RECORD_INTERVAL_SECONDS
        ):
            return
        await self._steps.record_refusal(
            user,
            method=LoginMethod.PASSKEY,
            reason=reason,
            client_ip=cmd.client_ip,
            user_agent=cmd.user_agent,
        )
