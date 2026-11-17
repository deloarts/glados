"""
Resolves a public_id (e.g. scanned from a QR tag) back to the resource
type and internal id that owns it, so the frontend can route to it
regardless of which screen the scan happened on.
"""

from uuid import UUID

from fastapi import Depends
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.deps.misc import get_resolve_public_id_use_case
from src.modules.platform.application.dto.resolve_dto import ResolvePublicIdResult
from src.modules.platform.application.use_cases.resolve.resolve_public_id import ResolvePublicId
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/{public_id}", response_model=ResolvePublicIdResult)
async def resolve_public_id(
    public_id: UUID,
    _: User = Depends(get_current_active_user),
    use_case: ResolvePublicId = Depends(get_resolve_public_id_use_case),
) -> ResolvePublicIdResult:
    return await use_case.execute(public_id)
