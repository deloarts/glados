"""
Administrative 2FA reset, the way back in for a user who has lost their
authenticator device.

Distinct from the self-service `DELETE /users/me/totp/`, which requires the
user's current TOTP code: that code is exactly what someone who has lost
the device cannot produce. The trade is that this route needs
write:settings and cannot be aimed at yourself (see
UserRules.assert_can_reset_totp).

Deliberately does *not* invalidate the target's sessions. Force-logout is
its own action (`DELETE /users/{id}/session`), so bundling the two here
would remove the admin's choice, a user who simply replaced their phone
should not be signed out of their desktop as a side effect. Where a device
is believed compromised, run both.

Trusted devices do NOT survive, though: they exist purely to vouch for
the second factor being reset here, and the replacement secret must earn
its own trust. (A live desktop session staying signed in is a different
thing from a browser silently skipping the *new* TOTP at its next login.)

Once enforce_totp is switched on, clearing `totp_enabled` puts the user
back through forced enrolment at their next login, with no extra wiring.
"""

from src.modules.platform.application.dto.user_dto import UserResult
from src.modules.platform.application.mappers.user_mapper import UserMapper
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.services.security_audit import SecurityAudit
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import UserNotFoundError
from src.modules.platform.domain.services.user_rules import UserRules
from src.modules.platform.domain.value_objects.security_event_type import SecurityEventType
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.repositories.trusted_device_repository import (
    ITrustedDeviceRepository,
)
from src.modules.platform.ports.outbound.repositories.user_pdm_link_repository import (
    IUserPdmLinkRepository,
)
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class ResetUserTotp:
    def __init__(
        self,
        user_repo: IUserRepository,
        trusted_device_repo: ITrustedDeviceRepository,
        link_repo: IUserPdmLinkRepository,
        *,
        uow: IUnitOfWork,
        audit: SecurityAudit | None = None,
    ) -> None:
        self._repo = user_repo
        self._trusted_devices = trusted_device_repo
        self._links = link_repo
        self._uow = uow
        self._audit = audit or SecurityAudit.disabled()

    async def execute(self, actor: User, target_id: int) -> UserResult:
        target = found_or_raise(
            await self._repo.get_by_id(target_id),
            UserNotFoundError,
            f"User #{target_id} not found.",
        )

        UserRules.assert_can_reset_totp(actor, target)

        target.totp_secret = None
        target.totp_enabled = False
        saved = await self._repo.save(target)
        await self._trusted_devices.revoke_all_for_user(target.id)
        await self._audit.record(SecurityEventType.TOTP_RESET, actor=actor, target_user=saved)
        await self._uow.commit()

        # Security-relevant administrative action: record who did it and to
        # whom, not just that it happened.
        log.info(f"Reset 2FA for {target.username!r} (ID={target.id}).")
        return UserMapper.to_result(saved, await self._links.list_by_user(saved.id))
