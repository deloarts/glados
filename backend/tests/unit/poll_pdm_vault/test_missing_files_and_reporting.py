"""
The set-difference missing sweep, reappearing-file handling, conflict
retry, run summary/poll-status persistence, the sync run log, write-back
(PdmWriteBack), and cold-folder poll cadence.
"""

import contextlib
from datetime import UTC
from datetime import datetime
from datetime import timedelta

from src.modules.catalogue.domain.value_objects.pdm_sync_state import PdmSyncState
from src.modules.external_data.application.dto.pdm_dto import IngestOutcome
from src.modules.external_data.domain.entities.pdm_folder_poll_state import PdmFolderPollState
from src.modules.external_data.domain.entities.pdm_sync_run import SYNC_RUN_RETENTION
from src.modules.external_data.domain.errors import PdmApiError
from src.modules.external_data.domain.services.pdm_poll_cadence import folder_key
from src.modules.external_data.domain.value_objects.pdm_file_sync_state import PdmFileSyncState
from src.modules.external_data.domain.value_objects.pdm_sync_trigger import PdmSyncTrigger
from src.modules.external_data.domain.value_objects.pdm_watched_folder import PdmWatchedFolder
from tests.unit.poll_pdm_vault._helpers import _OUTSIDE_FOLDER_ID
from tests.unit.poll_pdm_vault._helpers import _SUB_FOLDER_ID
from tests.unit.poll_pdm_vault._helpers import BOUGHT_FOLDER
from tests.unit.poll_pdm_vault._helpers import BOUGHT_FOLDER_ID
from tests.unit.poll_pdm_vault._helpers import BY_KIND_FOLDER
from tests.unit.poll_pdm_vault._helpers import BY_KIND_FOLDER_ID
from tests.unit.poll_pdm_vault._helpers import MADE_FOLDER
from tests.unit.poll_pdm_vault._helpers import MADE_FOLDER_ID
from tests.unit.poll_pdm_vault._helpers import WRITE_BACK_VAR_MAP
from tests.unit.poll_pdm_vault._helpers import make_made_item
from tests.unit.poll_pdm_vault._helpers import make_object
from tests.unit.poll_pdm_vault._helpers import make_pdm_settings
from tests.unit.poll_pdm_vault._helpers import make_snapshot
from tests.unit.poll_pdm_vault.rig import FakeGateway
from tests.unit.poll_pdm_vault.rig import FakeIngest
from tests.unit.poll_pdm_vault.rig import Rig


