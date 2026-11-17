"""
secret_key field: None means "keep existing". A non-None value replaces the stored secret.
"""

from src.modules.platform.application.dto.admin_settings_dto.storage import (
    AdminStorageSettingsResult,
)
from src.modules.platform.application.dto.admin_settings_dto.storage import (
    UpdateStorageSettingsCommand,
)
from src.modules.platform.application.mappers.admin_settings_mapper.storage import (
    StorageSettingsMapper,
)
from src.modules.platform.domain.entities.admin_settings.audit import AdminSettingsAuditEntry
from src.modules.platform.domain.entities.admin_settings.storage import AdminStorageSettings
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import StorageProviderInvalidError
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork

_VALID_PROVIDERS = {"local", "seaweedfs", "s3", "azure"}


class UpdateStorageSettings:
    def __init__(self, repo: IPlatformSettingsRepository, *, uow: IUnitOfWork) -> None:
        self._repo = repo
        self._uow = uow

    async def execute(
        self, actor: User, cmd: UpdateStorageSettingsCommand
    ) -> AdminStorageSettingsResult:
        SettingsRules.assert_can_write(actor)

        if cmd.provider not in _VALID_PROVIDERS:
            raise StorageProviderInvalidError(
                f"Invalid storage provider {cmd.provider!r}. "
                f"Must be one of: {', '.join(sorted(_VALID_PROVIDERS))}."
            )

        current = await self._repo.get_storage()
        secret_key = cmd.secret_key if cmd.secret_key is not None else current.secret_key

        settings = AdminStorageSettings(
            id=1,
            provider=cmd.provider,
            enabled=cmd.enabled,
            endpoint_url=cmd.endpoint_url,
            public_endpoint_url=cmd.public_endpoint_url,
            bucket_name=cmd.bucket_name,
            access_key=cmd.access_key,
            secret_key=secret_key,
            region=cmd.region,
            use_ssl=cmd.use_ssl,
            backup_enabled=cmd.backup_enabled,
            backup_path=cmd.backup_path,
            backup_cron=cmd.backup_cron,
            backup_retention_count=cmd.backup_retention_count,
            disk_warning_percent=cmd.disk_warning_percent,
        )
        saved = await self._repo.save_storage(settings)

        await self._repo.append_audit(
            AdminSettingsAuditEntry.by_actor(
                actor,
                settings_domain="storage",
                summary=f"Storage settings updated by {actor.username} (provider={cmd.provider}).",
            )
        )
        await self._uow.commit()

        log.info(f"Updated storage settings (provider={cmd.provider}).")
        return StorageSettingsMapper.storage_to_result(saved)
