"""Enable or disable optional system features, preserving unchanged settings to avoid
unexpected defaults on partial updates."""

from src.modules.platform.application.dto.admin_settings_dto.features import (
    AdminFeatureSettingsResult,
)
from src.modules.platform.application.dto.admin_settings_dto.features import (
    UpdateFeatureSettingsCommand,
)
from src.modules.platform.application.mappers.admin_settings_mapper.features import (
    FeatureSettingsMapper,
)
from src.modules.platform.domain.entities.admin_settings.audit import AdminSettingsAuditEntry
from src.modules.platform.domain.entities.admin_settings.features import AdminFeatureSettings
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class UpdateFeatureSettings:
    def __init__(self, repo: IPlatformSettingsRepository, *, uow: IUnitOfWork) -> None:
        self._repo = repo
        self._uow = uow

    async def execute(
        self, actor: User, cmd: UpdateFeatureSettingsCommand
    ) -> AdminFeatureSettingsResult:
        SettingsRules.assert_can_write(actor)

        # Partial: the admin tab only offers the flags something enforces, so
        # an omitted field must keep its stored value rather than snap back to
        # a default the admin never saw.
        current = await self._repo.get_features()

        def pick(new: bool | None, existing: bool) -> bool:
            return existing if new is None else new

        settings = AdminFeatureSettings(
            id=1,
            enable_email_notifications=pick(
                cmd.enable_email_notifications, current.enable_email_notifications
            ),
            enable_production_planning=pick(
                cmd.enable_production_planning, current.enable_production_planning
            ),
            allow_private_webhooks=pick(cmd.allow_private_webhooks, current.allow_private_webhooks),
            enable_calculations=pick(cmd.enable_calculations, current.enable_calculations),
            enable_checklists=pick(cmd.enable_checklists, current.enable_checklists),
            enable_devices=pick(cmd.enable_devices, current.enable_devices),
            enable_sequences=pick(cmd.enable_sequences, current.enable_sequences),
            enable_todos=pick(cmd.enable_todos, current.enable_todos),
        )
        saved = await self._repo.save_features(settings)

        await self._repo.append_audit(
            AdminSettingsAuditEntry.by_actor(
                actor,
                settings_domain="features",
                summary=f"Feature flags updated by {actor.username}.",
            )
        )
        await self._uow.commit()

        log.info("Updated feature settings.")
        return FeatureSettingsMapper.features_to_result(saved)
