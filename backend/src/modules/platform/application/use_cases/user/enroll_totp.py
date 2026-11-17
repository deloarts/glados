"""
Generates and stores a new TOTP secret for a user without yet enabling 2FA.
The caller must follow up with ConfirmTOTPEnrollment to activate it. An
account that already has 2FA on is refused, so a session alone can never
replace the active factor.

A user enrolling from a session gives the current password again, so
whoever finds an unlocked session cannot put a second factor of their own
on the account and lock its owner out. A user forced to enrol at sign-in
proved the password moments ago and is not asked again. Wrong passwords
count toward the login throttle (password_confirmation.py).
"""

from collections.abc import Callable
from dataclasses import dataclass

from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.use_cases.user.password_confirmation import (
    PasswordConfirmation,
)
from src.modules.platform.domain.exceptions import CurrentPasswordRequiredError
from src.modules.platform.domain.exceptions import TOTPAlreadyEnabledError
from src.modules.platform.domain.exceptions import UserNotFoundError
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


@dataclass
class TOTPEnrollmentResult:
    secret: str
    provisioning_uri: str


class EnrollTOTP:
    def __init__(
        self,
        user_repo: IUserRepository,
        secret_factory: Callable[[], str],
        uri_factory: Callable[[str, str], str],  # (secret, username) -> provisioning_uri
        *,
        password_confirmation: PasswordConfirmation,
        uow: IUnitOfWork,
    ) -> None:
        self._repo = user_repo
        self._secret_factory = secret_factory
        self._uri_factory = uri_factory
        self._password_confirmation = password_confirmation
        self._uow = uow

    async def execute(
        self,
        user_id: int,
        *,
        password: str | None,
        proven_at_sign_in: bool,
        client_ip: str | None = None,
    ) -> TOTPEnrollmentResult:
        user = found_or_raise(
            await self._repo.get_by_id(user_id), UserNotFoundError, f"User {user_id} not found."
        )
        # Login checks the stored secret as soon as 2FA is on, so replacing
        # it here would swap the active factor for whoever holds the session.
        if user.totp_enabled:
            raise TOTPAlreadyEnabledError(
                "2FA is already enabled. Disable it before enrolling again."
            )
        if not proven_at_sign_in:
            if not password:
                raise CurrentPasswordRequiredError("Setting up 2FA requires your current password.")
            # Re-reads the account with the password proven, which ends the
            # read transaction, so the secret is set on the returned row.
            user = await self._password_confirmation.confirm(user, password, client_ip=client_ip)
        secret = self._secret_factory()
        user.totp_secret = secret
        # totp_enabled stays False until ConfirmTOTPEnrollment succeeds
        await self._repo.save(user)
        await self._uow.commit()
        log.info("TOTP enrollment started.")
        return TOTPEnrollmentResult(
            secret=secret,
            provisioning_uri=self._uri_factory(secret, user.username),
        )
