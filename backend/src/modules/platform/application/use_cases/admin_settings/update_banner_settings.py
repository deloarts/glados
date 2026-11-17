"""Update the system-wide announcement banner, audit the change, and track whether it
was enabled, disabled, or modified."""

from src.modules.platform.application.dto.admin_settings_dto.banner import AdminBannerSettingsResult
from src.modules.platform.application.dto.admin_settings_dto.banner import (
    UpdateBannerSettingsCommand,
)
from src.modules.platform.application.mappers.admin_settings_mapper.banner import (
    BannerSettingsMapper,
)
from src.modules.platform.domain.entities.admin_settings.audit import AdminSettingsAuditEntry
from src.modules.platform.domain.entities.admin_settings.banner import AdminBannerSettings
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc


class UpdateBannerSettings:
    def __init__(self, repo: IPlatformSettingsRepository, *, uow: IUnitOfWork) -> None:
        self._repo = repo
        self._uow = uow

    async def execute(
        self, actor: User, cmd: UpdateBannerSettingsCommand
    ) -> AdminBannerSettingsResult:
        SettingsRules.assert_can_write(actor)

        # A full replace (like maintenance), so the previous state is read
        # first purely to pick the right verb for the audit summary: the
        # save below always writes every field regardless of what changed.
        previous = await self._repo.get_banner()
        if not previous.enabled and cmd.enabled:
            action = "enabled"
        elif previous.enabled and not cmd.enabled:
            action = "disabled"
        else:
            action = "updated"

        settings = AdminBannerSettings(
            id=1,
            enabled=cmd.enabled,
            text=cmd.text,
            severity=cmd.severity,
            shows_from=cmd.shows_from,
            shows_until=cmd.shows_until,
            dismissable=cmd.dismissable,
            updated_at=now_utc(),
        )
        saved = await self._repo.save_banner(settings)

        await self._repo.append_audit(
            AdminSettingsAuditEntry.by_actor(
                actor,
                settings_domain="banner",
                summary=f"Banner {action} by {actor.username}.",
            )
        )
        await self._uow.commit()

        log.info(f"{action.capitalize()} the banner.")
        return BannerSettingsMapper.banner_to_result(saved)
