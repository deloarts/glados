"""
Registering a passkey for the acting user, in two requests around the
browser's prompt: the options (after the password was confirmed) and the
verification of what the authenticator created.

The password is asked for again even though the caller has a session: a
passkey signs in without password and TOTP, so whoever finds an unlocked
session must not be able to plant one of their own. Wrong passwords count
toward the same throttle as the login form, so this route cannot be used to
guess around it (password_confirmation.py). A wrong password and the new
passkey are recorded in the security log.
"""

from collections.abc import Awaitable
from collections.abc import Callable

from src.modules.platform.application.dto.passkey_dto import PasskeyChallenge
from src.modules.platform.application.dto.passkey_dto import PasskeyResult
from src.modules.platform.application.dto.passkey_dto import RegisterPasskeyCommand
from src.modules.platform.application.services.passkey_challenge import issue_passkey_challenge
from src.modules.platform.application.services.passkey_challenge import redeem_passkey_challenge
from src.modules.platform.application.services.security_audit import SecurityAudit
from src.modules.platform.application.use_cases.passkey.manage_passkeys import to_passkey_result
from src.modules.platform.application.use_cases.user.password_confirmation import (
    PasswordConfirmation,
)
from src.modules.platform.domain.entities.passkey import make_passkey
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import PasskeyRegistrationFailedError
from src.modules.platform.domain.services.user_rules import UserRules
from src.modules.platform.domain.value_objects import token_scope
from src.modules.platform.domain.value_objects.security_event_type import SecurityEventType
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.ldap_authenticator_port import ILdapAuthenticator
from src.modules.platform.ports.outbound.login_attempt_tracker_port import ILoginAttemptTracker
from src.modules.platform.ports.outbound.passkey_verifier_port import IPasskeyVerifier
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.replay_guard_port import IReplayGuard
from src.modules.platform.ports.outbound.repositories.passkey_repository import IPasskeyRepository
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc

DEFAULT_PASSKEY_NAME = "Passkey"


class BeginPasskeyRegistration:
    def __init__(
        self,
        *,
        user_repo: IUserRepository,
        passkey_repo: IPasskeyRepository,
        settings_repo: IPlatformSettingsRepository,
        attempts: ILoginAttemptTracker,
        ldap: ILdapAuthenticator | None,
        verifier: IPasskeyVerifier,
        uow: IUnitOfWork,
        verify_fn: Callable[[str, str], Awaitable[bool]],
        audit: SecurityAudit | None = None,
    ) -> None:
        self._user_repo = user_repo
        self._passkeys = passkey_repo
        self._settings = settings_repo
        self._attempts = attempts
        self._ldap = ldap
        self._verifier = verifier
        self._uow = uow
        self._verify = verify_fn
        self._audit = audit

    async def execute(
        self, actor: User, password: str, *, client_ip: str | None = None
    ) -> PasskeyChallenge:
        UserRules.assert_can_register_passkey(actor)
        user = await PasswordConfirmation(
            user_repo=self._user_repo,
            settings_repo=self._settings,
            attempts=self._attempts,
            ldap=self._ldap,
            uow=self._uow,
            verify_fn=self._verify,
            audit=self._audit,
        ).confirm(actor, password, client_ip=client_ip)

        # A confirmed password is as good as a password login for the
        # directory recheck of later passkey logins.
        user.password_verified_at = now_utc()
        await self._user_repo.save(user)

        existing = await self._passkeys.list_for_user(user.id)
        options = self._verifier.registration_options(
            user_handle=user.public_id.bytes,
            username=user.username,
            display_name=user.full_name,
            exclude_credential_ids=[p.credential_id for p in existing],
        )
        await self._uow.commit()
        return PasskeyChallenge(
            options=options.options,
            challenge_token=issue_passkey_challenge(
                options.challenge, token_scope.PASSKEY_REGISTRATION, user_id=user.id
            ),
        )


class FinishPasskeyRegistration:
    def __init__(
        self,
        *,
        passkey_repo: IPasskeyRepository,
        replay_guard: IReplayGuard,
        verifier: IPasskeyVerifier,
        uow: IUnitOfWork,
        audit: SecurityAudit | None = None,
    ) -> None:
        self._passkeys = passkey_repo
        self._replay_guard = replay_guard
        self._verifier = verifier
        self._uow = uow
        self._audit = audit or SecurityAudit.disabled()

    async def execute(self, actor: User, cmd: RegisterPasskeyCommand) -> PasskeyResult:
        UserRules.assert_can_register_passkey(actor)
        challenge = await redeem_passkey_challenge(
            cmd.challenge_token,
            scope=token_scope.PASSKEY_REGISTRATION,
            replay_guard=self._replay_guard,
            user_id=actor.id,
        )
        if challenge is None:
            raise PasskeyRegistrationFailedError("The passkey registration expired. Start again.")

        verified = self._verifier.verify_registration(
            credential=cmd.credential, challenge=challenge
        )
        if await self._passkeys.get_by_credential_id(verified.credential_id) is not None:
            raise PasskeyRegistrationFailedError("This passkey is already registered.")

        saved = await self._passkeys.save(
            make_passkey(
                user_id=actor.id,
                credential_id=verified.credential_id,
                public_key=verified.public_key,
                sign_count=verified.sign_count,
                name=cmd.name.strip() or DEFAULT_PASSKEY_NAME,
                transports=verified.transports,
                backed_up=verified.backed_up,
            )
        )
        await self._audit.record(
            SecurityEventType.PASSKEY_ADDED,
            actor=actor,
            target_user=actor,
            target_id=saved.id,
            detail={"name": saved.name},
        )
        await self._uow.commit()
        log.info(f"Registered passkey {saved.public_id} ({saved.name!r}).")
        return to_passkey_result(saved)