class TestMissingFiles:
    async def test_missing_file_is_marked_via_set_difference(self) -> None:
        existing = make_snapshot(file_id=99, path="\\Made-Parts\\gone.sldprt", item_id=42)
        rig = Rig(snapshots=[existing], made_items=[make_made_item(42)])
        rig.gateway.folders[MADE_FOLDER_ID] = []  # this run's walk finds nothing

        summary = await rig.use_case.execute()

        assert summary.missing == 1
        row = rig.snapshot_repo.get("V1", 99)
        assert row is not None
        assert row.sync_state == PdmFileSyncState.MISSING.value
        assert row.last_error == "file no longer found under \\Made-Parts"
        item = await rig.made_item_repo.get_by_id(42)
        assert item is not None
        assert item.pdm_sync_state == PdmSyncState.MISSING.value

    async def test_a_deleted_subfolders_files_are_no_longer_swept(self) -> None:
        """Attribution is by the snapshot's own `parent_folder_id` against
        the folder ids actually visited this run, not by a path-prefix
        guess. A subfolder that is itself gone from its parent's listing is
        never visited, so it never becomes a `folder_membership` entry
        either, and a file whose parent_folder_id names that vanished
        subfolder is left alone this run, same as a file under a root whose
        own browse failed. A path-prefix guess would sweep this file (its
        stored path still falls under the watched root's own path), but it
        cannot tell a folder rename apart from a genuine move and would
        mis-attribute snapshots across a rename."""
        existing = make_snapshot(
            file_id=1,
            path="\\Made-Parts\\Sub\\gone.sldprt",
            parent_folder_id=_SUB_FOLDER_ID,
            item_id=42,
        )
        rig = Rig(snapshots=[existing], made_items=[make_made_item(42)])
        rig.gateway.folders[MADE_FOLDER_ID] = []  # "Sub" is gone

        summary = await rig.use_case.execute()

        assert summary.missing == 0
        row = rig.snapshot_repo.get("V1", 1)
        assert row is not None
        assert row.sync_state != PdmFileSyncState.MISSING.value

    async def test_by_kind_folder_missing_sweep_matches_by_parent_folder_id(self) -> None:
        existing = make_snapshot(
            file_id=99, kind=None, path="\\Parts\\gone.sldprt", parent_folder_id=BY_KIND_FOLDER_ID
        )
        rig = Rig(
            settings=make_pdm_settings(watched_folders=[BY_KIND_FOLDER]), snapshots=[existing]
        )
        rig.gateway.folders[BY_KIND_FOLDER_ID] = []

        summary = await rig.use_case.execute()

        assert summary.missing == 1
        row = rig.snapshot_repo.get("V1", 99)
        assert row is not None
        assert row.sync_state == PdmFileSyncState.MISSING.value

    async def test_a_file_outside_every_walked_folder_is_never_swept(self) -> None:
        existing = make_snapshot(
            file_id=1, path="\\Other\\thing.sldprt", parent_folder_id=_OUTSIDE_FOLDER_ID
        )
        rig = Rig(snapshots=[existing])
        rig.gateway.folders[MADE_FOLDER_ID] = []

        summary = await rig.use_case.execute()

        assert summary.missing == 0
        row = rig.snapshot_repo.get("V1", 1)
        assert row is not None
        assert row.sync_state != PdmFileSyncState.MISSING.value

    async def test_already_missing_row_is_not_recounted(self) -> None:
        existing = make_snapshot(
            file_id=1,
            path="\\Made-Parts\\gone.sldprt",
            sync_state=PdmFileSyncState.MISSING,
        )
        rig = Rig(snapshots=[existing])
        rig.gateway.folders[MADE_FOLDER_ID] = []

        summary = await rig.use_case.execute()

        assert summary.missing == 0


class TestReappearingMissingFile:
    async def test_same_version_and_state_marks_synced_without_ingest(self) -> None:
        existing = make_snapshot(
            file_id=1,
            path="\\Made-Parts\\part.sldprt",
            version=5,
            state_id=10,
            sync_state=PdmFileSyncState.MISSING,
            item_id=42,
        )
        rig = Rig(snapshots=[existing], made_items=[make_made_item(42)])
        rig.gateway.folders[MADE_FOLDER_ID] = [
            make_object(id=1, path="\\Made-Parts\\part.sldprt", version=5, state_id=10)
        ]

        summary = await rig.use_case.execute()

        assert rig.ingest.calls == []
        assert summary.changed == 1
        assert summary.ingested == 1
        row = rig.snapshot_repo.get("V1", 1)
        assert row is not None
        assert row.sync_state == PdmFileSyncState.INGESTED.value
        item = await rig.made_item_repo.get_by_id(42)
        assert item is not None
        assert item.pdm_sync_state == PdmSyncState.SYNCED.value
        run_id = next(iter(rig.run_repo.runs))
        entries = rig.run_repo.entries[run_id]
        assert len(entries) == 1
        assert entries[0].action == "status"

    async def test_changed_version_re_ingests_normally(self) -> None:
        existing = make_snapshot(
            file_id=1,
            path="\\Made-Parts\\part.sldprt",
            version=5,
            state_id=10,
            sync_state=PdmFileSyncState.MISSING,
            item_id=42,
        )
        rig = Rig(snapshots=[existing], made_items=[make_made_item(42)])
        rig.gateway.folders[MADE_FOLDER_ID] = [
            make_object(id=1, path="\\Made-Parts\\part.sldprt", version=6, state_id=10)
        ]

        await rig.use_case.execute()

        assert len(rig.ingest.calls) == 1
        item = await rig.made_item_repo.get_by_id(42)
        assert item is not None
        assert item.pdm_sync_state is None  # untouched by the poller itself; ingest owns this

    async def test_reappearing_without_a_linked_item_re_ingests_normally(self) -> None:
        existing = make_snapshot(
            file_id=1,
            path="\\Made-Parts\\part.sldprt",
            version=5,
            state_id=10,
            sync_state=PdmFileSyncState.MISSING,
            item_id=None,
        )
        rig = Rig(snapshots=[existing])
        rig.gateway.folders[MADE_FOLDER_ID] = [
            make_object(id=1, path="\\Made-Parts\\part.sldprt", version=5, state_id=10)
        ]

        await rig.use_case.execute()

        assert len(rig.ingest.calls) == 1


