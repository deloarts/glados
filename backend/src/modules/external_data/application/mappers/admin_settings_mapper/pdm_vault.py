"""
Maps the PDM file snapshot, sync run and reconciliation finding entities shown
on the admin settings page to result DTOs.
"""

from src.modules.external_data.application.dto.pdm_dto import PdmFileSnapshotResult
from src.modules.external_data.application.dto.pdm_dto import PdmReconciliationFindingResult
from src.modules.external_data.application.dto.pdm_dto import PdmSyncRunEntryResult
from src.modules.external_data.application.dto.pdm_dto import PdmSyncRunResult
from src.modules.external_data.domain.entities.pdm_file_snapshot import PdmFileSnapshot
from src.modules.external_data.domain.entities.pdm_reconciliation_finding import (
    PdmReconciliationFinding,
)
from src.modules.external_data.domain.entities.pdm_sync_run import PdmSyncRun
from src.modules.external_data.domain.entities.pdm_sync_run import PdmSyncRunEntry


class PdmVaultMapper:
    @staticmethod
    def pdm_file_snapshot_to_result(
        e: PdmFileSnapshot, item_kind: str | None
    ) -> PdmFileSnapshotResult:
        return PdmFileSnapshotResult(
            id=e.id,
            public_id=e.public_id,
            vault_id=e.vault_id,
            file_id=e.file_id,
            kind=e.kind,
            name=e.name,
            path=e.path,
            parent_folder_id=e.parent_folder_id,
            version=e.version,
            state_id=e.state_id,
            state=e.state,
            modified_at=e.modified_at,
            first_seen_at=e.first_seen_at,
            last_seen_at=e.last_seen_at,
            last_ingested_version=e.last_ingested_version,
            sync_state=e.sync_state,
            last_error=e.last_error,
            part_number=e.part_number,
            revision=e.revision,
            item_id=e.item_id,
            item_kind=item_kind,
            has_parked_payload=e.parked_payload is not None,
        )

    @staticmethod
    def pdm_sync_run_to_result(e: PdmSyncRun) -> PdmSyncRunResult:
        return PdmSyncRunResult(
            id=e.id,
            public_id=e.public_id,
            started_at=e.started_at,
            finished_at=e.finished_at,
            trigger=e.trigger,
            files_seen=e.files_seen,
            changed=e.changed,
            ingested=e.ingested,
            skipped=e.skipped,
            conflicts=e.conflicts,
            errors=e.errors,
            missing=e.missing,
            error=e.error,
            summary=e.summary,
            folders_walked=e.folders_walked,
            folders_skipped_cold=e.folders_skipped_cold,
            phase=e.phase,
            current_path=e.current_path,
            files_queued=e.files_queued,
            files_processed=e.files_processed,
            progress_at=e.progress_at,
        )

    @staticmethod
    def pdm_sync_run_entry_to_result(e: PdmSyncRunEntry) -> PdmSyncRunEntryResult:
        return PdmSyncRunEntryResult(
            id=e.id,
            public_id=e.public_id,
            run_id=e.run_id,
            vault_id=e.vault_id,
            file_id=e.file_id,
            name=e.name,
            path=e.path,
            kind=e.kind,
            action=e.action,
            item_id=e.item_id,
            message=e.message,
            created_at=e.created_at,
        )

    @staticmethod
    def pdm_reconciliation_finding_to_result(
        e: PdmReconciliationFinding,
    ) -> PdmReconciliationFindingResult:
        return PdmReconciliationFindingResult(
            id=e.id,
            public_id=e.public_id,
            run_id=e.run_id,
            category=e.category,
            severity=e.severity,
            kind=e.kind,
            item_id=e.item_id,
            file_id=e.file_id,
            part_number=e.part_number,
            revision=e.revision,
            message=e.message,
            count=e.count,
            created_at=e.created_at,
        )
