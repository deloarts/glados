"""Validate and upload a new system favicon to storage, replacing the previous one
and auditing the change."""

from dataclasses import replace

from src.modules.platform.application.dto.admin_settings_dto.branding import (
    AdminBrandingSettingsResult,
)
from src.modules.platform.application.mappers.admin_settings_mapper.branding import (
    BrandingSettingsMapper,
)
from src.modules.platform.application.services.storage_asset import assert_allowed_type
from src.modules.platform.application.services.storage_asset import assert_magic_bytes_match
from src.modules.platform.application.services.storage_asset import assert_within_size_limit
from src.modules.platform.application.services.storage_asset import replace_stored_asset
from src.modules.platform.application.services.storage_asset import resolve_extension
from src.modules.platform.domain.entities.admin_settings.audit import AdminSettingsAuditEntry
from src.modules.platform.domain.entities.admin_settings.branding import AdminBrandingSettings
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import BrandingImageInvalidTypeError
from src.modules.platform.domain.exceptions import BrandingImageTooLargeError
from src.modules.platform.domain.exceptions import StorageNotEnabledError
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.storage_port import IStoragePort
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork

_ALLOWED_TYPES = {"image/x-icon", "image/vnd.microsoft.icon", "image/png", "image/svg+xml"}
MAX_BYTES = 2 * 1024 * 1024  # 2 MB
_EXT_OVERRIDES = {
    "image/x-icon": ".ico",
    "image/vnd.microsoft.icon": ".ico",
    "image/png": ".png",
    "image/svg+xml": ".svg",
}


class UploadBrandingFavicon:
    def __init__(
        self,
        repo: IPlatformSettingsRepository,
        storage: IStoragePort | None,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._repo = repo
        self._storage = storage
        self._uow = uow

    async def execute(
        self, actor: User, data: bytes, content_type: str
    ) -> AdminBrandingSettingsResult:
        if self._storage is None:
            raise StorageNotEnabledError("Storage is not enabled.")

        SettingsRules.assert_can_write(actor)

        assert_within_size_limit(data, MAX_BYTES, error=BrandingImageTooLargeError, label="Favicon")
        assert_allowed_type(
            content_type, _ALLOWED_TYPES, error=BrandingImageInvalidTypeError, label="favicon"
        )
        assert_magic_bytes_match(
            data, content_type, error=BrandingImageInvalidTypeError, label="favicon"
        )

        current = await self._repo.get_branding()
        key = f"public/favicon{resolve_extension(content_type, _EXT_OVERRIDES)}"

        async def save() -> AdminBrandingSettings:
            saved = await self._repo.save_branding(replace(current, favicon_key=key))
            await self._repo.append_audit(
                AdminSettingsAuditEntry.by_actor(
                    actor,
                    settings_domain="branding",
                    summary=f"Branding favicon uploaded by {actor.username}.",
                )
            )
            return saved

        saved = await replace_stored_asset(
            self._storage,
            self._uow,
            key=key,
            old_key=current.favicon_key,
            data=data,
            save=save,
            label="branding favicon",
        )

        log.info("Uploaded a new branding favicon.")
        return BrandingSettingsMapper.branding_to_result(saved)
