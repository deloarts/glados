"""
Copies every object from the current storage provider to the target provider,
then atomically commits the target settings to the database.
If any file copy fails the DB is not updated and the original settings are preserved.
An optional progress callback hears about each object before it is copied, which
the streaming endpoint turns into live progress for the migration dialog.
"""

from src.modules.platform.application.dto.admin_settings_dto.storage import StorageMigrationProgress
from src.modules.platform.application.dto.admin_settings_dto.storage import (
    StorageMigrationProgressCallback,
)
from src.modules.platform.application.dto.admin_settings_dto.storage import StorageMigrationResult
from src.modules.platform.application.dto.admin_settings_dto.storage import (
    UpdateStorageSettingsCommand,
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
from src.modules.platform.ports.outbound.storage_port import IStorageAdapterFactory
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork

_VALID_PROVIDERS = {"local", "seaweedfs", "s3", "azure"}


class MigrateStorage:
    def __init__(
        self,
        repo: IPlatformSettingsRepository,
        storage_factory: IStorageAdapterFactory,
        uow: IUnitOfWork,
    ) -> None:
        self._repo = repo
        self._storage_factory = storage_factory
        self._uow = uow

    async def execute(
        self,
        actor: User,
        cmd: UpdateStorageSettingsCommand,
        progress: StorageMigrationProgressCallback | None = None,
    ) -> StorageMigrationResult:
        SettingsRules.assert_can_write(actor)

        if cmd.provider not in _VALID_PROVIDERS:
            raise StorageProviderInvalidError(
                f"Invalid storage provider {cmd.provider!r}. "
                f"Must be one of: {', '.join(sorted(_VALID_PROVIDERS))}."
            )

        current = await self._repo.get_storage()
        secret_key = cmd.secret_key if cmd.secret_key is not None else current.secret_key

        target = AdminStorageSettings(
            id=current.id,
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
        )

        source_adapter = self._storage_factory(current)
        target_adapter = self._storage_factory(target)

        # The copy loop can run for minutes and touches only storage. Ending
        # the read transaction first keeps the connection out of an idle
        # transaction the server would terminate.
        await self._uow.commit()
        keys = await source_adapter.list_keys()
        migrated = 0
        errors: list[str] = []

        for position, key in enumerate(keys, start=1):
            if progress is not None:
                progress(StorageMigrationProgress(current=position, total=len(keys), key=key))
            try:
                data, content_type = await source_adapter.download(key)
                await target_adapter.upload(key, data, content_type)
                migrated += 1
            except Exception as exc:
                errors.append(f"{key}: {exc}")

        committed = False
        if not errors:
            await self._repo.save_storage(target)
            await self._repo.append_audit(
                AdminSettingsAuditEntry.by_actor(
                    actor,
                    settings_domain="storage",
                    summary=(
                        f"Storage migrated by {actor.username}: "
                        f"{current.provider} → {target.provider} "
                        f"({migrated} object(s) copied)."
                    ),
                )
            )
            await self._uow.commit()
            committed = True
            log.info(
                "Storage migration completed: %s → %s (%d object(s)).",
                current.provider,
                target.provider,
                migrated,
            )
        else:
            log.warning(
                "Storage migration failed: %d/%d object(s) errored. DB unchanged.",
                len(errors),
                len(keys),
            )

        return StorageMigrationResult(
            migrated_count=migrated,
            failed_count=len(errors),
            errors=errors,
            committed=committed,
        )
