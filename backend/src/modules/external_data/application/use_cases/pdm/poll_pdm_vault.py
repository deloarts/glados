"""
The PDM baseline sync: once per configured interval, walks every enabled
watched folder's tree via `browse`, diffs what PDM reports against
pdm_file_snapshot, and re-ingests whatever changed. This makes the
integration self-healing after an outage or a missed trigger; the add-in
trigger is only a low-latency accelerator on top of it. The behaviour (folder
walk, diff, missing sweep, reappearance, conflicts and retries, cold-folder
cadence, run log) is documented in docs/reference/pdm-sync.md section 3, and
documents, thumbnails and the file type rule in section 11.

Two invariants shape the code. One failed browse must never read as
"everything under this folder is gone", so a failed watched root skips its
missing sweep and its cadence update. PDM calls always happen before the
matching database write, so a mid-scan PDM failure never leaves a
half-written batch. IngestPdmFile owns the item write; this use case only
decides which files to hand to it and keeps the snapshots, the run log and
the poll status up to date around that.

The parts live in sibling modules, each a base class of PollPdmVault: the
folder walk in _poll_walk.py, the per-file diff in _poll_diff.py, the
dispatch to ingest and document sync in _poll_dispatch.py, the missing
sweep, conflict retries and cadence update in _poll_reconcile.py, and the run
bookkeeping in _poll_run.py. This module keeps the constructor and the order
in which a run calls them.
"""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import datetime

