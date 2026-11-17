"""
Upload (or replace) a user's avatar image via the active storage provider.
"""

import uuid

from src.modules.platform.application.dto.user_dto import UserResult
from src.modules.platform.application.mappers.user_mapper import UserMapper
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.services.storage_asset import assert_allowed_type
from src.modules.platform.application.services.storage_asset import assert_magic_bytes_match
from src.modules.platform.application.services.storage_asset import assert_within_size_limit
from src.modules.platform.application.services.storage_asset import replace_stored_asset
from src.modules.platform.application.services.storage_asset import resolve_extension
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import AvatarInvalidTypeError
from src.modules.platform.domain.exceptions import AvatarTooLargeError
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.exceptions import StorageNotEnabledError
from src.modules.platform.domain.exceptions import UserNotFoundError
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.repositories.user_pdm_link_repository import (
    IUserPdmLinkRepository,
)
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.storage_port import IStoragePort
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork

_ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_BYTES = 5 * 1024 * 1024  # 5 MB
_EXT_OVERRIDES = {"image/jpeg": ".jpg"}  # mimetypes' canonical .jpe guess is non-standard


class UploadUserAvatar:
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

    async def execute(
        self, actor: User, user_id: int, data: bytes, content_type: str
    ) -> UserResult:
        if self._storage is None:
            raise StorageNotEnabledError("Storage is not enabled.")

        if actor.id != user_id and not actor.has_permission(Permission.WRITE_SETTINGS):
            raise InsufficientPermissionsError("Cannot update another user's avatar.")

        assert_within_size_limit(data, MAX_BYTES, error=AvatarTooLargeError, label="Avatar")
        assert_allowed_type(
            content_type, _ALLOWED_TYPES, error=AvatarInvalidTypeError, label="image"
        )
        assert_magic_bytes_match(data, content_type, error=AvatarInvalidTypeError, label="image")

        user = found_or_raise(
            await self._repo.get_by_id(user_id), UserNotFoundError, f"User #{user_id} not found."
        )

        ext = resolve_extension(content_type, _EXT_OVERRIDES)
        key = f"users/avatars/{user_id}/{uuid.uuid4().hex}{ext}"

        async def save() -> User:
            user.avatar_key = key
            return await self._repo.save(user)

        saved = await replace_stored_asset(
            self._storage,
            self._uow,
            key=key,
            old_key=user.avatar_key,
            data=data,
            save=save,
            label=f"avatar for user #{user_id}",
        )

        log.info(
            "Avatar uploaded for user #%s (%s bytes, %s).",
            user_id,
            len(data),
            content_type,
        )
        return UserMapper.to_result(saved, await self._links.list_by_user(saved.id))
