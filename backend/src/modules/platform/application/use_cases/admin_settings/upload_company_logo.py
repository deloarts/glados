"""
The company logo is the organisation's own mark, kept apart from the branding
logo, which is how *the application* presents itself. An installation can be
branded "Glados" while the company behind it is "Example Ltd", and the two
images are not interchangeable.
"""

from dataclasses import replace

from src.modules.platform.application.dto.admin_settings_dto.general import (
    AdminGeneralSettingsResult,
)
from src.modules.platform.application.mappers.admin_settings_mapper.general import (
    GeneralSettingsMapper,
)
from src.modules.platform.application.services.storage_asset import assert_allowed_type
from src.modules.platform.application.services.storage_asset import assert_magic_bytes_match
from src.modules.platform.application.services.storage_asset import assert_within_size_limit
from src.modules.platform.application.services.storage_asset import replace_stored_asset
from src.modules.platform.application.services.storage_asset import resolve_extension
from src.modules.platform.domain.entities.admin_settings.audit import AdminSettingsAuditEntry
from src.modules.platform.domain.entities.admin_settings.general import AdminGeneralSettings
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

# Same envelope as the branding logo, an admin uploading a company mark has no
# reason to expect different rules from the one two tabs away.
_ALLOWED_TYPES = {"image/png", "image/jpeg", "image/svg+xml", "image/webp"}
MAX_BYTES = 5 * 1024 * 1024  # 5 MB
_EXT_OVERRIDES = {"image/svg+xml": ".svg"}


class UploadCompanyLogo:
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
    ) -> AdminGeneralSettingsResult:
        if self._storage is None:
            raise StorageNotEnabledError("Storage is not enabled.")

        SettingsRules.assert_can_write(actor)

        assert_within_size_limit(
            data, MAX_BYTES, error=BrandingImageTooLargeError, label="Company logo"
        )
        assert_allowed_type(
            content_type, _ALLOWED_TYPES, error=BrandingImageInvalidTypeError, label="company logo"
        )
        assert_magic_bytes_match(
            data, content_type, error=BrandingImageInvalidTypeError, label="company logo"
        )

        current = await self._repo.get_general()
        key = f"public/company-logo{resolve_extension(content_type, _EXT_OVERRIDES)}"

        async def save() -> AdminGeneralSettings:
            saved = await self._repo.save_general(replace(current, company_logo_key=key))
            await self._repo.append_audit(
                AdminSettingsAuditEntry.by_actor(
                    actor,
                    settings_domain="general",
                    summary=f"Company logo uploaded by {actor.username}.",
                )
            )
            return saved

        saved = await replace_stored_asset(
            self._storage,
            self._uow,
            key=key,
            old_key=current.company_logo_key,
            data=data,
            save=save,
            label="company logo",
        )

        log.info("Uploaded a new company logo.")
        return GeneralSettingsMapper.general_to_result(saved)
