"""
Self-service management of trusted devices (TOTP "don't ask again").
Mounted at /api/v1/web/users/me/trusted-devices. Always scoped to the
acting user's own grants.
"""

from uuid import UUID

from fastapi import Depends
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.deps.auth import get_my_trusted_devices_use_case
from src.modules.platform.adapters.inbound.api.deps.auth import (
    get_revoke_all_my_trusted_devices_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.auth import (
    get_revoke_my_trusted_device_use_case,
)
from src.modules.platform.adapters.inbound.api.schemas.session_schema import RevokedCountResult
from src.modules.platform.adapters.inbound.api.schemas.session_schema import TrustedDeviceResult
from src.modules.platform.application.use_cases.session.manage_trusted_devices import (
    GetMyTrustedDevices,
)
from src.modules.platform.application.use_cases.session.manage_trusted_devices import (
    RevokeAllMyTrustedDevices,
)
from src.modules.platform.application.use_cases.session.manage_trusted_devices import (
    RevokeMyTrustedDevice,
)
from src.modules.platform.domain.entities.user import User

router = APIRouter()


# Deliberately unpaginated: bounded per-user collection.
@router.get("/", response_model=list[TrustedDeviceResult])
async def read_my_trusted_devices(
    actor: User = Depends(get_current_active_user),
    use_case: GetMyTrustedDevices = Depends(get_my_trusted_devices_use_case),
) -> list[TrustedDeviceResult]:
    """The acting user's live trusted-device grants, newest first."""
    return await use_case.execute(actor)


@router.delete("/", response_model=RevokedCountResult)
async def revoke_all_my_trusted_devices(
    actor: User = Depends(get_current_active_user),
    use_case: RevokeAllMyTrustedDevices = Depends(get_revoke_all_my_trusted_devices_use_case),
) -> RevokedCountResult:
    """Un-trust every device, TOTP will be asked everywhere again."""
    count = await use_case.execute(actor)
    return RevokedCountResult(revoked=count)


@router.delete("/{public_id}", response_model=dict)
async def revoke_my_trusted_device(
    public_id: UUID,
    actor: User = Depends(get_current_active_user),
    use_case: RevokeMyTrustedDevice = Depends(get_revoke_my_trusted_device_use_case),
) -> dict[str, str]:
    await use_case.execute(actor, public_id)
    return {"detail": "Trusted device revoked"}