class TestConflictRetry:
    async def test_parked_conflict_is_retried_at_end_of_run(self) -> None:
        conflicted = make_snapshot(
            file_id=7,
            sync_state=PdmFileSyncState.CONFLICT,
            path="\\Made-Parts\\c.sldprt",
            version=5,
            state_id=10,
        )
        rig = Rig(snapshots=[conflicted])
        # The conflicted file still exists in PDM (unchanged version/state,
        # so the normal walk does NOT re-queue it; conflict rows are
        # retried only by the dedicated end-of-run step, never by the
        # ordinary changed-file path) and its own files_info lookup (used
        # by the retry) resolves it too.
        rig.gateway.folders[MADE_FOLDER_ID] = [
            make_object(id=7, path="\\Made-Parts\\c.sldprt", version=5, state_id=10)
        ]
        rig.gateway.by_id[7] = make_object(id=7, path="\\Made-Parts\\c.sldprt")

        summary = await rig.use_case.execute()

        assert len(rig.ingest.calls) == 1
        assert rig.ingest.calls[0].file_id == 7
        assert summary.ingested == 1

    async def test_conflict_whose_file_vanished_is_marked_missing(self) -> None:
        # kind="bought" with only MADE_FOLDER enabled (the Rig default) so
        # the folder-level missing sweep never touches this row; this
        # isolates _retry_conflicts' own "file no longer found" branch
        # rather than the ordinary missing sweep catching it first.
        conflicted = make_snapshot(
            file_id=8,
            kind="bought",
            sync_state=PdmFileSyncState.CONFLICT,
            path="\\Bought-Parts\\c.sldprt",
        )
        rig = Rig(snapshots=[conflicted])
        rig.gateway.folders[MADE_FOLDER_ID] = []
        # file 8 is not in gateway.by_id at all -> files_info returns nothing

        summary = await rig.use_case.execute()

        assert rig.ingest.calls == []
        assert summary.missing == 1
        row = rig.snapshot_repo.get("V1", 8)
        assert row is not None
        assert row.sync_state == PdmFileSyncState.MISSING.value

    async def test_retry_reproduces_a_still_unresolved_link_conflict_without_ingest(self) -> None:
        """The bought folder's own root browse fails this run, so the
        ordinary walk never gets a chance to re-examine file 9 itself (and
        the missing sweep skips that folder too); only the dedicated
        retry step, which resolves the file directly by id, sees that it
        is still sitting under the wrong folder and re-parks it rather
        than calling ingest."""
        conflicted = make_snapshot(
            file_id=9,
            kind="made",
            sync_state=PdmFileSyncState.CONFLICT,
            path="\\Bought-Parts\\c.sldprt",
            parent_folder_id=BOUGHT_FOLDER_ID,
            item_id=42,
        )
        rig = Rig(
            settings=make_pdm_settings(watched_folders=[MADE_FOLDER, BOUGHT_FOLDER]),
            snapshots=[conflicted],
        )
        rig.gateway.folders[MADE_FOLDER_ID] = []
        rig.gateway.browse_errors[BOUGHT_FOLDER_ID] = PdmApiError(
            "PDM call failed with HTTP 500.", status_code=500, body=""
        )
        # Still sitting under the bought folder in PDM; the conflict has
        # not actually been resolved yet.
        rig.gateway.by_id[9] = make_object(
            id=9, path="\\Bought-Parts\\c.sldprt", parent_folder_id=BOUGHT_FOLDER_ID
        )

        summary = await rig.use_case.execute()

        assert rig.ingest.calls == []
        assert summary.conflicts == 1
        row = rig.snapshot_repo.get("V1", 9)
        assert row is not None
        assert row.sync_state == PdmFileSyncState.CONFLICT.value


