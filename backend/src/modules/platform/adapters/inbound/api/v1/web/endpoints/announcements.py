"""
User-facing surface for the banner + acknowledgements features: any
active user (no read:settings/write:settings gate) may fetch what's
currently addressed to them and confirm an acknowledgement. Mounted at
/announcements.
"""

from uuid import UUID

from fastapi import Depends
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.deps.acknowledgements import (
    get_acknowledge_announcement_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.acknowledgements import (
    get_my_announcements_use_case,
)
from src.modules.platform.application.dto.acknowledgement_dto import MyAnnouncementsResult
from src.modules.platform.application.use_cases.acknowledgement.announcements_for_user import (
    AcknowledgeAnnouncement,
)
from src.modules.platform.application.use_cases.acknowledgement.announcements_for_user import (
    GetMyAnnouncements,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.context import current_session_id

router = APIRouter()


@router.get("/me", response_model=MyAnnouncementsResult)
async def read_my_announcements(
    actor: User = Depends(get_current_active_user),
    use_case: GetMyAnnouncements = Depends(get_my_announcements_use_case),
) -> MyAnnouncementsResult:
    """The signed-in banner (if any) plus every acknowledgement still
    awaiting this user's confirmation, oldest first."""
    return await use_case.execute(actor, current_session_id())


@router.post("/acknowledgements/{public_id}/acknowledge", status_code=status.HTTP_204_NO_CONTENT)
async def acknowledge_announcement(
    public_id: UUID,
    actor: User = Depends(get_current_active_user),
    use_case: AcknowledgeAnnouncement = Depends(get_acknowledge_announcement_use_case),
) -> None:
    """Confirm one acknowledgement. Idempotent: already-confirmed is still
    204."""
    await use_case.execute(actor, public_id)
