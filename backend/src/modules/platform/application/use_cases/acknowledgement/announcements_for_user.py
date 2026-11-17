"""
The user-facing half of the announcements feature: any active user (no
read:settings/write:settings gate, enforced only by
auth_deps.get_current_active_user) may see what's addressed to them and
confirm an acknowledgement.
"""

from uuid import UUID

from src.modules.platform.application.dto.acknowledgement_dto import MyAnnouncementsBannerResult
from src.modules.platform.application.dto.acknowledgement_dto import MyAnnouncementsResult
from src.modules.platform.application.mappers.acknowledgement_mapper import AcknowledgementMapper
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import AcknowledgementNotFoundError
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.repositories.acknowledgement_repository import (
    IAcknowledgementRepository,
)
from src.modules.platform.ports.outbound.repositories.user_session_repository import (
    IUserSessionRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc


class GetMyAnnouncements:
    def __init__(
        self,
        ack_repo: IAcknowledgementRepository,
        settings_repo: IPlatformSettingsRepository,
        session_repo: IUserSessionRepository,
    ) -> None:
        self._acks = ack_repo
        self._settings = settings_repo
        self._sessions = session_repo

    async def execute(self, actor: User, current_sid: UUID | None) -> MyAnnouncementsResult:
        banner_settings = await self._settings.get_banner()
        banner = None
        if banner_settings.enabled and banner_settings.text.strip():
            banner = MyAnnouncementsBannerResult(
                text=banner_settings.text,
                severity=banner_settings.severity,
                shows_from=banner_settings.shows_from,
                shows_until=banner_settings.shows_until,
                dismissable=banner_settings.dismissable,
                updated_at=banner_settings.updated_at,
            )

        # No current_sid, or it names a session that is already gone or
        # belongs to someone else, shouldn't happen on an authenticated
        # route, fail safe to "no session known" (next_login acks omitted)
        # rather than 500. Mirrors GetCurrentSession's same defensive
        # check in manage_sessions.py.
        session = await self._sessions.get_by_public_id(current_sid) if current_sid else None
        session_created_at = (
            session.created_at if session is not None and session.user_id == actor.id else None
        )

        pending = await self._acks.get_pending_for_user(actor.id, session_created_at)
        return MyAnnouncementsResult(
            banner=banner,
            pending_acknowledgements=[AcknowledgementMapper.to_pending_result(a) for a in pending],
        )


class AcknowledgeAnnouncement:
    def __init__(self, ack_repo: IAcknowledgementRepository, *, uow: IUnitOfWork) -> None:
        self._acks = ack_repo
        self._uow = uow

    async def execute(self, actor: User, public_id: UUID) -> None:
        """204 whether this is the first confirmation or a repeat one
        (idempotent, see IAcknowledgementRepository.acknowledge)."""
        found = await self._acks.acknowledge(public_id, actor.id, now_utc())
        if not found:
            raise AcknowledgementNotFoundError(
                f"Acknowledgement {public_id} not found, disabled, or you are not a recipient."
            )
        await self._uow.commit()
