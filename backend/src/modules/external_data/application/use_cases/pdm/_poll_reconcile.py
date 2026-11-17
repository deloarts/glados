"""The end of a PDM poll run: the missing-file sweep over the walked
folders, the retry of parked conflicts and the cold-folder cadence update.
The behaviour is documented in docs/reference/pdm-sync.md sections 3.6, 3.9
and 3.10.

PollReconcile is a base class of PollPdmVault and reads the dependencies its
constructor sets. A conflict retry goes through the same dispatch as a
changed file, so it inherits the per-file diff and dispatch parts.
"""

from datetime import timedelta

from src.modules.external_data.application.services.pdm_vault import sync_run_entry
from src.modules.external_data.application.use_cases.pdm._poll_diff import PollFileDiff
from src.modules.external_data.application.use_cases.pdm._poll_dispatch import PollDispatch
from src.modules.external_data.application.use_cases.pdm._poll_run import PollSummary
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.entities.pdm_file_snapshot import PdmFileSnapshot
from src.modules.external_data.domain.entities.pdm_folder_poll_state import PdmFolderPollState
from src.modules.external_data.domain.entities.pdm_sync_run import PdmSyncRun
from src.modules.external_data.domain.entities.pdm_sync_run import PdmSyncRunEntry
from src.modules.external_data.domain.services.pdm_poll_cadence import folder_key
from src.modules.external_data.domain.services.pdm_poll_cadence import next_interval_minutes
from src.modules.external_data.domain.value_objects.pdm_file_sync_state import PdmFileSyncState
from src.modules.external_data.domain.value_objects.pdm_watched_folder import PdmWatchedFolder
from src.modules.external_data.domain.value_objects.pdm_watched_folder import match_watched_folder
from src.modules.external_data.ports.outbound.pdm_gateway_port import IPdmGateway
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmObjectInfo
from src.modules.external_data.ports.outbound.repositories.pdm_folder_poll_state_repository import (
    IPdmFolderPollStateRepository,
)
from src.shared_kernel.domain.services.clock import now_utc

# Beyond this many parked conflicts, an unchanged one is retried at most
# once per interval (manual runs always retry). Conflicts are re-read from
# PDM this many at a time.
_CONFLICT_BACKLOG = 100
_CONFLICT_RETRY_INTERVAL = timedelta(hours=1)
_FILES_INFO_BATCH = 100


