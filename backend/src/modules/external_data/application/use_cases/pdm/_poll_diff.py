"""The per-file diff of the PDM poll: reading the stored snapshots of a
walked folder and deciding, for each file the walk found, whether it is new,
changed, reappeared, in a folder kind conflict or unchanged. The behaviour is
documented in docs/reference/pdm-sync.md sections 3.3, 3.6 and 3.8.

An unchanged file costs no database write. A changed one is queued for
ingest with its snapshot row marked pending. PollFileDiff is a base class of
PollPdmVault and reads the dependencies its constructor sets.
"""

from datetime import datetime

from src.modules.catalogue.domain.value_objects.pdm_sync_state import PdmSyncState
from src.modules.catalogue.ports.outbound.cad_item_store_port import IBoughtItemCadStore
from src.modules.catalogue.ports.outbound.cad_item_store_port import IMadeItemCadStore
from src.modules.external_data.application.services.pdm_item_link import set_item_pdm_sync_state
from src.modules.external_data.application.services.pdm_vault import sync_run_entry
from src.modules.external_data.application.use_cases.pdm._poll_run import PollRunLog
from src.modules.external_data.application.use_cases.pdm._poll_run import PollSummary
from src.modules.external_data.domain.entities.pdm_file_snapshot import PdmFileSnapshot
from src.modules.external_data.domain.entities.pdm_sync_run import PdmSyncRun
from src.modules.external_data.domain.value_objects.pdm_file_sync_state import PdmFileSyncState
from src.modules.external_data.domain.value_objects.pdm_watched_folder import PdmWatchedFolder
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmObjectInfo
from src.modules.external_data.ports.outbound.repositories.pdm_file_snapshot_repository import (
    IPdmFileSnapshotRepository,
)
from src.shared_kernel.domain.services.clock import now_utc


