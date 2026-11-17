"""
Remove the login screen's background video from storage and clear the key.
"""

from dataclasses import replace

from src.modules.platform.application.dto.admin_settings_dto.branding import (
    AdminBrandingSettingsResult,
)
from src.modules.platform.application.mappers.admin_settings_mapper.branding import (
    BrandingSettingsMapper,
)
from src.modules.platform.application.services.storage_asset import (
    delete_storage_object_best_effort,
)
from src.modules.platform.domain.entities.admin_settings.audit import AdminSettingsAuditEntry
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.storage_port import IStoragePort
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class DeleteLoginBackgroundVideo:
    def __init__(
        self, repo: IPlatformSettingsRepository, storage: IStoragePort | None, *, uow: IUnitOfWork
    ) -> None:
        self._repo = repo
        self._uow = uow
        self._storage = storage

    async def execute(self, actor: User) -> AdminBrandingSettingsResult:
        SettingsRules.assert_can_write(actor)

        current = await self._repo.get_branding()

        if current.login_background_video_key and self._storage is not None:
            await delete_storage_object_best_effort(
                self._storage,
                current.login_background_video_key,
                context="removing login background video",
            )

        saved = await self._repo.save_branding(replace(current, login_background_video_key=None))

        await self._repo.append_audit(
            AdminSettingsAuditEntry.by_actor(
                actor,
                settings_domain="branding",
                summary=f"Login background video removed by {actor.username}.",
            )
        )
        await self._uow.commit()

        log.info("Removed the login background video.")
        return BrandingSettingsMapper.branding_to_result(saved)
