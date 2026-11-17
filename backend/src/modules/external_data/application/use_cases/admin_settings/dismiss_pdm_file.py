"""
Backs the admin "PDM files" pending list's Dismiss action (POST
/admin/settings/pdm/files/{id}/dismiss): drops a row's parked ingest
payload and marks it skipped, without contacting PDM. For a conflict the
admin has resolved by hand in PDM or decided not to sync at all, the row
stays as a record, but the next poll's parked-conflict retry
(docs/reference/field-ownership.md section 5) will no longer pick it up, since there is
nothing parked left to retry.
"""

from src.modules.external_data.application.dto.pdm_dto import PdmFileSnapshotResult
from src.modules.external_data.application.mappers.admin_settings_mapper.pdm_vault import (
    PdmVaultMapper,
)
from src.modules.external_data.application.services.pdm_skip_reasons import dismissed_message
from src.modules.external_data.application.services.pdm_snapshot_item_kind import (
    snapshot_item_kinds,
)
from src.modules.external_data.domain.errors import AdminSettingsNotFoundError
from src.modules.external_data.domain.value_objects.pdm_file_sync_state import PdmFileSyncState
from src.modules.external_data.ports.outbound.external_data_settings_repository import (
    IExternalDataSettingsRepository,
)
from src.modules.external_data.ports.outbound.repositories.pdm_document_link_repository import (
    IPdmDocumentLinkRepository,
)
from src.modules.external_data.ports.outbound.repositories.pdm_file_snapshot_repository import (
    IPdmFileSnapshotRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.admin_settings.audit import AdminSettingsAuditEntry
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class DismissPdmFile:
    def __init__(
        self,
        snapshot_repo: IPdmFileSnapshotRepository,
        settings_repo: IExternalDataSettingsRepository,
        *,
        uow: IUnitOfWork,
        document_link_repo: IPdmDocumentLinkRepository | None = None,
    ) -> None:
        self._uow = uow
        self._snapshots = snapshot_repo
        self._settings = settings_repo
        self._links = document_link_repo

    async def execute(self, actor: User, snapshot_id: int) -> PdmFileSnapshotResult:
        SettingsRules.assert_can_write(actor)

        snapshot = found_or_raise(
            await self._snapshots.get_by_id(snapshot_id),
            AdminSettingsNotFoundError,
            f"PDM file snapshot #{snapshot_id} not found.",
        )

        snapshot.sync_state = PdmFileSyncState.SKIPPED
        snapshot.parked_payload = None
        snapshot.last_error = dismissed_message(actor.username)

        saved = await self._snapshots.save(snapshot)

        await self._settings.append_audit(
            AdminSettingsAuditEntry.by_actor(
                actor,
                settings_domain="pdm",
                summary=(
                    f"PDM file dismissed by {actor.username}: "
                    f"{snapshot.path} (file #{snapshot.file_id})."
                ),
            )
        )
        await self._uow.commit()

        log.info(f"Dismissed PDM file snapshot #{snapshot.id} (file #{snapshot.file_id}).")
        # The frontend swaps the returned row into its list, so it carries
        # the same item catalogue the list itself would show.
        item_kinds = await snapshot_item_kinds([saved], self._links)
        return PdmVaultMapper.pdm_file_snapshot_to_result(saved, item_kinds[saved.id])
