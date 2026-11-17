"""
Soft-deletes a user by setting is_active=False, recorded in the security
log as a deactivation.
All linked records (orders, items, files, etc.) are preserved intact, except the
user's time tracking credentials, which deactivation deletes.
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
from src.modules.platform.ports.outbound.repositories.user_pdm_link_repository import (
    IUserPdmLinkRepository,
)
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.platform.ports.outbound.user_held_credentials_port import IUserHeldCredentials


class DeleteUser:
    def __init__(
        self,
        user_repo: IUserRepository,
        link_repo: IUserPdmLinkRepository,
        *,
        uow: IUnitOfWork,
        time_tracking_credentials_repo: IUserHeldCredentials | None = None,
        audit: SecurityAudit | None = None,
    ) -> None:
        self._repo = user_repo
        self._links = link_repo
        self._uow = uow
        self._time_tracking_credentials = time_tracking_credentials_repo
        self._audit = audit or SecurityAudit.disabled()

    async def execute(self, actor: User, target_id: int) -> UserResult:
        target = found_or_raise(
            await self._repo.get_by_id(target_id),
            UserNotFoundError,
            f"User #{target_id} not found.",
        )

        UserRules.assert_can_delete(actor, target)

        was_active = target.is_active
        target.is_active = False
        saved = await self._repo.save(target)
        if was_active:
            await self._audit.record(
                SecurityEventType.USER_DEACTIVATED, actor=actor, target_user=saved
            )
        if self._time_tracking_credentials is not None:
            await self._time_tracking_credentials.delete_for_user(saved.id)
        await self._uow.commit()

        log.info(f"Deactivated user {target.username!r} (ID={target.id}).")
        return UserMapper.to_result(saved, await self._links.list_by_user(saved.id))