class PollReconcile(PollFileDiff, PollDispatch):
    """The end-of-run steps; PollPdmVault sets every attribute declared here."""

    _folder_poll_states: IPdmFolderPollStateRepository

    async def _sweep_missing(
        self,
        vault_id: str,
        folder_membership: dict[int, PdmWatchedFolder],
        all_snapshots: dict[int, PdmFileSnapshot],
        seen_file_ids: set[int],
        summary: PollSummary,
        run: PdmSyncRun,
        changed_folder_keys: set[str],
    ) -> None:
        """Set difference over the vault-wide snapshot map loaded at the
        start of the run: any row whose `parent_folder_id` this run
        actually visited (a key of `folder_membership`, built while
        walking) but whose own file was not
        seen this run, and is not already missing, gets marked so. A
        folder whose root browse failed contributes nothing to
        `folder_membership`, so one bad call never mass-misses an entire
        tree, and a snapshot is attributed by its exact parent folder id
        rather than the longest matching path prefix: a prefix guess breaks
        silently across a rename, since a renamed folder's stored `path` no
        longer matches anything it still, in PDM, actually contains.

        Every folder a missing file is attributed to is also added to
        `changed_folder_keys`, mutated in place: cold-folder cadence
        treats a newly missing file the same
        as any other change, so the folder's own backoff resets rather
        than advancing just because nothing was actively re-ingested."""
        if not folder_membership:
            return
        to_write: list[PdmFileSnapshot] = []
        entries: list[PdmSyncRunEntry] = []
        any_missing = False
        now = now_utc()
        for snapshot in all_snapshots.values():
            if snapshot.file_id in seen_file_ids:
                continue
            if snapshot.sync_state == PdmFileSyncState.MISSING.value:
                continue
            folder = folder_membership.get(snapshot.parent_folder_id)
            if folder is None:
                continue
            snapshot.sync_state = PdmFileSyncState.MISSING
            snapshot.last_error = f"file no longer found under {folder.path}"
            to_write.append(snapshot)
            summary.missing += 1
            changed_folder_keys.add(folder_key(folder))
            entries.append(
                PdmSyncRunEntry(
                    id=0,
                    run_id=run.id,
                    vault_id=vault_id,
                    file_id=snapshot.file_id,
                    name=snapshot.name,
                    path=snapshot.path,
                    kind=snapshot.kind,
                    action="missing",
                    item_id=snapshot.item_id,
                    message=snapshot.last_error,
                    created_at=now,
                )
            )
            if snapshot.item_id is not None and snapshot.kind in ("made", "bought"):
                # A "document" snapshot's item_id names the made/bought
                # row it backs, not one this snapshot itself owns. A
                # missing document keeps the item file and marks only the
                # snapshot missing, never the item's own pdm_sync_state
                # (see PdmFileSnapshot's docstring and docs/reference/pdm-documents.md
                # section 5).
                await self._set_item_missing(snapshot.kind, snapshot.item_id)
                any_missing = True
        if to_write:
            await self._snapshots.upsert_many(to_write)
        if entries:
            await self._runs.add_entries(run.id, entries)
        if to_write or any_missing:
            await self._uow.commit()

    async def _update_folder_cadence(
        self,
        vault_id: str,
        settings: AdminPdmSettings,
        walked_folder_keys: set[str],
        changed_folder_keys: set[str],
        cold_states: dict[str, PdmFolderPollState],
    ) -> None:
        """Called only for a SCHEDULED run: a MANUAL or INITIAL run walks every folder but never
        touches this state, so a forced re-evaluation can never itself
        cool a folder down or prematurely warm it back up. For every
        folder actually walked this run (root browse succeeded), a folder
        in `changed_folder_keys` is reset back to the base interval via
        the repository's own `reset`; every other walked folder advances
        its unchanged streak and gets a new `next_due_at`, capped by
        `settings.cold_folder_max_multiplier`. Writes are staged only
        (upsert/reset never commit); the run's own commit persists them."""
        now = now_utc()
        for key in walked_folder_keys:
            if key in changed_folder_keys:
                await self._folder_poll_states.reset(vault_id, key)
                continue
            state = cold_states.get(key)
            unchanged_runs = (state.consecutive_unchanged_runs if state is not None else 0) + 1
            next_due = now + timedelta(
                minutes=next_interval_minutes(
                    settings.poll_interval_minutes,
                    unchanged_runs,
                    settings.cold_folder_max_multiplier,
                )
            )
            await self._folder_poll_states.upsert(
                PdmFolderPollState(
                    id=state.id if state is not None else 0,
                    vault_id=vault_id,
                    folder_key=key,
                    consecutive_unchanged_runs=unchanged_runs,
                    next_due_at=next_due,
                    last_changed_at=state.last_changed_at if state is not None else None,
                    updated_at=now,
                )
            )

    async def _retry_conflicts(
        self,
        vault_id: str,
        folders: list[PdmWatchedFolder],
        settings: AdminPdmSettings,
        summary: PollSummary,
        run: PdmSyncRun,
        force: bool = False,
    ) -> None:
        """docs/reference/field-ownership.md section 5: a parked conflict is retried at the
        end of every run so a resolved clash (a renumbering chain, a freed
        part number, a corrected kind variable, a file moved back to its
        own kind's folder) converges on its own. Re-reads the file fresh
        from PDM rather than replaying `parked_payload` verbatim. This is the
        exact same "fetch, then ingest" path as a changed file, so it
        needs no special-cased version-guard bypass: an item's own
        pdm_file_version is never bumped while it sits in conflict, so a
        fresh read always clears the version guard on its own. Each retry's outcome
        (re-ingested, still conflicted, or vanished) lands its own run
        entry, the same as any other touched file.

        `folder_kind` for the retry is resolved fresh from the file's
        current path (its watched folder may have changed since the
        conflict was parked), falling back to the snapshot's own kind
        when no folder covers it any more, and finally to "by_kind" (a
        fresh resolution attempt) when neither is known. The scan-time
        "linked file in the wrong explicit folder" check
        (`_folder_link_conflict_message`) is re-applied first: a retry
        that would still hit the same conflict never reaches
        IngestPdmFile at all, which, unlike the poller's own scan, has
        no way to know the file was already linked as a different kind.

        The files are re-read in batches. Once more than _CONFLICT_BACKLOG
        conflicts are parked, one whose file is unchanged in PDM is only
        retried again when its last attempt is an hour old, or on a manual
        run, so a large backlog does not cost a full ingest of every
        conflict each tick."""
        conflicts = await self._snapshots.list_conflicts(vault_id)
        fresh = await self._fetch_by_ids([snapshot.file_id for snapshot in conflicts])
        throttle = not force and len(conflicts) > _CONFLICT_BACKLOG
        retry_before = now_utc() - _CONFLICT_RETRY_INTERVAL
        for snapshot in conflicts:
            obj = fresh.get(snapshot.file_id)
            if obj is None:
                await self._mark_conflict_vanished(vault_id, snapshot, summary, run)
                continue
            unchanged = obj.version == snapshot.version and obj.state_id == snapshot.state_id
            if throttle and unchanged and snapshot.last_seen_at > retry_before:
                continue
            folder_kind = self._retry_folder_kind(folders, obj, snapshot)

            conflict_message = self._folder_link_conflict_message(snapshot, folder_kind)
            if conflict_message is not None:
                snapshot.last_error = conflict_message
                snapshot.last_seen_at = now_utc()
                await self._snapshots.upsert_many([snapshot])
                entry = sync_run_entry(
                    run.id,
                    vault_id,
                    obj,
                    snapshot.kind,
                    "conflict",
                    snapshot.item_id,
                    conflict_message,
                )
                await self._runs.add_entries(run.id, [entry])
                await self._uow.commit()
                summary.conflicts += 1
                continue

            await self._ingest_one(
                vault_id, obj, snapshot.kind, folder_kind, settings, summary, run
            )

    @staticmethod
    def _retry_folder_kind(
        folders: list[PdmWatchedFolder], obj: PdmObjectInfo, snapshot: PdmFileSnapshot
    ) -> str:
        """The covering watched folder's kind, else the snapshot's own kind, else "by_kind" for
        a fresh resolution attempt."""
        folder = match_watched_folder(folders, obj.path)
        if folder is not None:
            return folder.kind
        if snapshot.kind is not None:
            return snapshot.kind
        return "by_kind"

    async def _mark_conflict_vanished(
        self, vault_id: str, snapshot: PdmFileSnapshot, summary: PollSummary, run: PdmSyncRun
    ) -> None:
        """A parked conflict whose file PDM no longer returns is marked missing, together with
        its linked item."""
        snapshot.sync_state = PdmFileSyncState.MISSING
        snapshot.last_error = "file no longer found in PDM"
        await self._snapshots.upsert_many([snapshot])
        if snapshot.item_id is not None:
            # kind is "made"/"bought" here: PdmDocumentSync never produces a `conflict`
            # sync_state, so a "document" snapshot is never returned by list_conflicts.
            assert snapshot.kind in ("made", "bought")
            await self._set_item_missing(snapshot.kind, snapshot.item_id)
        await self._runs.add_entries(
            run.id,
            [
                PdmSyncRunEntry(
                    id=0,
                    run_id=run.id,
                    vault_id=vault_id,
                    file_id=snapshot.file_id,
                    name=snapshot.name,
                    path=snapshot.path,
                    kind=snapshot.kind,
                    action="missing",
                    item_id=snapshot.item_id,
                    message="file no longer found in PDM",
                    created_at=now_utc(),
                )
            ],
        )
        await self._uow.commit()
        summary.missing += 1

    async def _fetch_by_ids(self, file_ids: list[int]) -> dict[int, PdmObjectInfo]:
        """Current file info for `file_ids`, in batched Web API calls. A file
        PDM no longer returns is absent from the result."""
        found: dict[int, PdmObjectInfo] = {}
        for start in range(0, len(file_ids), _FILES_INFO_BATCH):
            batch = file_ids[start : start + _FILES_INFO_BATCH]

            async def _do(
                gw: IPdmGateway, token: str, ids: list[int] = batch
            ) -> list[PdmObjectInfo]:
                return await gw.files_info(token, ids)

            for obj in await self._session.call(_do):
                found[obj.id] = obj
        return found
