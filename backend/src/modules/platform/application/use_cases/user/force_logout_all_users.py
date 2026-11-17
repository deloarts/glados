"""
Invalidates sessions for all non-system active users in one operation.
"""

from src.modules.platform.application.services.paging import fetch_all
from src.modules.platform.application.services.security_audit import SecurityAudit
from src.modules.platform.const import MAX_PAGE_SIZE
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.domain.value_objects.security_event_type import SecurityEventType
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.repositories.pat_repository import IPatRepository
from src.modules.platform.ports.outbound.repositories.trusted_device_repository import (
    ITrustedDeviceRepository,
)
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.repositories.user_repository import UserFilterDto
from src.modules.platform.ports.outbound.repositories.user_session_repository import (
    IUserSessionRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class ForceLogoutAllUsers:
    def __init__(
        self,
        user_repo: IUserRepository,
        pat_repo: IPatRepository,
        session_repo: IUserSessionRepository,
        trusted_device_repo: ITrustedDeviceRepository,
        *,
        uow: IUnitOfWork,
        audit: SecurityAudit | None = None,
    ) -> None:
        self._repo = user_repo
        self._pats = pat_repo
        self._sessions = session_repo
        self._trusted_devices = trusted_device_repo
        self._uow = uow
        self._audit = audit or SecurityAudit.disabled()

    async def execute(self, actor: User) -> int:
        """Returns the number of users logged out."""
        if not actor.has_permission(Permission.WRITE_SETTINGS):
            raise InsufficientPermissionsError(
                f"User #{actor.id} ({actor.username!r}) "
                "does not have permission to logout all users."
            )

        users = await fetch_all(
            lambda skip, limit: self._repo.get_multi(
                UserFilterDto(is_active=True, skip=skip, limit=limit)
            ),
            MAX_PAGE_SIZE,
        )

        count = 0
        for user in users:
            if user.is_systemuser or user.id == actor.id:
                continue
            user.token_version += 1
            await self._repo.save(user)
            await self._pats.revoke_all_for_user(user.id)
            await self._sessions.revoke_all_for_user(user.id)
            await self._trusted_devices.revoke_all_for_user(user.id)
            count += 1
        # One entry for the whole action rather than one per user, which
        # names everyone it signed out only in the app log.
        await self._audit.record(
            SecurityEventType.SESSION_REVOKED,
            actor=actor,
            detail={"scope": "forced_all_users", "users": count},
        )
        await self._uow.commit()

        log.info(f"Force-logged out {count} users.")
        return count