class TestSummaryAndPollStatus:
    async def test_summary_counts_a_mixed_run(self) -> None:
        rig = Rig(
            ingest=FakeIngest(
                outcomes={
                    2: IngestOutcome(action="skipped", item_id=None, message="skip"),
                    3: IngestOutcome(action="conflict", item_id=None, message="conflict"),
                }
            )
        )
        rig.gateway.folders[MADE_FOLDER_ID] = [
            make_object(id=1, path="\\Made-Parts\\a.sldprt"),
            make_object(id=2, path="\\Made-Parts\\b.sldprt"),
            make_object(id=3, path="\\Made-Parts\\c.sldprt"),
        ]

        summary = await rig.use_case.execute()

        assert summary.files_seen == 3
        assert summary.changed == 3
        assert summary.ingested == 1
        assert summary.skipped == 1
        assert summary.conflicts == 1
        assert summary.errors == 0
        assert summary.folders_walked == 1

    async def test_poll_status_is_persisted_on_success(self) -> None:
        rig = Rig()
        rig.gateway.folders[MADE_FOLDER_ID] = [make_object(id=1)]

        await rig.use_case.execute()

        assert len(rig.admin_settings_repo.poll_status_calls) == 1
        _at, error, summary_text = rig.admin_settings_repo.poll_status_calls[0]
        assert error is None
        assert summary_text is not None
        assert "1 files seen" in summary_text
        assert "folders walked" in summary_text

    async def test_poll_status_records_error_on_top_level_failure(self) -> None:
        class BrokenGateway(FakeGateway):
            async def browse_folder(self, token: str, folder_id: int):
                raise RuntimeError("vault unreachable")

        rig = Rig()
        rig.gateway = BrokenGateway()
        rig.rebuild()

        try:
            await rig.use_case.execute()
            raised = False
        except RuntimeError:
            raised = True

        assert raised
        assert len(rig.admin_settings_repo.poll_status_calls) == 1
        _, error, _ = rig.admin_settings_repo.poll_status_calls[0]
        assert error == "vault unreachable"


