"""
Backs the admin "PDM files" pending list's Retry action (POST
/admin/settings/pdm/files/{id}/retry): resets one snapshot row to pending
and asks the pdm_sync worker to refresh it, the same
PdmFileChangeRequested path the vault add-in's trigger endpoint and the
poller's per-file refresh use. Glados re-reads the file from the vault
itself; nothing about the retry is trusted from the request beyond which
row to retry. Publishes with source="retry" so the pdm_sync worker records
its resulting sync run under PdmSyncTrigger.RETRY rather than FILE_TRIGGER.
"""

from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.entities.pdm_file_snapshot import PdmFileSnapshot
from src.modules.external_data.domain.errors import AdminSettingsNotFoundError
from src.modules.external_data.domain.events.pdm_events import PdmFileChangeRequested
from src.modules.external_data.domain.value_objects.pdm_file_sync_state import PdmFileSyncState
from src.modules.external_data.ports.outbound.external_data_settings_repository import (
    IExternalDataSettingsRepository,
)
from src.modules.external_data.ports.outbound.repositories.pdm_file_snapshot_repository import (
    IPdmFileSnapshotRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.admin_settings.audit import AdminSettingsAuditEntry
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class RetryPdmFile:
    def __init__(
        self,
        snapshot_repo: IPdmFileSnapshotRepository,
        settings_repo: IExternalDataSettingsRepository,
        *,
        event_bus: IEventBus,
        uow: IUnitOfWork,
    ) -> None:
        self._uow = uow
        self._snapshots = snapshot_repo
        self._settings = settings_repo
        self._bus = event_bus

    async def execute(self, actor: User, snapshot_id: int) -> None:
        SettingsRules.assert_can_write(actor)

        snapshot = found_or_raise(
            await self._snapshots.get_by_id(snapshot_id),
            AdminSettingsNotFoundError,
            f"PDM file snapshot #{snapshot_id} not found.",
        )
        await self._retry(actor, snapshot, await self._settings.get_pdm())

    async def execute_for_file(self, actor: User, file_id: int) -> None:
        """The same retry, addressed by the vault file id a reconciliation
        finding carries rather than by the snapshot row id."""
        SettingsRules.assert_can_write(actor)

        settings = await self._settings.get_pdm()
        snapshot = found_or_raise(
            await self._snapshots.get_by_file(settings.vault_id, file_id),
            AdminSettingsNotFoundError,
            f"PDM file #{file_id} has no snapshot.",
        )
        await self._retry(actor, snapshot, settings)

    async def _retry(
        self, actor: User, snapshot: PdmFileSnapshot, settings: AdminPdmSettings
    ) -> None:
        snapshot.sync_state = PdmFileSyncState.PENDING
        snapshot.last_error = None

        # Staged into the caller's session before the unit of work below
        # commits it, per event_outbox.py's ordering rule for the
        # transactional bus: publish before commit, never after.
        await self._bus.publish(
            PdmFileChangeRequested(
                vault_name=settings.vault_name,
                file_id=snapshot.file_id,
                path=snapshot.path,
                version=None,
                requested_by_id=actor.id,
                source="retry",
                requested_by_name=actor.full_name,
            )
        )
        await self._snapshots.save(snapshot)

        await self._settings.append_audit(
            AdminSettingsAuditEntry.by_actor(
                actor,
                settings_domain="pdm",
                summary=(
                    f"PDM file retry requested by {actor.username} for "
                    f"{snapshot.path} (file #{snapshot.file_id})."
                ),
            )
        )
        await self._uow.commit()

        log.info(f"Requested a PDM retry for snapshot #{snapshot.id} (file #{snapshot.file_id}).")
