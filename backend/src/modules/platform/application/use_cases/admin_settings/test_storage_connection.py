"""
Verify connectivity to a storage backend using the supplied (not-yet-saved)
settings. Requires write:settings.
"""

from src.modules.platform.application.dto.admin_settings_dto.storage import (
    UpdateStorageSettingsCommand,
)
from src.modules.platform.domain.entities.admin_settings.storage import AdminStorageSettings
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import StorageConnectionError
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.storage_port import IStorageAdapterFactory


class TestStorageConnection:
    def __init__(
        self, repo: IPlatformSettingsRepository, storage_factory: IStorageAdapterFactory
    ) -> None:
        self._repo = repo
        self._storage_factory = storage_factory

    async def execute(self, actor: User, cmd: UpdateStorageSettingsCommand) -> None:
        SettingsRules.assert_can_write(actor)

        current = await self._repo.get_storage()
        secret_key = cmd.secret_key if cmd.secret_key is not None else current.secret_key

        target = AdminStorageSettings(
            id=current.id,
            provider=cmd.provider,
            enabled=True,
            endpoint_url=cmd.endpoint_url,
            public_endpoint_url=cmd.public_endpoint_url,
            bucket_name=cmd.bucket_name,
            access_key=cmd.access_key,
            secret_key=secret_key,
            region=cmd.region,
            use_ssl=cmd.use_ssl,
            backup_enabled=False,
            backup_path=None,
            backup_cron=None,
            backup_retention_count=7,
        )

        # Bad/missing config (e.g. no bucket_name) raises StorageMigrationError from
        # the factory itself, already a DomainError mapped to 400, let it propagate.
        adapter = self._storage_factory(target)

        try:
            await adapter.test_connection()
        except Exception as exc:
            raise StorageConnectionError(str(exc)) from exc
