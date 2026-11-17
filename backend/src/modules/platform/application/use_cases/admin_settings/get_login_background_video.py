"""
Stream the login screen's background video bytes fresh from storage on every request.
Unauthenticated, the login screen has no token yet when it requests this.
"""

from src.modules.platform.domain.exceptions import LoginVideoNotFoundError
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.storage_port import IStoragePort
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class GetLoginBackgroundVideo:
    def __init__(
        self,
        repo: IPlatformSettingsRepository,
        storage: IStoragePort | None,
        uow: IUnitOfWork | None = None,
    ) -> None:
        self._repo = repo
        self._storage = storage
        self._uow = uow

    async def execute(self) -> tuple[bytes, str]:
        branding = await self._repo.get_branding()

        if not branding.login_background_video_key or self._storage is None:
            raise LoginVideoNotFoundError("No login background video is configured.")

        # Nothing has been written. Ending the read transaction hands the
        # connection back to the pool for the storage download.
        if self._uow is not None:
            await self._uow.commit()

        return await self._storage.download(branding.login_background_video_key)
