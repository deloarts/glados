"""
Read the branded parts of the web app manifest: the name and description an
installed Glados shows, and whether the branding favicon can be its icon.
Unauthenticated, a browser fetches the manifest before anyone signs in.
"""

from src.modules.platform.application.dto.web_app_manifest_dto import WebAppManifestResult
from src.modules.platform.domain.services.install_icon import install_icon_sizes
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.storage_port import IStoragePort
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class GetWebAppManifest:
    def __init__(
        self,
        repo: IPlatformSettingsRepository,
        storage: IStoragePort | None,
        uow: IUnitOfWork | None = None,
    ) -> None:
        self._repo = repo
        self._storage = storage
        self._uow = uow

    async def execute(self) -> WebAppManifestResult:
        branding = await self._repo.get_branding()
        favicon_type: str | None = None
        favicon_sizes: str | None = None

        if branding.favicon_key and self._storage is not None:
            # Nothing has been written. Ending the read transaction hands the
            # connection back to the pool for the storage download.
            if self._uow is not None:
                await self._uow.commit()
            data, content_type = await self._storage.download(branding.favicon_key)
            favicon_sizes = install_icon_sizes(content_type, data)
            if favicon_sizes is not None:
                favicon_type = content_type

        return WebAppManifestResult(
            name=branding.app_name,
            description=branding.app_description,
            favicon_type=favicon_type,
            favicon_sizes=favicon_sizes,
        )
