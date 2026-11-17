"""
Invalidates all active sessions for a user by incrementing token_version
and revoking all of their personal access tokens. Any JWT issued with a
lower version, or any revoked PAT, is rejected on the next request.
"""

from src.modules.platform.application.dto.user_dto import UserResult
from src.modules.platform.application.mappers.user_mapper import UserMapper
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.services.security_audit import SecurityAudit
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.events.user_events import UserForcedLogout
from src.modules.platform.domain.exceptions import UserNotFoundError
from src.modules.platform.domain.services.user_rules import UserRules
from src.modules.platform.domain.value_objects.security_event_type import SecurityEventType
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.repositories.pat_repository import IPatRepository
from src.modules.platform.ports.outbound.repositories.trusted_device_repository import (
    ITrustedDeviceRepository,
)
from src.modules.platform.ports.outbound.repositories.user_pdm_link_repository import (
    IUserPdmLinkRepository,
)
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.repositories.user_session_repository import (
    IUserSessionRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class ForceLogoutUser:
    def __init__(
        self,
        user_repo: IUserRepository,
        pat_repo: IPatRepository,
        session_repo: IUserSessionRepository,
        trusted_device_repo: ITrustedDeviceRepository,
        link_repo: IUserPdmLinkRepository,
        *,
        event_bus: IEventBus,
        uow: IUnitOfWork,
        audit: SecurityAudit | None = None,
    ) -> None:
        self._repo = user_repo
        self._pats = pat_repo
        self._sessions = session_repo
        self._trusted_devices = trusted_device_repo
        self._links = link_repo
        self._bus = event_bus
        self._uow = uow
        self._audit = audit or SecurityAudit.disabled()

    async def execute(self, actor: User, target_id: int) -> UserResult:
        target = found_or_raise(
            await self._repo.get_by_id(target_id),
            UserNotFoundError,
            f"User #{target_id} not found.",
        )

        UserRules.assert_can_force_logout(actor, target)

        target.token_version += 1
        saved = await self._repo.save(target)
        pats_revoked = await self._pats.revoke_all_for_user(target.id)
        # The version bump already kills every session token; revoking the
        # rows too keeps the sessions list honest, and trusted devices must
        # go with them, force-logout means "this account's credentials are
        # no longer to be trusted anywhere".
        sessions_revoked = await self._sessions.revoke_all_for_user(target.id)
        await self._trusted_devices.revoke_all_for_user(target.id)
        await self._audit.record(
            SecurityEventType.SESSION_REVOKED,
            actor=actor,
            target_user=saved,
            detail={
                "scope": "forced",
                "sessions": sessions_revoked,
                "personal_access_tokens": pats_revoked,
            },
        )

        await self._bus.publish(UserForcedLogout(user_id=saved.id, actor_id=actor.id))
        await self._uow.commit()

        log.info(f"Force-logged out {target.username!r} (ID={target.id}).")
        return UserMapper.to_result(saved, await self._links.list_by_user(saved.id))
