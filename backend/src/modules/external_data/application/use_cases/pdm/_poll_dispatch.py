"""The per-file dispatch of the PDM poll: handing each changed file to
IngestPdmFile or PdmDocumentSync, in parallel workers when a worker factory
is wired, and recording each outcome, skip and error on the snapshot and the
run log. The behaviour is documented in docs/reference/pdm-sync.md sections
3.4, 3.8 and 3.11.

Each file is handled while holding its lock, so the trigger path never
ingests it at the same time. PollDispatch is a base class of PollPdmVault and
reads the dependencies its constructor sets; a parallel worker is another
PollPdmVault on its own database session.
"""

import asyncio
from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Sequence
from contextlib import AbstractAsyncContextManager
from typing import TypeVar

from src.modules.external_data.application.dto.pdm_dto import IngestOutcome
from src.modules.external_data.application.dto.pdm_dto import PdmFilePayload
from src.modules.external_data.application.services.pdm_integration import is_private_state
from src.modules.external_data.application.services.pdm_session import PdmSessionService
from src.modules.external_data.application.services.pdm_skip_reasons import UNREADABLE
from src.modules.external_data.application.services.pdm_variables import NO_FILE_LEVEL_CONFIGURATION
from src.modules.external_data.application.services.pdm_variables import resolve_file_kind
from src.modules.external_data.application.services.pdm_variables import select_configuration
from src.modules.external_data.application.services.pdm_vault import file_extension
from src.modules.external_data.application.services.pdm_vault import hold_file
from src.modules.external_data.application.services.pdm_vault import sync_run_entry
from src.modules.external_data.application.services.pdm_writeback import PdmWriteBack
from src.modules.external_data.application.use_cases.pdm._poll_run import _PHASE_INGESTING
from src.modules.external_data.application.use_cases.pdm._poll_run import PollRunLog
from src.modules.external_data.application.use_cases.pdm._poll_run import PollSummary
from src.modules.external_data.application.use_cases.pdm.ingest_pdm_file import IngestPdmFile
from src.modules.external_data.application.use_cases.pdm.pdm_documents import PdmDocumentSync
from src.modules.external_data.application.use_cases.pdm.pdm_documents import PdmThumbnails
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.entities.pdm_sync_run import PdmSyncRun
from src.modules.external_data.domain.errors import PdmApiError
from src.modules.external_data.domain.value_objects.pdm_file_sync_state import PdmFileSyncState
from src.modules.external_data.domain.value_objects.pdm_watched_folder import PdmWatchedFolder
from src.modules.external_data.ports.outbound.pdm_file_lock_port import IPdmFileLock
from src.modules.external_data.ports.outbound.pdm_gateway_port import IPdmGateway
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmConfigVariables
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmObjectInfo
from src.modules.external_data.ports.outbound.repositories.pdm_file_snapshot_repository import (
    IPdmFileSnapshotRepository,
)
from src.modules.platform.infrastructure.logging.logger import log

# PDM's HTTP status for a file the vault lists but the current session may
# not read: a private-state file added to the vault but never checked in, or
# one this vault user lacks read grants to. Both are expected, not failures.
_UNREADABLE_STATUS_CODE = 403

T = TypeVar("T")


