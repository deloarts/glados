"""Refreshes exactly one PDM file, the single-file counterpart of the poller,
used by the add-in trigger and the admin Retry action (see
docs/reference/pdm-sync.md section 2).

The file is resolved fresh from the Web API, since a trigger payload is
never trusted, and handed to ingest or, for a documents folder, to the
document sync, with the same folder, file type and fetch-before-write rules
as the poller. Every call that can name a file writes a one-entry sync run.
A linked file that vanished or left every watched folder is marked missing.
A successful ingest resets the folder's cold-folder cadence. The run also
records who asked and why, as the request said (RunOrigin), which is what
the vault add-in's file history shows next to the outcome.
"""

from dataclasses import dataclass

from src.modules.catalogue.domain.value_objects.pdm_sync_state import PdmSyncState
from src.modules.catalogue.ports.outbound.cad_item_store_port import IBoughtItemCadStore
from src.modules.catalogue.ports.outbound.cad_item_store_port import IMadeItemCadStore
from src.modules.external_data.application.dto.pdm_dto import IngestOutcome
from src.modules.external_data.application.dto.pdm_dto import PdmFilePayload
from src.modules.external_data.application.services.pdm_integration import is_pdm_enabled
from src.modules.external_data.application.services.pdm_integration import is_private_state
from src.modules.external_data.application.services.pdm_item_link import set_item_pdm_sync_state
from src.modules.external_data.application.services.pdm_session import PdmSessionService
from src.modules.external_data.application.services.pdm_skip_reasons import UNREADABLE
from src.modules.external_data.application.services.pdm_variables import NO_FILE_LEVEL_CONFIGURATION
from src.modules.external_data.application.services.pdm_variables import resolve_file_kind
from src.modules.external_data.application.services.pdm_variables import select_configuration
from src.modules.external_data.application.services.pdm_vault import file_extension
from src.modules.external_data.application.services.pdm_vault import hold_file
from src.modules.external_data.application.services.pdm_vault import resolve_and_store_vault_id
from src.modules.external_data.application.services.pdm_vault import sync_run_entry
from src.modules.external_data.application.services.pdm_vault import vault_name_matches
from src.modules.external_data.application.services.pdm_writeback import PdmWriteBack
from src.modules.external_data.application.use_cases.pdm.ingest_pdm_file import IngestPdmFile
from src.modules.external_data.application.use_cases.pdm.pdm_documents import PdmDocumentSync
from src.modules.external_data.application.use_cases.pdm.pdm_documents import PdmThumbnails
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.entities.pdm_file_snapshot import PdmFileSnapshot
from src.modules.external_data.domain.entities.pdm_sync_run import SYNC_RUN_RETENTION
from src.modules.external_data.domain.entities.pdm_sync_run import PdmSyncRun
from src.modules.external_data.domain.entities.pdm_sync_run import PdmSyncRunEntry
from src.modules.external_data.domain.errors import PdmApiError
from src.modules.external_data.domain.services.pdm_poll_cadence import folder_key
from src.modules.external_data.domain.value_objects.pdm_file_sync_state import PdmFileSyncState
from src.modules.external_data.domain.value_objects.pdm_sync_trigger import PdmSyncTrigger
from src.modules.external_data.domain.value_objects.pdm_watched_folder import PdmWatchedFolder
from src.modules.external_data.domain.value_objects.pdm_watched_folder import match_watched_folder
from src.modules.external_data.ports.outbound.external_data_settings_repository import (
    IExternalDataSettingsRepository,
)
from src.modules.external_data.ports.outbound.pdm_file_lock_port import IPdmFileLock
from src.modules.external_data.ports.outbound.pdm_gateway_port import IPdmGateway
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmConfigVariables
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
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc


@dataclass(frozen=True)
class RunOrigin:
    """What the one-entry run records about its request: the trigger, the
    caller's PdmChangeReason value and destination state, and the
    requester's full name."""

    trigger: PdmSyncTrigger
    change_reason: str | None = None
    change_state: str | None = None
    requested_by_name: str | None = None


