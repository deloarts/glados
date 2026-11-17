"""Update system branding settings (app name, description, footer text) and audit the
change."""

from src.modules.platform.application.dto.admin_settings_dto.branding import (
    AdminBrandingSettingsResult,
)
from src.modules.platform.application.dto.admin_settings_dto.branding import (
    UpdateBrandingSettingsCommand,
)
from src.modules.platform.application.mappers.admin_settings_mapper.branding import (
    BrandingSettingsMapper,
)
from src.modules.platform.domain.entities.admin_settings.audit import AdminSettingsAuditEntry
from src.modules.platform.domain.entities.admin_settings.branding import AdminBrandingSettings
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class UpdateBrandingSettings:
    def __init__(self, repo: IPlatformSettingsRepository, *, uow: IUnitOfWork) -> None:
        self._repo = repo
        self._uow = uow

    async def execute(
        self, actor: User, cmd: UpdateBrandingSettingsCommand
    ) -> AdminBrandingSettingsResult:
        SettingsRules.assert_can_write(actor)

        current = await self._repo.get_branding()
        settings = AdminBrandingSettings(
            id=1,
            app_name=cmd.app_name,
            app_description=cmd.app_description,
            footer_text=cmd.footer_text if cmd.footer_text is not None else current.footer_text,
            logo_url=current.logo_url,
            favicon_url=current.favicon_url,
            logo_key=current.logo_key,
            favicon_key=current.favicon_key,
            login_background_video_key=current.login_background_video_key,
        )
        saved = await self._repo.save_branding(settings)

        await self._repo.append_audit(
            AdminSettingsAuditEntry.by_actor(
                actor,
                settings_domain="branding",
                summary=f"Branding settings updated by {actor.username}.",
            )
        )
        await self._uow.commit()

        log.info("Updated branding settings.")
        return BrandingSettingsMapper.branding_to_result(saved)