class PollDispatch(PollRunLog):
    """The per-file dispatch; PollPdmVault sets every attribute declared here."""

    _worker_factory: Callable[[], AbstractAsyncContextManager["PollDispatch"]] | None
    _file_lock: IPdmFileLock | None
    _session: PdmSessionService
    _snapshots: IPdmFileSnapshotRepository
    _ingest: IngestPdmFile
    _write_back: PdmWriteBack
    _document_sync: PdmDocumentSync
    _thumbnails: PdmThumbnails

    async def _ingest_one(
        self,
        vault_id: str,
        obj: PdmObjectInfo,
        kind: str | None,
        folder_kind: str,
        settings: AdminPdmSettings,
        summary: PollSummary,
        run: PdmSyncRun,
    ) -> None:
        # A file added to the vault but never checked in sits in PDM's
        # private state (see is_private_state's own docstring), and
        # file_variables would 403 for it anyway, so this skips straight
        # past that call.
        if is_private_state(obj):
            summary.skipped += 1
            await self._record_private_state_skip(vault_id, obj, kind, run, summary)
            return
        try:
            outcome, resolved_kind = await self._fetch_and_ingest(
                vault_id, obj, kind, folder_kind, settings
            )
            self._tally(outcome_action=outcome.action, summary=summary)
            await self._runs.add_entries(
                run.id,
                [
                    sync_run_entry(
                        run.id,
                        vault_id,
                        obj,
                        resolved_kind,
                        outcome.action,
                        outcome.item_id,
                        outcome.message,
                    )
                ],
            )
            # Each step's run entry (and the thumbnail key) is committed on
            # its own before the next step talks to PDM, so no Web API call
            # ever starts with pending writes on this shared session.
            await self._uow.commit()
            if resolved_kind is not None:
                wb_action = await self._write_back.after_outcome(
                    vault_id, obj, resolved_kind, outcome, run
                )
                await self._uow.commit()
                if wb_action == "writeback":
                    summary.written_back += 1
                thumb_action = await self._thumbnails.after_ingest(
                    vault_id, obj, resolved_kind, outcome, run
                )
                await self._uow.commit()
                if thumb_action == "thumbnail":
                    summary.thumbnails += 1
        except Exception as exc:
            if isinstance(exc, PdmApiError) and exc.status_code == _UNREADABLE_STATUS_CODE:
                # Same 403 as the empty-state case above, just discovered a
                # call later: a file this vault user may list but not read.
                summary.skipped += 1
                await self._record_private_state_skip(vault_id, obj, kind, run, summary)
                return
            log.exception("PDM poll: %s/%s failed.", vault_id, obj.id)
            summary.errors += 1
            await self._record_error(vault_id, obj, kind, str(exc), run)

    async def _document_one(
        self,
        vault_id: str,
        obj: PdmObjectInfo,
        folder: PdmWatchedFolder,
        summary: PollSummary,
        run: PdmSyncRun,
    ) -> None:
        try:
            outcome = await self._document_sync.sync_one(vault_id=vault_id, folder=folder, obj=obj)
            if outcome.action == "document":
                summary.documents += 1
            elif outcome.action == "document_error":
                summary.document_errors += 1
            else:
                summary.skipped += 1
            await self._runs.add_entries(
                run.id,
                [
                    sync_run_entry(
                        run.id,
                        vault_id,
                        obj,
                        "document",
                        outcome.action,
                        outcome.item_id,
                        outcome.message,
                    )
                ],
            )
            await self._uow.commit()
        except Exception as exc:
            if isinstance(exc, PdmApiError) and exc.status_code == _UNREADABLE_STATUS_CODE:
                summary.skipped += 1
                await self._record_private_state_skip(vault_id, obj, "document", run, summary)
                return
            log.exception("PDM poll: document %s/%s failed.", vault_id, obj.id)
            summary.errors += 1
            await self._record_error(vault_id, obj, "document", str(exc), run)

    async def _for_each_file(
        self,
        items: Sequence[T],
        concurrency: int,
        file_id_of: Callable[[T], int],
        work: Callable[["PollDispatch", T], Awaitable[None]],
        run: PdmSyncRun,
        summary: PollSummary,
    ) -> None:
        """Runs `work` once per changed file, holding that file's lock so the
        trigger worker never ingests it at the same time. With a worker
        factory and a concurrency above 1, up to `concurrency` workers drain
        the files in parallel, each on its own database session, since one
        session cannot serve concurrent requests; otherwise this poller
        handles them one after another on its own session. Each finished
        file counts towards the run's live progress."""
        if not items:
            return
        run.phase = _PHASE_INGESTING
        run.files_queued += len(items)
        await self._save_progress(run, summary, force=True)

        if self._worker_factory is None or concurrency <= 1 or len(items) <= 1:
            for item in items:
                async with hold_file(self._file_lock, file_id_of(item)):
                    await work(self, item)
                run.files_processed += 1
                await self._save_progress(run, summary)
            return

        pending: asyncio.Queue[T] = asyncio.Queue()
        for item in items:
            pending.put_nowait(item)
        factory = self._worker_factory

        async def drain() -> None:
            async with factory() as worker:
                while True:
                    try:
                        item = pending.get_nowait()
                    except asyncio.QueueEmpty:
                        return
                    async with hold_file(self._file_lock, file_id_of(item)):
                        await work(worker, item)
                    run.files_processed += 1
                    await worker._save_progress(run, summary)

        async with asyncio.TaskGroup() as group:
            for _ in range(min(concurrency, len(items))):
                group.create_task(drain())

    async def _fetch_and_ingest(
        self,
        vault_id: str,
        obj: PdmObjectInfo,
        kind: str | None,
        folder_kind: str,
        settings: AdminPdmSettings,
    ) -> tuple[IngestOutcome, str | None]:
        """Fetches `obj`'s datacard variables and, for a `by_kind` folder,
        resolves the kind from them before ingest ever runs (kind is
        unknown at scan time for such folders); for an explicit folder,
        checks the same variable for a disagreement with the folder's own
        declared kind. Either failure mode (kind not resolvable, or a
        disagreement) is handled here directly, without calling
        IngestPdmFile at all: see docs/reference/pdm-settings.md section 4.3, "kind
        by datacard". Returns the outcome plus the kind actually used, so the
        caller's run-log entry reflects it even when it was only just
        resolved."""

        async def _do(gw: IPdmGateway, token: str) -> list[PdmConfigVariables]:
            return await gw.file_variables(token, obj.id, obj.version, obj.parent_folder_id)

        configs = await self._session.call(_do)
        variables = select_configuration(configs)
        if variables is None:
            return await self._skip_kind_not_set(vault_id, obj, NO_FILE_LEVEL_CONFIGURATION), kind

        resolution = resolve_file_kind(
            folder_kind=folder_kind, variables=variables, settings=settings
        )
        if resolution.conflict is not None:
            return await self._kind_folder_conflict(vault_id, obj, resolution.conflict), kind
        if resolution.kind is None:
            message = (
                "kind not set"
                if not resolution.raw
                else f"kind not set (value: {resolution.raw!r})"
            )
            return await self._skip_kind_not_set(vault_id, obj, message), None
        kind = resolution.kind

        # File-type rule re-check (docs/reference/pdm-documents.md section 1): a
        # by_kind folder admitted the union of both
        # extension sets at walk time since its kind was unknown then;
        # now that the kind is resolved, re-check against that kind's own
        # set specifically. An explicit made/bought folder never reaches
        # here having admitted the wrong extension: _walk_children
        # already filtered it at scan time.
        if folder_kind == "by_kind":
            kind_extensions = (
                settings.made_item_extensions if kind == "made" else settings.bought_item_extensions
            )
            ext = file_extension(obj.name)
            if ext not in kind_extensions:
                message = f"{ext} files are not {kind} items"
                return await self._skip_kind_not_set(vault_id, obj, message), kind

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
        return await self._ingest.execute(payload), kind

    async def _skip_kind_not_set(
        self, vault_id: str, obj: PdmObjectInfo, message: str
    ) -> IngestOutcome:
        """A by_kind folder's file whose kind datacard variable is empty
        or unrecognised: no ingest is attempted (IngestPdmFile requires a
        resolved kind), the snapshot's own `kind` column stays whatever it
        already was (None for a brand-new file)."""
        snapshot = await self._snapshots.get_by_file(vault_id, obj.id)
        if snapshot is not None:
            snapshot.sync_state = PdmFileSyncState.SKIPPED
            snapshot.last_error = message
            await self._snapshots.upsert_many([snapshot])
            await self._uow.commit()
        return IngestOutcome(action="skipped", item_id=None, message=message)

    async def _kind_folder_conflict(
        self, vault_id: str, obj: PdmObjectInfo, message: str
    ) -> IngestOutcome:
        """An explicit made/bought folder whose file's kind datacard
        variable disagrees with the folder. The add-in is the first
        guard, and this is the poller's own backstop. No ingest is attempted."""
        snapshot = await self._snapshots.get_by_file(vault_id, obj.id)
        if snapshot is not None:
            snapshot.sync_state = PdmFileSyncState.CONFLICT
            snapshot.last_error = message
            await self._snapshots.upsert_many([snapshot])
            await self._uow.commit()
        return IngestOutcome(action="conflict", item_id=None, message=message)

    @staticmethod
    def _tally(*, outcome_action: str, summary: PollSummary) -> None:
        if outcome_action == "conflict":
            summary.conflicts += 1
        elif outcome_action == "skipped":
            summary.skipped += 1
        else:
            summary.ingested += 1

    async def _record_error(
        self, vault_id: str, obj: PdmObjectInfo, kind: str | None, message: str, run: PdmSyncRun
    ) -> None:
        """Records an ingest/sync failure against the file's snapshot and
        the run entry, then commits. Rolls back first: the poller shares
        one session across every file of a tick, so the exception this is
        called for may have left pending, half-written state on the
        session (from the failed ingest attempt) that must not be
        committed alongside the error record. A caller that already rolled
        back before calling this is unaffected, a second rollback is a
        no-op."""
        await self._uow.rollback()
        snapshot = await self._snapshots.get_by_file(vault_id, obj.id)
        if snapshot is not None:
            snapshot.sync_state = PdmFileSyncState.ERROR
            snapshot.last_error = message
            await self._snapshots.upsert_many([snapshot])
        await self._runs.add_entries(
            run.id, [sync_run_entry(run.id, vault_id, obj, kind, "error", None, message)]
        )
        await self._uow.commit()

    async def _record_private_state_skip(
        self,
        vault_id: str,
        obj: PdmObjectInfo,
        kind: str | None,
        run: PdmSyncRun,
        summary: PollSummary,
    ) -> None:
        """Stores UNREADABLE in last_error, the same message
        the run entry below gets, matching every other skip IngestPdmFile
        records. Unlike _record_error, this is an expected, transient
        condition, not a failure. The snapshot's version/state were already
        refreshed by this run's own diff upsert, so a later check-in still
        shows up as changed and gets ingested normally.

        A file already linked (snapshot.item_id set) still gets a
        write-back attempt here: even though nothing was re-ingested, the
        vault's own Glados.* variables should keep reflecting the last
        known-good state rather than going stale just because this
        particular run could not re-read the file: see PdmWriteBack's
        module docstring."""
        snapshot = await self._snapshots.get_by_file(vault_id, obj.id)
        if snapshot is not None:
            snapshot.sync_state = PdmFileSyncState.SKIPPED
            snapshot.last_error = UNREADABLE
            await self._snapshots.upsert_many([snapshot])
        await self._runs.add_entries(
            run.id,
            [sync_run_entry(run.id, vault_id, obj, kind, "skipped", None, UNREADABLE)],
        )
        await self._uow.commit()
        if (
            snapshot is not None
            and snapshot.item_id is not None
            and snapshot.kind in ("made", "bought")
        ):
            outcome = IngestOutcome(action="skipped", item_id=snapshot.item_id, message=UNREADABLE)
            wb_action = await self._write_back.after_outcome(
                vault_id, obj, snapshot.kind, outcome, run
            )
            await self._uow.commit()
            if wb_action == "writeback":
                summary.written_back += 1