class TestSyncRunLog:
    async def test_default_trigger_is_scheduled(self) -> None:
        rig = Rig()
        rig.gateway.folders[MADE_FOLDER_ID] = [make_object(id=1)]

        await rig.use_case.execute()

        assert len(rig.run_repo.runs) == 1
        run = next(iter(rig.run_repo.runs.values()))
        assert run.trigger == PdmSyncTrigger.SCHEDULED.value

    async def test_explicit_trigger_is_recorded(self) -> None:
        rig = Rig()
        rig.gateway.folders[MADE_FOLDER_ID] = [make_object(id=1)]

        await rig.use_case.execute(trigger=PdmSyncTrigger.MANUAL)

        run = next(iter(rig.run_repo.runs.values()))
        assert run.trigger == PdmSyncTrigger.MANUAL.value

    async def test_one_entry_per_changed_file(self) -> None:
        rig = Rig()
        rig.gateway.folders[MADE_FOLDER_ID] = [
            make_object(id=1, path="\\Made-Parts\\a.sldprt"),
            make_object(id=2, path="\\Made-Parts\\b.sldprt"),
        ]

        await rig.use_case.execute()

        run_id = next(iter(rig.run_repo.runs))
        entries = rig.run_repo.entries[run_id]
        assert len(entries) == 2
        assert {e.file_id for e in entries} == {1, 2}
        assert all(e.action == "created" for e in entries)
        assert all(e.run_id == run_id for e in entries)

    async def test_unchanged_file_gets_no_entry(self) -> None:
        existing = make_snapshot(file_id=1, version=5, state_id=10)
        rig = Rig(snapshots=[existing])
        rig.gateway.folders[MADE_FOLDER_ID] = [make_object(id=1, version=5, state_id=10)]

        await rig.use_case.execute()

        run_id = next(iter(rig.run_repo.runs))
        assert rig.run_repo.entries[run_id] == []

    async def test_error_produces_an_error_entry(self) -> None:
        rig = Rig(ingest=FakeIngest(raises={1: RuntimeError("boom")}))
        rig.gateway.folders[MADE_FOLDER_ID] = [make_object(id=1)]

        await rig.use_case.execute()

        run_id = next(iter(rig.run_repo.runs))
        entries = rig.run_repo.entries[run_id]
        assert len(entries) == 1
        assert entries[0].action == "error"
        assert "boom" in entries[0].message

    async def test_missing_file_gets_a_missing_entry(self) -> None:
        existing = make_snapshot(file_id=99, path="\\Made-Parts\\gone.sldprt")
        rig = Rig(snapshots=[existing])
        rig.gateway.folders[MADE_FOLDER_ID] = []

        await rig.use_case.execute()

        run_id = next(iter(rig.run_repo.runs))
        entries = rig.run_repo.entries[run_id]
        assert len(entries) == 1
        assert entries[0].action == "missing"
        assert entries[0].file_id == 99

    async def test_conflict_retry_that_reingests_gets_an_entry(self) -> None:
        conflicted = make_snapshot(
            file_id=7,
            sync_state=PdmFileSyncState.CONFLICT,
            path="\\Made-Parts\\c.sldprt",
            version=5,
            state_id=10,
        )
        rig = Rig(snapshots=[conflicted])
        rig.gateway.folders[MADE_FOLDER_ID] = [
            make_object(id=7, path="\\Made-Parts\\c.sldprt", version=5, state_id=10)
        ]
        rig.gateway.by_id[7] = make_object(id=7, path="\\Made-Parts\\c.sldprt")

        await rig.use_case.execute()

        run_id = next(iter(rig.run_repo.runs))
        entries = rig.run_repo.entries[run_id]
        assert len(entries) == 1
        assert entries[0].file_id == 7
        assert entries[0].action == "created"

    async def test_conflict_retry_whose_file_vanished_gets_a_missing_entry(self) -> None:
        conflicted = make_snapshot(
            file_id=8,
            kind="bought",
            sync_state=PdmFileSyncState.CONFLICT,
            path="\\Bought-Parts\\c.sldprt",
        )
        rig = Rig(snapshots=[conflicted])
        rig.gateway.folders[MADE_FOLDER_ID] = []

        await rig.use_case.execute()

        run_id = next(iter(rig.run_repo.runs))
        entries = rig.run_repo.entries[run_id]
        assert len(entries) == 1
        assert entries[0].file_id == 8
        assert entries[0].action == "missing"

    async def test_finish_carries_the_summary_counts(self) -> None:
        rig = Rig(
            ingest=FakeIngest(
                outcomes={2: IngestOutcome(action="skipped", item_id=None, message="skip")}
            )
        )
        rig.gateway.folders[MADE_FOLDER_ID] = [
            make_object(id=1, path="\\Made-Parts\\a.sldprt"),
            make_object(id=2, path="\\Made-Parts\\b.sldprt"),
        ]

        await rig.use_case.execute()

        run_id = next(iter(rig.run_repo.runs))
        run = rig.run_repo.runs[run_id]
        assert run.files_seen == 2
        assert run.changed == 2
        assert run.ingested == 1
        assert run.skipped == 1
        assert run.error is None
        assert run.finished_at is not None
        assert run.folders_walked == 1
        assert rig.run_repo.finished_run_ids == [run_id]
        assert rig.run_repo.prune_calls == [SYNC_RUN_RETENTION]

    async def test_top_level_failure_still_finishes_and_prunes_the_run(self) -> None:
        class BrokenGateway(FakeGateway):
            async def browse_folder(self, token: str, folder_id: int):
                raise RuntimeError("vault unreachable")

        rig = Rig()
        rig.gateway = BrokenGateway()
        rig.rebuild()

        with contextlib.suppress(RuntimeError):
            await rig.use_case.execute()

        run_id = next(iter(rig.run_repo.runs))
        run = rig.run_repo.runs[run_id]
        assert run.error == "vault unreachable"
        assert run.finished_at is not None
        assert rig.run_repo.finished_run_ids == [run_id]
        assert rig.run_repo.prune_calls == [SYNC_RUN_RETENTION]