from src.modules.catalogue.ports.outbound.cad_item_store_port import IBoughtItemCadStore
from src.modules.catalogue.ports.outbound.cad_item_store_port import IMadeItemCadStore
from src.modules.external_data.application.services.pdm_session import PdmSessionService
from src.modules.external_data.application.services.pdm_vault import resolve_and_store_vault_id
from src.modules.external_data.application.services.pdm_writeback import PdmWriteBack
from src.modules.external_data.application.use_cases.pdm._poll_dispatch import PollDispatch
from src.modules.external_data.application.use_cases.pdm._poll_reconcile import PollReconcile
from src.modules.external_data.application.use_cases.pdm._poll_run import _PHASE_FINISHING
from src.modules.external_data.application.use_cases.pdm._poll_run import _PHASE_WALKING
from src.modules.external_data.application.use_cases.pdm._poll_run import PollSummary
from src.modules.external_data.application.use_cases.pdm._poll_walk import _DOCUMENTS_FOLDER_KIND
from src.modules.external_data.application.use_cases.pdm._poll_walk import PollFolderWalk
from src.modules.external_data.application.use_cases.pdm.ingest_pdm_file import IngestPdmFile
from src.modules.external_data.application.use_cases.pdm.pdm_documents import PdmDocumentSync
from src.modules.external_data.application.use_cases.pdm.pdm_documents import PdmThumbnails
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.entities.pdm_file_snapshot import PdmFileSnapshot
from src.modules.external_data.domain.entities.pdm_folder_poll_state import PdmFolderPollState
from src.modules.external_data.domain.entities.pdm_sync_run import PdmSyncRun
from src.modules.external_data.domain.services.pdm_poll_cadence import folder_key
from src.modules.external_data.domain.value_objects.pdm_file_sync_state import PdmFileSyncState
from src.modules.external_data.domain.value_objects.pdm_sync_trigger import PdmSyncTrigger
from src.modules.external_data.domain.value_objects.pdm_watched_folder import PdmWatchedFolder
from src.modules.external_data.ports.outbound.external_data_settings_repository import (
    IExternalDataSettingsRepository,
)
from src.modules.external_data.ports.outbound.pdm_file_lock_port import IPdmFileLock
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmObjectInfo
from src.modules.external_data.ports.outbound.repositories.pdm_file_snapshot_repository import (
    IPdmFileSnapshotRepository,
)
from src.modules.external_data.ports.outbound.repositories.pdm_folder_poll_state_repository import (
    IPdmFolderPollStateRepository,
)
from src.modules.external_data.ports.outbound.repositories.pdm_sync_run_repository import (
    IPdmSyncRunRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc

__all__ = ["PollPdmVault", "PollSummary"]


class PollPdmVault(PollFolderWalk, PollReconcile):
    def __init__(
        self,
        session: PdmSessionService,
        admin_settings_repo: IExternalDataSettingsRepository,
        snapshot_repo: IPdmFileSnapshotRepository,
        made_item_repo: IMadeItemCadStore,
        bought_item_repo: IBoughtItemCadStore,
        ingest: IngestPdmFile,
        write_back: PdmWriteBack,
        document_sync: PdmDocumentSync,
        thumbnails: PdmThumbnails,
        run_repo: IPdmSyncRunRepository,
        folder_poll_state_repo: IPdmFolderPollStateRepository,
        uow: IUnitOfWork,
        worker_factory: Callable[[], AbstractAsyncContextManager["PollPdmVault"]] | None = None,
        file_lock: IPdmFileLock | None = None,
    ) -> None:
        self._worker_factory = worker_factory
        self._file_lock = file_lock
        self._session = session
        self._admin_settings = admin_settings_repo
        self._snapshots = snapshot_repo
        self._made_items = made_item_repo
        self._bought_items = bought_item_repo
        self._ingest = ingest
        self._write_back = write_back
        self._document_sync = document_sync
        self._thumbnails = thumbnails
        self._runs = run_repo
        self._folder_poll_states = folder_poll_state_repo
        self._uow = uow

    async def execute(self, trigger: PdmSyncTrigger = PdmSyncTrigger.SCHEDULED) -> PollSummary:
        """Walks every enabled watched folder and re-ingests whatever
        changed since the last run.

        A `MANUAL` trigger (an admin's "Synchronize with PDM" request)
        forces every file the walk finds to be treated as changed,
        bypassing the version/state_id/sync_state diff in
        `_process_seen_file`. This is what lets an admin force a full
        re-evaluation on demand, e.g. right after fixing a settings
        problem (a watched folder, a variable map, a state list) that
        `UpdatePdmSettings` itself did not already requeue. It also skips
        the "reappeared unchanged" shortcut, so a file coming back from
        `missing` on a manual run gets a full re-ingest rather than just
        being flipped back to `ingested`. A `SCHEDULED` trigger keeps the
        normal diff, since re-ingesting every watched file on every tick
        would be needless load."""
        started_at = now_utc()
        summary = PollSummary(
            files_seen=0,
            changed=0,
            ingested=0,
            skipped=0,
            conflicts=0,
            errors=0,
            missing=0,
            folders_walked=0,
            folders_skipped_cold=0,
            written_back=0,
            ignored_by_type=0,
            documents=0,
            document_errors=0,
            thumbnails=0,
        )
        run = await self._runs.start(
            PdmSyncRun(
                id=0,
                started_at=started_at,
                finished_at=None,
                trigger=trigger,
                files_seen=0,
                changed=0,
                ingested=0,
                skipped=0,
                conflicts=0,
                errors=0,
                missing=0,
                error=None,
                summary=None,
                folders_walked=0,
                folders_skipped_cold=0,
                phase=_PHASE_WALKING,
                progress_at=started_at,
            )
        )
        await self._uow.commit()
        try:
            await self._run(summary, run, trigger)
        except Exception as exc:
            # A failure mid-scan (vault unreachable, session rejected) must
            # still leave the admin UI a status to show, even though
            # nothing here swallows it. The scheduler tick logs it, and this
            # only makes sure last_poll_error/summary reflect what was
            # actually done before the failure.
            await self._admin_settings.save_pdm_poll_status(
                at=started_at, error=str(exc), summary=self._format_summary(summary)
            )
            await self._uow.commit()
            await self._finish_run(run, summary, error=str(exc))
            raise
        await self._finish_run(run, summary, error=None)
        return summary

    async def _run(self, summary: PollSummary, run: PdmSyncRun, trigger: PdmSyncTrigger) -> None:
        settings = await self._admin_settings.get_pdm()
        force_changed = trigger == PdmSyncTrigger.MANUAL
        vault_id = await resolve_and_store_vault_id(
            settings, self._session, self._admin_settings, self._uow
        )

        folders = [f for f in settings.watched_folders if f.enabled]
        # The snapshots this run has read so far, keyed by file id: each
        # watched folder's own rows are loaded once it has been walked (see
        # _load_snapshots), never the whole vault at once.
        all_snapshots: dict[int, PdmFileSnapshot] = {}
        seen_file_ids: set[int] = set()
        # Every folder id actually visited this run, mapped to the watched
        # folder it was found under: see _sweep_missing and this module's
        # docstring. A non-empty map after the walk is also this run's
        # "at least one folder was ok" signal.
        folder_membership: dict[int, PdmWatchedFolder] = {}

        # Cold-folder poll cadence (docs/reference/pdm-sync.md section 3.10):
        # only a SCHEDULED run ever consults or updates this state, MANUAL
        # and INITIAL always walk every enabled folder regardless.
        cadence_now = now_utc()
        cold_states = await self._folder_poll_states.get_all_for_vault(vault_id)
        walked_folder_keys: set[str] = set()
        changed_folder_keys: set[str] = set()

        for folder in folders:
            await self._process_folder(
                folder,
                vault_id=vault_id,
                run=run,
                summary=summary,
                settings=settings,
                trigger=trigger,
                cadence_now=cadence_now,
                cold_states=cold_states,
                all_snapshots=all_snapshots,
                seen_file_ids=seen_file_ids,
                folder_membership=folder_membership,
                force_changed=force_changed,
                walked_folder_keys=walked_folder_keys,
                changed_folder_keys=changed_folder_keys,
            )

        run.phase = _PHASE_FINISHING
        run.current_path = None
        await self._save_progress(run, summary, force=True)
        await self._sweep_missing(
            vault_id,
            folder_membership,
            all_snapshots,
            seen_file_ids,
            summary,
            run,
            changed_folder_keys,
        )
        await self._retry_conflicts(vault_id, folders, settings, summary, run, force_changed)

        if trigger == PdmSyncTrigger.SCHEDULED:
            await self._update_folder_cadence(
                vault_id, settings, walked_folder_keys, changed_folder_keys, cold_states
            )

        await self._admin_settings.save_pdm_poll_status(
            at=now_utc(), error=None, summary=self._format_summary(summary)
        )
        await self._uow.commit()

    async def _process_folder(
        self,
        folder: PdmWatchedFolder,
        *,
        vault_id: str,
        run: PdmSyncRun,
        summary: PollSummary,
        settings: AdminPdmSettings,
        trigger: PdmSyncTrigger,
        cadence_now: datetime,
        cold_states: dict[str, PdmFolderPollState],
        all_snapshots: dict[int, PdmFileSnapshot],
        seen_file_ids: set[int],
        folder_membership: dict[int, PdmWatchedFolder],
        force_changed: bool,
        walked_folder_keys: set[str],
        changed_folder_keys: set[str],
    ) -> None:
        """One watched folder's walk-and-diff pass for this run: skipped
        outright when cold-folder cadence says it is not due yet
        (SCHEDULED runs only), otherwise walked and dispatched to the
        documents diff or the made/bought per-file diff depending on its
        kind. Mutates `summary` and the run-wide tracking collections the
        caller owns."""
        key = folder_key(folder)
        if trigger == PdmSyncTrigger.SCHEDULED:
            state = cold_states.get(key)
            is_cold = (
                state is not None
                and state.next_due_at is not None
                and state.next_due_at > cadence_now
            )
            if is_cold:
                summary.folders_skipped_cold += 1
                return

        changed_before = summary.changed
        run.phase = _PHASE_WALKING
        run.current_path = folder.path
        await self._save_progress(run, summary, force=True)
        files, root_ok, walked = await self._walk_folder(
            vault_id, folder, run, summary, settings, folder_membership
        )
        summary.folders_walked += walked
        if not root_ok:
            return
        walked_folder_keys.add(key)
        await self._load_snapshots(
            vault_id,
            [fid for fid, owner in folder_membership.items() if owner is folder],
            [obj.id for obj in files],
            all_snapshots,
        )

        if folder.kind == _DOCUMENTS_FOLDER_KIND:
            await self._process_documents_folder(
                vault_id, folder, files, all_snapshots, seen_file_ids, force_changed, summary, run
            )
        else:
            await self._process_made_bought_folder(
                vault_id,
                folder,
                files,
                all_snapshots,
                seen_file_ids,
                force_changed,
                settings,
                summary,
                run,
            )

        if summary.changed > changed_before:
            changed_folder_keys.add(key)

    async def _process_made_bought_folder(
        self,
        vault_id: str,
        folder: PdmWatchedFolder,
        files: list[PdmObjectInfo],
        all_snapshots: dict[int, PdmFileSnapshot],
        seen_file_ids: set[int],
        force_changed: bool,
        settings: AdminPdmSettings,
        summary: PollSummary,
        run: PdmSyncRun,
    ) -> None:
        snapshots_to_write: list[PdmFileSnapshot] = []
        to_ingest: list[tuple[PdmObjectInfo, str | None]] = []
        for obj in files:
            seen_file_ids.add(obj.id)
            summary.files_seen += 1
            existing = all_snapshots.get(obj.id)
            snapshot = await self._process_seen_file(
                vault_id=vault_id,
                obj=obj,
                folder=folder,
                existing=existing,
                force=force_changed,
                summary=summary,
                run=run,
                snapshots_to_write=snapshots_to_write,
                to_ingest=to_ingest,
            )
            all_snapshots[obj.id] = snapshot

        if snapshots_to_write:
            await self._snapshots.upsert_many(snapshots_to_write)
            await self._uow.commit()

        async def ingest(poll: PollDispatch, item: tuple[PdmObjectInfo, str | None]) -> None:
            obj, kind = item
            await poll._ingest_one(vault_id, obj, kind, folder.kind, settings, summary, run)

        await self._for_each_file(
            to_ingest, settings.ingest_concurrency, lambda item: item[0].id, ingest, run, summary
        )

    async def _process_documents_folder(
        self,
        vault_id: str,
        folder: PdmWatchedFolder,
        files: list[PdmObjectInfo],
        all_snapshots: dict[int, PdmFileSnapshot],
        seen_file_ids: set[int],
        force: bool,
        summary: PollSummary,
        run: PdmSyncRun,
    ) -> None:
        """A `documents` folder's own diff: unlike made/bought, every file
        here keeps snapshot kind "document" (never made/bought conflict
        detection, see PdmFileSnapshot's docstring on why the two kind
        vocabularies are deliberately distinct strings) and is handed to
        PdmDocumentSync rather than IngestPdmFile. No workflow-state
        gating either: a file reaching an "Exported Documents" folder
        is already whatever a PDM task decided to publish there."""
        now = now_utc()
        snapshots_to_write: list[PdmFileSnapshot] = []
        to_sync: list[PdmObjectInfo] = []

        for obj in files:
            seen_file_ids.add(obj.id)
            summary.files_seen += 1
            existing = all_snapshots.get(obj.id)
            if existing is None:
                snapshot = PdmFileSnapshot(
                    id=0,
                    vault_id=vault_id,
                    file_id=obj.id,
                    kind="document",
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
                snapshots_to_write.append(snapshot)
                summary.changed += 1
                to_sync.append(obj)
                all_snapshots[obj.id] = snapshot
                continue

            is_changed = (
                force
                or existing.version != obj.version
                or existing.state_id != obj.state_id
                or existing.sync_state
                in (
                    PdmFileSyncState.PENDING.value,
                    PdmFileSyncState.ERROR.value,
                    PdmFileSyncState.MISSING.value,
                )
            )
            if not is_changed:
                continue
            self._apply_scan_fields(existing, obj, now)
            self._mark_queued(existing)
            snapshots_to_write.append(existing)
            summary.changed += 1
            to_sync.append(obj)
            all_snapshots[obj.id] = existing

        if snapshots_to_write:
            await self._snapshots.upsert_many(snapshots_to_write)
            await self._uow.commit()

        async def sync(poll: PollDispatch, obj: PdmObjectInfo) -> None:
            await poll._document_one(vault_id, obj, folder, summary, run)

        concurrency = (await self._admin_settings.get_pdm()).ingest_concurrency
        await self._for_each_file(to_sync, concurrency, lambda obj: obj.id, sync, run, summary)
