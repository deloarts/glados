"""
Stream a user's avatar image bytes fresh from storage on every request.
"""

from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.exceptions import AvatarNotFoundError
from src.modules.platform.domain.exceptions import UserNotFoundError
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.storage_port import IStoragePort
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class GetUserAvatar:
    def __init__(
        self,
        user_repo: IUserRepository,
        storage: IStoragePort | None,
        uow: IUnitOfWork | None = None,
    ) -> None:
        self._repo = user_repo
        self._storage = storage
        self._uow = uow

    async def execute(self, user_id: int) -> tuple[bytes, str]:
        user = found_or_raise(
            await self._repo.get_by_id(user_id), UserNotFoundError, f"User #{user_id} not found."
        )

        if not user.avatar_key or self._storage is None:
            raise AvatarNotFoundError(f"User #{user_id} has no avatar.")

        # Nothing has been written. Ending the read transaction hands the
        # connection back to the pool for the storage download.
        if self._uow is not None:
            await self._uow.commit()

        return await self._storage.download(user.avatar_key)
