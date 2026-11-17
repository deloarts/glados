"""
Remove a user's avatar from storage and clear the avatar_key.
"""

from src.modules.platform.application.dto.user_dto import UserResult
from src.modules.platform.application.mappers.user_mapper import UserMapper
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.services.storage_asset import (
    delete_storage_object_best_effort,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.exceptions import UserNotFoundError
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.repositories.user_pdm_link_repository import (
    IUserPdmLinkRepository,
)
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.storage_port import IStoragePort
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class DeleteUserAvatar:
    def __init__(
        self,
        user_repo: IUserRepository,
        storage: IStoragePort | None,
        link_repo: IUserPdmLinkRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._repo = user_repo
        self._storage = storage
        self._links = link_repo
        self._uow = uow

    async def execute(self, actor: User, user_id: int) -> UserResult:
        if actor.id != user_id and not actor.has_permission(Permission.WRITE_SETTINGS):
            raise InsufficientPermissionsError("Cannot delete another user's avatar.")

        user = found_or_raise(
            await self._repo.get_by_id(user_id), UserNotFoundError, f"User #{user_id} not found."
        )

        if user.avatar_key and self._storage is not None:
            await delete_storage_object_best_effort(
                self._storage, user.avatar_key, context=f"removing avatar for user #{user_id}"
            )

        user.avatar_key = None
        saved = await self._repo.save(user)
        await self._uow.commit()
        log.info("Avatar deleted for user #%s.", user_id)
        return UserMapper.to_result(saved, await self._links.list_by_user(saved.id))