class PollFileDiff(PollRunLog):
    """The per-file diff; PollPdmVault sets every attribute declared here."""

    _snapshots: IPdmFileSnapshotRepository
    _made_items: IMadeItemCadStore
    _bought_items: IBoughtItemCadStore

    async def _load_snapshots(
        self,
        vault_id: str,
        folder_ids: list[int],
        file_ids: list[int],
        loaded: dict[int, PdmFileSnapshot],
    ) -> None:
        """Adds the stored rows of one walked watched folder to `loaded`: every
        row whose parent folder was visited, which the diff and the missing
        sweep both need, plus the rows of files found here that were stored
        under another folder, which have moved in. Rows already loaded keep
        this run's own changes."""
        for row in await self._snapshots.get_by_parent_folder_ids(vault_id, folder_ids):
            loaded.setdefault(row.file_id, row)
        moved_in = [file_id for file_id in file_ids if file_id not in loaded]
        if moved_in:
            for row in await self._snapshots.get_by_file_ids(vault_id, moved_in):
                loaded.setdefault(row.file_id, row)

    @staticmethod
    def _folder_link_conflict_message(existing: PdmFileSnapshot, folder_kind: str) -> str | None:
        """An explicit made/bought folder disagreeing with an already
        linked file's own resolved kind is parked as a conflict
        (docs/reference/pdm-sync.md section 3.8). A `by_kind` folder never triggers this:
        its kind is deferred to the datacard variable instead
        (resolve_file_kind), unrelated to this check. An unlinked
        snapshot (item_id is None) is never a conflict here either. The
        caller adopts the folder's kind instead of flagging it."""
        if folder_kind == "by_kind":
            return None
        if existing.item_id is None:
            return None
        if existing.kind is None or existing.kind == folder_kind:
            return None
        return f"linked as {existing.kind}, now in a {folder_kind} folder"

    @staticmethod
    def _apply_scan_fields(snapshot: PdmFileSnapshot, obj: PdmObjectInfo, now: datetime) -> None:
        snapshot.name = obj.name
        snapshot.path = obj.path
        snapshot.parent_folder_id = obj.parent_folder_id
        snapshot.version = obj.version
        snapshot.state_id = obj.state_id
        snapshot.state = obj.state
        snapshot.modified_at = obj.modified_at
        snapshot.last_seen_at = now

    async def _process_seen_file(
        self,
        *,
        vault_id: str,
        obj: PdmObjectInfo,
        folder: PdmWatchedFolder,
        existing: PdmFileSnapshot | None,
        force: bool,
        summary: PollSummary,
        run: PdmSyncRun,
        snapshots_to_write: list[PdmFileSnapshot],
        to_ingest: list[tuple[PdmObjectInfo, str | None]],
    ) -> PdmFileSnapshot:
        """Diffs one file the walk found against its (possibly absent)
        snapshot row. A write is queued only when something actually
        changed: an unchanged file is returned untouched, with no database
        call and no ingest. Returns the snapshot now tracked for
        `obj.id`, for the caller's vault-wide in-memory map."""
        now = now_utc()

        if existing is None:
            snapshot = self._new_snapshot(vault_id, obj, folder, now)
            snapshots_to_write.append(snapshot)
            summary.changed += 1
            to_ingest.append((obj, snapshot.kind))
            return snapshot

        conflict_message = self._folder_link_conflict_message(existing, folder.kind)
        if conflict_message is not None:
            await self._park_folder_conflict(
                vault_id, obj, existing, conflict_message, now, summary, run, snapshots_to_write
            )
            return existing

        kind_adopted = self._adopt_folder_kind(existing, folder)

        if not force and not kind_adopted and self._reappeared_unchanged(existing, obj):
            await self._mark_reappeared(
                vault_id, obj, existing, now, summary, run, snapshots_to_write
            )
            return existing

        if not (kind_adopted or force or self._differs_from_snapshot(existing, obj)):
            return existing

        self._apply_scan_fields(existing, obj, now)
        self._mark_queued(existing)
        snapshots_to_write.append(existing)
        summary.changed += 1
        to_ingest.append((obj, existing.kind))
        return existing

    @staticmethod
    def _mark_queued(snapshot: PdmFileSnapshot) -> None:
        """Marks a changed file pending before its new version is stored, so
        a run that dies before ingesting it leaves a row the next run still
        treats as changed, instead of one that already looks up to date."""
        snapshot.sync_state = PdmFileSyncState.PENDING
        snapshot.last_error = None

    @staticmethod
    def _new_snapshot(
        vault_id: str, obj: PdmObjectInfo, folder: PdmWatchedFolder, now: datetime
    ) -> PdmFileSnapshot:
        """A pending snapshot for a file seen for the first time. A by_kind folder leaves the
        kind open until the datacard is read."""
        return PdmFileSnapshot(
            id=0,
            vault_id=vault_id,
            file_id=obj.id,
            kind=None if folder.kind == "by_kind" else folder.kind,
            name=obj.name,
            path=obj.path,
            parent_folder_id=obj.parent_folder_id,
            version=obj.version,
            state_id=obj.state_id,
            state=obj.state,
            modified_at=obj.modified_at,
            first_seen_at=now,
            last_seen_at=now,
            last_ingested_version=None,
            sync_state=PdmFileSyncState.PENDING,
            last_error=None,
            part_number=None,
            revision=None,
            item_id=None,
            parked_payload=None,
        )

    async def _park_folder_conflict(
        self,
        vault_id: str,
        obj: PdmObjectInfo,
        existing: PdmFileSnapshot,
        conflict_message: str,
        now: datetime,
        summary: PollSummary,
        run: PdmSyncRun,
        snapshots_to_write: list[PdmFileSnapshot],
    ) -> None:
        existing.sync_state = PdmFileSyncState.CONFLICT
        existing.last_error = conflict_message
        self._apply_scan_fields(existing, obj, now)
        snapshots_to_write.append(existing)
        summary.changed += 1
        summary.conflicts += 1
        entry = sync_run_entry(
            run.id, vault_id, obj, existing.kind, "conflict", existing.item_id, conflict_message
        )
        await self._runs.add_entries(run.id, [entry])

    @staticmethod
    def _adopt_folder_kind(existing: PdmFileSnapshot, folder: PdmWatchedFolder) -> bool:
        """An unlinked file that moved into a different explicit folder since it was last seen
        simply takes that folder's kind, since there is nothing to protect yet. Returns whether
        the kind was adopted."""
        if (
            folder.kind != "by_kind"
            and existing.kind is not None
            and existing.kind != folder.kind
            and existing.item_id is None
        ):
            existing.kind = folder.kind
            return True
        return False

    @staticmethod
    def _reappeared_unchanged(existing: PdmFileSnapshot, obj: PdmObjectInfo) -> bool:
        """A linked file that went missing and came back at the same version and state needs
        no ingest, since nothing about it could have changed while it was unreachable."""
        return (
            existing.sync_state == PdmFileSyncState.MISSING.value
            and existing.item_id is not None
            and existing.version == obj.version
            and existing.state_id == obj.state_id
        )

    async def _mark_reappeared(
        self,
        vault_id: str,
        obj: PdmObjectInfo,
        existing: PdmFileSnapshot,
        now: datetime,
        summary: PollSummary,
        run: PdmSyncRun,
        snapshots_to_write: list[PdmFileSnapshot],
    ) -> None:
        assert existing.item_id is not None  # guaranteed by _reappeared_unchanged
        existing.sync_state = PdmFileSyncState.INGESTED
        existing.last_error = None
        self._apply_scan_fields(existing, obj, now)
        snapshots_to_write.append(existing)
        summary.changed += 1
        summary.ingested += 1
        await self._set_item_synced(existing.kind, existing.item_id)
        message = "file reappeared with unchanged version and state; item marked synced"
        entry = sync_run_entry(
            run.id, vault_id, obj, existing.kind, "status", existing.item_id, message
        )
        await self._runs.add_entries(run.id, [entry])

    @staticmethod
    def _differs_from_snapshot(existing: PdmFileSnapshot, obj: PdmObjectInfo) -> bool:
        """True when the version or workflow state moved, or the snapshot never converged.
        A `missing` row that reaches this check did not take the reappeared-unchanged shortcut
        (unlinked, or forced), so it is always worth a fresh ingest attempt."""
        return (
            existing.version != obj.version
            or existing.state_id != obj.state_id
            or existing.sync_state
            in (
                PdmFileSyncState.PENDING.value,
                PdmFileSyncState.ERROR.value,
                PdmFileSyncState.MISSING.value,
            )
        )

    # ── Item link status ─────────────────────────────────────────────

    async def _set_item_missing(self, kind: str, item_id: int) -> None:
        await set_item_pdm_sync_state(
            self._made_items, self._bought_items, kind, item_id, PdmSyncState.MISSING
        )

    async def _set_item_synced(self, kind: str | None, item_id: int) -> None:
        assert kind is not None  # item_id is only ever set on a kind-resolved row
        await set_item_pdm_sync_state(
            self._made_items, self._bought_items, kind, item_id, PdmSyncState.SYNCED
        )
