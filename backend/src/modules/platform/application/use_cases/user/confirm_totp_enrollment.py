"""
Verifies a TOTP code against the stored (but not yet active) secret,
then activates 2FA on the account and records that in the security log.
"""

from collections.abc import Awaitable
from collections.abc import Callable

from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.services.security_audit import SecurityAudit
from src.modules.platform.domain.exceptions import InvalidTOTPCodeError
from src.modules.platform.domain.exceptions import TOTPNotEnabledError
from src.modules.platform.domain.exceptions import UserNotFoundError
from src.modules.platform.domain.value_objects.security_event_type import SecurityEventType
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class ConfirmTOTPEnrollment:
    def __init__(
        self,
        user_repo: IUserRepository,
        verify: Callable[[str, str], Awaitable[bool]],  # (secret, code) -> bool
        *,
        uow: IUnitOfWork,
        audit: SecurityAudit | None = None,
    ) -> None:
        self._repo = user_repo
        self._verify = verify
        self._uow = uow
        self._audit = audit or SecurityAudit.disabled()

    async def execute(self, user_id: int, totp_code: str) -> None:
        user = found_or_raise(
            await self._repo.get_by_id(user_id), UserNotFoundError, f"User {user_id} not found."
        )
        if not user.totp_secret:
            raise TOTPNotEnabledError("No TOTP enrollment in progress. Call enroll first.")
        if not await self._verify(user.totp_secret, totp_code):
            # No log line here: this request is already
            # authenticated as `user`, so domain_error_handler's own log
            # line for InvalidTOTPCodeError carries the same username/id
            # automatically via ContextFilter's user_ctx, so logging it again
            # here would just double it.
            raise InvalidTOTPCodeError("Invalid TOTP code.")
        user.totp_enabled = True
        await self._repo.save(user)
        await self._audit.record(SecurityEventType.TOTP_ENABLED, actor=user, target_user=user)
        await self._uow.commit()
        log.info("TOTP 2FA activated.")