class TestWriteBack:
    """PdmWriteBack.after_outcome is wired into _ingest_one (success and
    conflict) and into the private-state skip path when the file is
    already linked; see poll_pdm_vault.py's own module docstring. Full
    coverage of PdmWriteBack's own rules lives in test_pdm_writeback.py;
    these tests only prove the wiring (right point in the flow, right
    args, tallied into PollSummary.written_back)."""

    async def test_successful_ingest_triggers_write_back(self) -> None:
        settings = make_pdm_settings(
            writeback_enabled=True, made_item_variable_map=dict(WRITE_BACK_VAR_MAP)
        )
        rig = Rig(settings=settings)
        rig.gateway.folders[MADE_FOLDER_ID] = [make_object(id=1)]

        summary = await rig.use_case.execute()

        assert summary.written_back == 1
        assert rig.gateway.datacard_calls == [1]
        assert len(rig.gateway.set_calls) == 1
        file_id, values = rig.gateway.set_calls[0]
        assert file_id == 1
        assert values["Glados.NewestRevisionSyncState"] == "synced"

    async def test_disabled_by_default_never_calls_the_gateway(self) -> None:
        rig = Rig()  # make_pdm_settings() defaults writeback_enabled=False
        rig.gateway.folders[MADE_FOLDER_ID] = [make_object(id=1)]

        summary = await rig.use_case.execute()

        assert summary.written_back == 0
        assert rig.gateway.datacard_calls == []

    async def test_unlinked_skip_does_not_trigger_write_back(self) -> None:
        settings = make_pdm_settings(
            writeback_enabled=True, made_item_variable_map=dict(WRITE_BACK_VAR_MAP)
        )
        ingest = FakeIngest(
            outcomes={
                1: IngestOutcome(action="skipped", item_id=None, message="identity vars missing")
            }
        )
        rig = Rig(settings=settings, ingest=ingest)
        rig.gateway.folders[MADE_FOLDER_ID] = [make_object(id=1)]

        summary = await rig.use_case.execute()

        assert summary.written_back == 0
        assert rig.gateway.datacard_calls == []

    async def test_conflict_outcome_on_a_linked_item_triggers_write_back(self) -> None:
        settings = make_pdm_settings(
            writeback_enabled=True, made_item_variable_map=dict(WRITE_BACK_VAR_MAP)
        )
        ingest = FakeIngest(
            outcomes={
                1: IngestOutcome(action="conflict", item_id=1, message="manufacturer unresolved")
            }
        )
        rig = Rig(settings=settings, ingest=ingest)
        rig.gateway.folders[MADE_FOLDER_ID] = [make_object(id=1)]

        summary = await rig.use_case.execute()

        assert summary.written_back == 1
        _, values = rig.gateway.set_calls[0]
        assert values["Glados.NewestRevisionSyncState"] == "conflict: manufacturer unresolved"

    async def test_private_state_skip_of_a_linked_file_triggers_write_back(self) -> None:
        existing = make_snapshot(file_id=1, state_id=10, item_id=42, kind="made")
        settings = make_pdm_settings(
            writeback_enabled=True, made_item_variable_map=dict(WRITE_BACK_VAR_MAP)
        )
        rig = Rig(settings=settings, snapshots=[existing])
        rig.gateway.folders[MADE_FOLDER_ID] = [make_object(id=1, state="", state_id=0)]

        summary = await rig.use_case.execute()

        assert summary.skipped == 1
        assert summary.written_back == 1
        assert rig.gateway.datacard_calls == [1]

    async def test_private_state_skip_of_an_unlinked_file_does_not_trigger_write_back(self) -> None:
        settings = make_pdm_settings(
            writeback_enabled=True, made_item_variable_map=dict(WRITE_BACK_VAR_MAP)
        )
        rig = Rig(settings=settings)
        rig.gateway.folders[MADE_FOLDER_ID] = [make_object(id=1, state="", state_id=0)]

        summary = await rig.use_case.execute()

        assert summary.skipped == 1
        assert summary.written_back == 0
        assert rig.gateway.datacard_calls == []