# PDM's HTTP status for a file the vault lists but the current session may
# not read: a private-state file added to the vault but never checked in, or
# one this vault user lacks read grants to. Both are expected, not failures.
_UNREADABLE_STATUS_CODE = 403


class RefreshPdmFile:
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
        file_lock: IPdmFileLock | None = None,
    ) -> None:
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

    async def execute(
        self,
        vault_name: str,
        file_id: int | None,
        path: str | None,
        trigger: PdmSyncTrigger = PdmSyncTrigger.FILE_TRIGGER,
        change_reason: str | None = None,
        change_state: str | None = None,
        requested_by_name: str | None = None,
    ) -> None:
        origin = RunOrigin(trigger, change_reason, change_state, requested_by_name)
        settings = await self._admin_settings.get_pdm()
        if not self._refresh_is_applicable(settings, vault_name):
            return

        vault_id = await resolve_and_store_vault_id(
            settings, self._session, self._admin_settings, self._uow
        )

        obj = await self._resolve_object(file_id, path)
        if obj is None:
            await self._handle_not_found(vault_id, file_id, path, origin)
            return

        # The poller's workers or another trigger may be ingesting the same
        # file right now; wait for them, then find the file in sync.
        async with hold_file(self._file_lock, obj.id):
            await self._refresh_resolved(settings, vault_id, obj, origin)

    async def _refresh_resolved(
        self,
        settings: AdminPdmSettings,
        vault_id: str,
        obj: PdmObjectInfo,
        origin: RunOrigin,
    ) -> None:
        run = await self._start_run(origin)

        folder = match_watched_folder(settings.watched_folders, obj.path)
        if folder is None:
            await self._handle_no_matching_folder(run, vault_id, obj)
            return

        if folder.kind == "documents":
            await self._refresh_document(run, vault_id, folder, obj)
            return

        # A by_kind folder's kind stays open until the datacard is read.
        kind = None if folder.kind == "by_kind" else folder.kind

        # File type rule: a non-admitted extension is never snapshotted.
        if kind is not None and not self._extension_admitted(obj, kind, settings):
            await self._finish_extension_rejected(run, vault_id, obj, kind)
            return

        snapshot = await self._upsert_seen(vault_id, obj, kind)

        # A never checked-in file is unreadable, so skip the variables call.
        if is_private_state(obj):
            await self._finish_private_state_skip(run, snapshot, vault_id, obj, kind)
            return

        await self._ingest_or_record_error(run, snapshot, vault_id, obj, kind, folder, settings)

    def _refresh_is_applicable(self, settings: AdminPdmSettings, vault_name: str) -> bool:
        """Repeats the request-time check, because the vault may have been
        reconfigured or the integration disabled since the trigger."""
        if not is_pdm_enabled(settings):
            log.info("PDM refresh: integration not enabled/configured; ignoring the request.")
            return False
        if not vault_name_matches(vault_name, settings.vault_name):
            log.info(
                "PDM refresh: request for vault %r does not match the configured vault %r; "
                "ignoring.",
                vault_name,
                settings.vault_name,
            )
            return False
        return True

    async def _handle_no_matching_folder(
        self, run: PdmSyncRun, vault_id: str, obj: PdmObjectInfo
    ) -> None:
        existing = await self._snapshots.get_by_file(vault_id, obj.id)
        if existing is None:
            log.info(
                "PDM refresh: file %s/%s at %r is outside every watched folder; ignoring.",
                vault_id,
                obj.id,
                obj.path,
            )
            message = "file is outside every watched folder"
            await self._finish_run(
                run,
                entry=sync_run_entry(run.id, vault_id, obj, None, "skipped", None, message),
                skipped=1,
            )
            return
        # Leaving every watched folder counts as a deletion.
        message = "file moved outside every watched folder"
        await self._mark_missing(existing, message)
        log.info(
            "PDM refresh: file %s/%s at %r moved outside every watched folder; marked missing.",
            vault_id,
            obj.id,
            obj.path,
        )
        await self._finish_run(
            run,
            entry=sync_run_entry(
                run.id, vault_id, obj, existing.kind, "missing", existing.item_id, message
            ),
            missing=1,
        )

    def _extension_admitted(
        self, obj: PdmObjectInfo, kind: str, settings: AdminPdmSettings
    ) -> bool:
        admitted = (
            settings.made_item_extensions if kind == "made" else settings.bought_item_extensions
        )
        return file_extension(obj.name) in admitted

    async def _finish_extension_rejected(
        self, run: PdmSyncRun, vault_id: str, obj: PdmObjectInfo, kind: str
    ) -> None:
        ext = file_extension(obj.name)
        log.info(
            "PDM refresh: file %s/%s (%r) is not a %s item by extension; ignoring.",
            vault_id,
            obj.id,
            obj.name,
            kind,
        )
        message = f"{ext} files are not {kind} items"
        await self._finish_run(
            run,
            entry=sync_run_entry(run.id, vault_id, obj, kind, "skipped", None, message),
            skipped=1,
        )

    async def _ingest_or_record_error(
        self,
        run: PdmSyncRun,
        snapshot: PdmFileSnapshot,
        vault_id: str,
        obj: PdmObjectInfo,
        kind: str | None,
        folder: PdmWatchedFolder,
        settings: AdminPdmSettings,
    ) -> None:
        try:
            await self._ingest_with_resolved_kind(
                run, snapshot, vault_id, obj, kind, folder, settings
            )
        except Exception as exc:
            # Whatever the failed attempt left pending must not be committed
            # along with the error record, the same rule the poller follows.
            await self._uow.rollback()
            if isinstance(exc, PdmApiError) and exc.status_code == _UNREADABLE_STATUS_CODE:
                # Same 403 as the empty-state case above, just discovered a
                # call later: a file this vault user may list but not read.
                await self._finish_private_state_skip(run, snapshot, vault_id, obj, kind)
                return
            log.exception("PDM refresh %s/%s: failed.", vault_id, obj.id)
            snapshot.sync_state = PdmFileSyncState.ERROR
            snapshot.last_error = str(exc)
            await self._snapshots.upsert_many([snapshot])
            await self._uow.commit()
            await self._finish_run(
                run,
                entry=sync_run_entry(run.id, vault_id, obj, kind, "error", None, str(exc)),
                changed=1,
                errors=1,
            )

    async def _ingest_with_resolved_kind(
        self,
        run: PdmSyncRun,
        snapshot: PdmFileSnapshot,
        vault_id: str,
        obj: PdmObjectInfo,
        kind: str | None,
        folder: PdmWatchedFolder,
        settings: AdminPdmSettings,
    ) -> None:
        async def _variables(gw: IPdmGateway, token: str) -> list[PdmConfigVariables]:
            return await gw.file_variables(token, obj.id, obj.version, obj.parent_folder_id)

        configs = await self._session.call(_variables)
        variables = select_configuration(configs)
        if variables is None:
            await self._finish_kind_not_set(
                run, snapshot, vault_id, obj, NO_FILE_LEVEL_CONFIGURATION
            )
            return

        resolution = resolve_file_kind(
            folder_kind=folder.kind, variables=variables, settings=settings
        )
        if resolution.conflict is not None:
            await self._finish_kind_conflict(
                run, snapshot, vault_id, obj, kind, resolution.conflict
            )
            return
        if resolution.kind is None:
            message = (
                "kind not set"
                if not resolution.raw
                else f"kind not set (value: {resolution.raw!r})"
            )
            await self._finish_kind_not_set(run, snapshot, vault_id, obj, message)
            return
        kind = resolution.kind

        # The only file type gate for a by_kind folder on this path.
        if folder.kind == "by_kind" and not self._extension_admitted(obj, kind, settings):
            ext = file_extension(obj.name)
            message = f"{ext} files are not {kind} items"
            await self._finish_kind_not_set(run, snapshot, vault_id, obj, message)
            return

        payload = PdmFilePayload(
            vault_id=vault_id,
            file_id=obj.id,
            file_version=obj.version,
            path=obj.path,
            name=obj.name,
            parent_folder_id=obj.parent_folder_id,
            state_id=obj.state_id,
            state=obj.state,
            kind=kind,
            variables=variables,
            modified_at=obj.modified_at,
        )
        outcome = await self._ingest.execute(payload)
        log.info(
            "PDM refresh %s/%s: %s (item #%s).",
            vault_id,
            obj.id,
            outcome.action,
            outcome.item_id,
        )
        if outcome.action not in ("skipped", "conflict"):
            # A real ingest proves the folder is active.
            await self._folder_poll_states.reset(vault_id, folder_key(folder))
            # Committed before write-back and thumbnails talk to PDM, so no
            # Web API call starts with pending writes on this session.
            await self._uow.commit()
        await self._finish_ingested(run, vault_id, obj, kind, outcome)

    async def _refresh_document(
        self, run: PdmSyncRun, vault_id: str, folder: PdmWatchedFolder, obj: PdmObjectInfo
    ) -> None:
        """Syncs a documents folder's file. Its snapshot kind is "document",
        deliberately distinct from the folder kind "documents"."""
        snapshot = await self._upsert_seen(vault_id, obj, "document")
        try:
            outcome = await self._document_sync.sync_one(vault_id=vault_id, folder=folder, obj=obj)
            log.info(
                "PDM refresh %s/%s: %s (item #%s).",
                vault_id,
                obj.id,
                outcome.action,
                outcome.item_id,
            )
            entry = sync_run_entry(
                run.id, vault_id, obj, "document", outcome.action, outcome.item_id, outcome.message
            )
            if outcome.action == "document":
                await self._folder_poll_states.reset(vault_id, folder_key(folder))
                await self._finish_run(run, entry=entry, changed=1, ingested=1)
            elif outcome.action == "document_error":
                await self._finish_run(run, entry=entry, changed=1, errors=1)
            else:
                await self._finish_run(run, entry=entry, changed=1, skipped=1)
        except Exception as exc:
            if isinstance(exc, PdmApiError) and exc.status_code == _UNREADABLE_STATUS_CODE:
                snapshot.sync_state = PdmFileSyncState.SKIPPED
                snapshot.last_error = UNREADABLE
                await self._snapshots.upsert_many([snapshot])
                await self._uow.commit()
                entry = sync_run_entry(
                    run.id, vault_id, obj, "document", "skipped", None, UNREADABLE
                )
                await self._finish_run(run, entry=entry, changed=1, skipped=1)
                return
            log.exception("PDM refresh: document %s/%s failed.", vault_id, obj.id)
            snapshot.sync_state = PdmFileSyncState.ERROR
            snapshot.last_error = str(exc)
            await self._snapshots.upsert_many([snapshot])
            await self._uow.commit()
            await self._finish_run(
                run,
                entry=sync_run_entry(run.id, vault_id, obj, "document", "error", None, str(exc)),
                changed=1,
                errors=1,
            )

    async def _resolve_object(self, file_id: int | None, path: str | None) -> PdmObjectInfo | None:
        async def _lookup(gw: IPdmGateway, token: str) -> PdmObjectInfo | None:
            if file_id is not None:
                results = await gw.files_info(token, [file_id])
                return results[0] if results else None
            return await gw.file_info_from_path(token, path or "")

        return await self._session.call(_lookup)

    async def _handle_not_found(
        self, vault_id: str, file_id: int | None, path: str | None, origin: RunOrigin
    ) -> None:
        existing = (
            await self._snapshots.get_by_file(vault_id, file_id) if file_id is not None else None
        )
        resolved_file_id = (
            file_id if file_id is not None else (existing.file_id if existing else None)
        )
        if resolved_file_id is None:
            # Nothing names this file, so nothing is recorded.
            log.info(
                "PDM refresh: file not found (vault=%r, file_id=%r, path=%r); nothing to update.",
                vault_id,
                file_id,
                path,
            )
            return

        message = "file no longer found in PDM"
        if existing is not None:
            await self._mark_missing(existing, message)
            log.info(
                "PDM refresh: file %s/%s no longer exists in PDM; marked missing.",
                vault_id,
                resolved_file_id,
            )
        else:
            log.info(
                "PDM refresh: file %s/%s not found in PDM and never seen before; nothing to "
                "update.",
                vault_id,
                resolved_file_id,
            )

        run = await self._start_run(origin)
        entry = PdmSyncRunEntry(
            id=0,
            run_id=run.id,
            vault_id=vault_id,
            file_id=resolved_file_id,
            name=existing.name if existing is not None else "",
            path=existing.path if existing is not None else (path or ""),
            kind=existing.kind if existing is not None else None,
            action="missing",
            item_id=existing.item_id if existing is not None else None,
            message=message,
            created_at=now_utc(),
        )
        await self._finish_run(run, entry=entry, missing=1)

    async def _mark_missing(self, snapshot: PdmFileSnapshot, message: str) -> None:
        """Marks the snapshot missing and, for a made or bought snapshot, its
        item as well."""
        snapshot.sync_state = PdmFileSyncState.MISSING
        snapshot.last_error = message
        await self._snapshots.upsert_many([snapshot])
        if snapshot.item_id is not None and snapshot.kind in ("made", "bought"):
            # A document snapshot does not own the item it names.
            await self._set_item_missing(snapshot.kind, snapshot.item_id)
        await self._uow.commit()

    async def _set_item_missing(self, kind: str, item_id: int) -> None:
        await set_item_pdm_sync_state(
            self._made_items, self._bought_items, kind, item_id, PdmSyncState.MISSING
        )

    async def _upsert_seen(
        self, vault_id: str, obj: PdmObjectInfo, kind: str | None
    ) -> PdmFileSnapshot:
        """Upserts the scan metadata before ingest, so a failure has a row to
        record on. An existing row keeps its kind and every ingest-owned
        field."""
        now = now_utc()
        existing = await self._snapshots.get_by_file(vault_id, obj.id)
        snapshot = existing or PdmFileSnapshot(
            id=0,
            vault_id=vault_id,
            file_id=obj.id,
            kind=kind,
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
        snapshot.name = obj.name
        snapshot.path = obj.path
        snapshot.parent_folder_id = obj.parent_folder_id
        snapshot.version = obj.version
        snapshot.state_id = obj.state_id
        snapshot.state = obj.state
        snapshot.modified_at = obj.modified_at
        snapshot.last_seen_at = now
        await self._snapshots.upsert_many([snapshot])
        await self._uow.commit()
        return snapshot

    # ── Sync run log ──────────────────────────────────────────────────

    async def _start_run(self, origin: RunOrigin) -> PdmSyncRun:
        run = await self._runs.start(
            PdmSyncRun(
                id=0,
                started_at=now_utc(),
                finished_at=None,
                trigger=origin.trigger,
                files_seen=1,
                changed=0,
                ingested=0,
                skipped=0,
                conflicts=0,
                errors=0,
                missing=0,
                error=None,
                summary=None,
                folders_walked=0,
                change_reason=origin.change_reason,
                change_state=origin.change_state,
                requested_by_name=origin.requested_by_name,
            )
        )
        await self._uow.commit()
        return run

    async def _finish_ingested(
        self, run: PdmSyncRun, vault_id: str, obj: PdmObjectInfo, kind: str, outcome: IngestOutcome
    ) -> None:
        entry = sync_run_entry(
            run.id, vault_id, obj, kind, outcome.action, outcome.item_id, outcome.message
        )
        # Write-back commits its entry before the thumbnail download, so no
        # PDM call starts with pending writes.
        await self._write_back.after_outcome(vault_id, obj, kind, outcome, run)
        await self._uow.commit()
        await self._thumbnails.after_ingest(vault_id, obj, kind, outcome, run)
        if outcome.action == "conflict":
            await self._finish_run(run, entry=entry, changed=1, conflicts=1)
        elif outcome.action == "skipped":
            await self._finish_run(run, entry=entry, changed=1, skipped=1)
        else:
            await self._finish_run(run, entry=entry, changed=1, ingested=1)

    async def _finish_private_state_skip(
        self,
        run: PdmSyncRun,
        snapshot: PdmFileSnapshot,
        vault_id: str,
        obj: PdmObjectInfo,
        kind: str | None,
    ) -> None:
        """Records an unreadable file as an expected skip; a later check-in
        is picked up normally. A linked file still gets write-back, so the
        vault keeps showing the last known state."""
        snapshot.sync_state = PdmFileSyncState.SKIPPED
        snapshot.last_error = UNREADABLE
        await self._snapshots.upsert_many([snapshot])
        await self._uow.commit()
        entry = sync_run_entry(run.id, vault_id, obj, kind, "skipped", None, UNREADABLE)
        if snapshot.item_id is not None and snapshot.kind is not None:
            outcome = IngestOutcome(action="skipped", item_id=snapshot.item_id, message=UNREADABLE)
            await self._write_back.after_outcome(vault_id, obj, snapshot.kind, outcome, run)
        await self._finish_run(run, entry=entry, changed=1, skipped=1)

    async def _finish_kind_not_set(
        self,
        run: PdmSyncRun,
        snapshot: PdmFileSnapshot,
        vault_id: str,
        obj: PdmObjectInfo,
        message: str,
    ) -> None:
        """A by_kind file without a recognised kind is skipped."""
        snapshot.sync_state = PdmFileSyncState.SKIPPED
        snapshot.last_error = message
        await self._snapshots.upsert_many([snapshot])
        await self._uow.commit()
        entry = sync_run_entry(run.id, vault_id, obj, snapshot.kind, "skipped", None, message)
        await self._finish_run(run, entry=entry, changed=1, skipped=1)

    async def _finish_kind_conflict(
        self,
        run: PdmSyncRun,
        snapshot: PdmFileSnapshot,
        vault_id: str,
        obj: PdmObjectInfo,
        kind: str | None,
        message: str,
    ) -> None:
        """A file whose kind variable disagrees with its folder is parked as
        a conflict; the add-in is the first guard."""
        snapshot.sync_state = PdmFileSyncState.CONFLICT
        snapshot.last_error = message
        await self._snapshots.upsert_many([snapshot])
        await self._uow.commit()
        entry = sync_run_entry(run.id, vault_id, obj, kind, "conflict", None, message)
        await self._finish_run(run, entry=entry, changed=1, conflicts=1)

    async def _finish_run(
        self,
        run: PdmSyncRun,
        *,
        entry: PdmSyncRunEntry,
        changed: int = 0,
        ingested: int = 0,
        skipped: int = 0,
        conflicts: int = 0,
        errors: int = 0,
        missing: int = 0,
    ) -> None:
        await self._runs.add_entries(run.id, [entry])
        run.finished_at = now_utc()
        run.changed = changed
        run.ingested = ingested
        run.skipped = skipped
        run.conflicts = conflicts
        run.errors = errors
        run.missing = missing
        run.summary = entry.message
        await self._runs.finish(run)
        await self._uow.commit()
        await self._runs.prune(now_utc() - SYNC_RUN_RETENTION)
        await self._uow.commit()
