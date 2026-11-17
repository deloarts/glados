"""
Self-service management of the acting user's trusted devices (the TOTP
"don't ask again" grants). Always scoped to the actor; the sweeping
revocations (password change, TOTP disable/reset, force-logout) live in
their respective use cases, not here.
"""

from uuid import UUID

from src.modules.platform.application.dto.session_dto import TrustedDeviceResult
from src.modules.platform.domain.entities.trusted_device import TrustedDevice
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import TrustedDeviceNotFoundError
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.repositories.trusted_device_repository import (
    ITrustedDeviceRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


def _to_result(device: TrustedDevice) -> TrustedDeviceResult:
    return TrustedDeviceResult(
        id=device.id,
        public_id=device.public_id,
        created_at=device.created_at,
        last_used_at=device.last_used_at,
        expires_at=device.expires_at,
        user_agent=device.user_agent,
    )


class GetMyTrustedDevices:
    def __init__(self, trusted_device_repo: ITrustedDeviceRepository) -> None:
        self._devices = trusted_device_repo

    async def execute(self, actor: User) -> list[TrustedDeviceResult]:
        return [_to_result(d) for d in await self._devices.list_for_user(actor.id)]


class RevokeMyTrustedDevice:
    def __init__(self, trusted_device_repo: ITrustedDeviceRepository, *, uow: IUnitOfWork) -> None:
        self._devices = trusted_device_repo
        self._uow = uow

    async def execute(self, actor: User, public_id: UUID) -> None:
        """Scoped by actor.id in the repository call, a guessed public_id
        belonging to someone else 404s exactly like a nonexistent one."""
        if not await self._devices.revoke_by_public_id(actor.id, public_id):
            raise TrustedDeviceNotFoundError(f"Trusted device {public_id} not found.")
        await self._uow.commit()
        log.info(f"Revoked trusted device {public_id}.")


class RevokeAllMyTrustedDevices:
    def __init__(self, trusted_device_repo: ITrustedDeviceRepository, *, uow: IUnitOfWork) -> None:
        self._devices = trusted_device_repo
        self._uow = uow

    async def execute(self, actor: User) -> int:
        count = await self._devices.revoke_all_for_user(actor.id)
        await self._uow.commit()
        log.info(f"Revoked {count} trusted device(s).")
        return count