class TestColdFolderCadence:
    """Per-folder cadence (domain.services.pdm_poll_cadence): a folder with
    no changes across consecutive scheduled runs is walked less often,
    capped by AdminPdmSettings.cold_folder_max_multiplier; any change, or a
    manual/initial run, ignores or resets that state."""

    def _make_state(
        self,
        *,
        folder: PdmWatchedFolder = MADE_FOLDER,
        consecutive_unchanged_runs: int = 0,
        next_due_at: datetime | None = None,
    ) -> PdmFolderPollState:
        now = datetime.now(UTC)
        return PdmFolderPollState(
            id=1,
            vault_id="V1",
            folder_key=folder_key(folder),
            consecutive_unchanged_runs=consecutive_unchanged_runs,
            next_due_at=next_due_at,
            last_changed_at=None,
            updated_at=now,
        )

    async def test_scheduled_run_skips_a_cold_folder(self) -> None:
        future = datetime.now(UTC) + timedelta(hours=1)
        state = self._make_state(consecutive_unchanged_runs=2, next_due_at=future)
        rig = Rig(folder_poll_states=[state])
        rig.gateway.folders[MADE_FOLDER_ID] = [make_object(id=1)]

        summary = await rig.use_case.execute(trigger=PdmSyncTrigger.SCHEDULED)

        assert summary.folders_skipped_cold == 1
        assert summary.folders_walked == 0
        assert summary.files_seen == 0
        assert rig.gateway.browse_calls == []
        run = next(iter(rig.run_repo.runs.values()))
        assert run.folders_skipped_cold == 1

    async def test_walked_folder_with_no_changes_advances_its_backoff(self) -> None:
        existing = make_snapshot(file_id=1, version=5, state_id=10)
        rig = Rig(snapshots=[existing])
        rig.gateway.folders[MADE_FOLDER_ID] = [make_object(id=1, version=5, state_id=10)]

        summary = await rig.use_case.execute(trigger=PdmSyncTrigger.SCHEDULED)

        assert summary.changed == 0
        assert summary.folders_skipped_cold == 0
        state = rig.folder_poll_state_repo.get("V1", folder_key(MADE_FOLDER))
        assert state is not None
        assert state.consecutive_unchanged_runs == 1
        assert state.next_due_at is not None
        assert state.next_due_at > datetime.now(UTC)

    async def test_a_change_under_a_folder_resets_its_cadence_state(self) -> None:
        stale = self._make_state(consecutive_unchanged_runs=3, next_due_at=None)
        rig = Rig(folder_poll_states=[stale])
        rig.gateway.folders[MADE_FOLDER_ID] = [make_object(id=1)]  # a new file: a change

        summary = await rig.use_case.execute(trigger=PdmSyncTrigger.SCHEDULED)

        assert summary.changed == 1
        state = rig.folder_poll_state_repo.get("V1", folder_key(MADE_FOLDER))
        assert state is not None
        assert state.consecutive_unchanged_runs == 0
        assert state.next_due_at is None

    async def test_a_missing_file_resets_its_folder(self) -> None:
        stale = self._make_state(consecutive_unchanged_runs=3, next_due_at=None)
        existing = make_snapshot(file_id=99, path="\\Made-Parts\\gone.sldprt")
        rig = Rig(snapshots=[existing], folder_poll_states=[stale])
        rig.gateway.folders[MADE_FOLDER_ID] = []  # the file is gone this run

        summary = await rig.use_case.execute(trigger=PdmSyncTrigger.SCHEDULED)

        assert summary.missing == 1
        state = rig.folder_poll_state_repo.get("V1", folder_key(MADE_FOLDER))
        assert state is not None
        assert state.consecutive_unchanged_runs == 0
        assert state.next_due_at is None

    async def test_manual_run_walks_a_cold_folder_and_never_touches_its_cadence(self) -> None:
        future = datetime.now(UTC) + timedelta(hours=1)
        state = self._make_state(consecutive_unchanged_runs=2, next_due_at=future)
        rig = Rig(folder_poll_states=[state])
        rig.gateway.folders[MADE_FOLDER_ID] = [make_object(id=1)]

        summary = await rig.use_case.execute(trigger=PdmSyncTrigger.MANUAL)

        assert summary.folders_skipped_cold == 0
        assert summary.files_seen == 1
        untouched = rig.folder_poll_state_repo.get("V1", folder_key(MADE_FOLDER))
        assert untouched is not None
        assert untouched.consecutive_unchanged_runs == 2
        assert untouched.next_due_at == future

    async def test_initial_run_walks_a_cold_folder(self) -> None:
        future = datetime.now(UTC) + timedelta(hours=1)
        state = self._make_state(consecutive_unchanged_runs=2, next_due_at=future)
        rig = Rig(folder_poll_states=[state])
        rig.gateway.folders[MADE_FOLDER_ID] = [make_object(id=1)]

        summary = await rig.use_case.execute(trigger=PdmSyncTrigger.INITIAL)

        assert summary.folders_skipped_cold == 0
        assert summary.files_seen == 1
