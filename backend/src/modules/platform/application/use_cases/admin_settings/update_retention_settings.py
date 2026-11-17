"""Configure data retention policies for logs, audit entries, soft-deleted
records and meetings, validate non-negative days, and audit the change. A
command without the meeting period keeps the stored one."""

from src.modules.platform.application.dto.admin_settings_dto.retention import (
    AdminRetentionSettingsResult,
)
from src.modules.platform.application.dto.admin_settings_dto.retention import (
    UpdateRetentionSettingsCommand,
)
from src.modules.platform.application.mappers.admin_settings_mapper.retention import (
    RetentionSettingsMapper,
)
from src.modules.platform.domain.entities.admin_settings.audit import AdminSettingsAuditEntry
from src.modules.platform.domain.entities.admin_settings.retention import AdminRetentionSettings
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class UpdateRetentionSettings:
    def __init__(self, repo: IPlatformSettingsRepository, *, uow: IUnitOfWork) -> None:
        self._repo = repo
        self._uow = uow

    async def execute(
        self, actor: User, cmd: UpdateRetentionSettingsCommand
    ) -> AdminRetentionSettingsResult:
        SettingsRules.assert_can_write(actor)

        if (
            cmd.log_retention_days < 0
            or cmd.audit_retention_days < 0
            or cmd.soft_delete_cleanup_days < 0
            or (cmd.meeting_retention_days is not None and cmd.meeting_retention_days < 0)
        ):
            raise ValueError("Retention days must be >= 0 (0 = keep forever / never purge).")

        meeting_retention_days = (
            cmd.meeting_retention_days
            if cmd.meeting_retention_days is not None
            else (await self._repo.get_retention()).meeting_retention_days
        )
        settings = AdminRetentionSettings(
            id=1,
            log_retention_days=cmd.log_retention_days,
            audit_retention_days=cmd.audit_retention_days,
            soft_delete_cleanup_days=cmd.soft_delete_cleanup_days,
            meeting_retention_days=meeting_retention_days,
        )
        saved = await self._repo.save_retention(settings)

        await self._repo.append_audit(
            AdminSettingsAuditEntry.by_actor(
                actor,
                settings_domain="retention",
                summary=f"Retention settings updated by {actor.username}.",
            )
        )
        await self._uow.commit()

        log.info("Updated retention settings.")
        return RetentionSettingsMapper.retention_to_result(saved)
