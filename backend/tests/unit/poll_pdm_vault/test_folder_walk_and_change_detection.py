"""
PollPdmVault's own folder walk (resolution, recursion, cycle safety,
per-folder browse failures), plus its change-detection and manual-trigger
re-evaluation rules.
"""

from src.modules.external_data.domain.errors import PdmApiError
from src.modules.external_data.domain.value_objects.pdm_file_sync_state import PdmFileSyncState
from src.modules.external_data.domain.value_objects.pdm_sync_trigger import PdmSyncTrigger
from src.modules.external_data.domain.value_objects.pdm_watched_folder import PdmWatchedFolder
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmConfigVariables
from tests.unit.poll_pdm_vault._helpers import MADE_FOLDER_FLAT
from tests.unit.poll_pdm_vault._helpers import MADE_FOLDER_ID
from tests.unit.poll_pdm_vault._helpers import ROOT_ID
from tests.unit.poll_pdm_vault._helpers import make_folder
from tests.unit.poll_pdm_vault._helpers import make_made_item
from tests.unit.poll_pdm_vault._helpers import make_object
from tests.unit.poll_pdm_vault._helpers import make_pdm_settings
from tests.unit.poll_pdm_vault._helpers import make_snapshot
from tests.unit.poll_pdm_vault.rig import FakeIngest
from tests.unit.poll_pdm_vault.rig import Rig


class TestFolderWalk:
    async def test_recursion_finds_a_nested_file(self) -> None:
        rig = Rig()
        rig.gateway.folders[MADE_FOLDER_ID] = [
            make_folder(id=11, name="Sub", path="\\Made-Parts\\Sub", parent_folder_id=10)
        ]
        rig.gateway.folders[11] = [
            make_object(id=1, path="\\Made-Parts\\Sub\\nested.sldprt", parent_folder_id=11)
        ]

        summary = await rig.use_case.execute()

        assert summary.files_seen == 1
        assert summary.ingested == 1
        assert rig.ingest.calls[0].path == "\\Made-Parts\\Sub\\nested.sldprt"
        # root (10) + the one subfolder (11), not the resolution browse of 1.
        assert summary.folders_walked == 2

    async def test_non_recursive_folder_stops_at_the_root(self) -> None:
        rig = Rig(settings=make_pdm_settings(watched_folders=[MADE_FOLDER_FLAT]))
        rig.gateway.folders[MADE_FOLDER_ID] = [
            make_object(id=1, path="\\Made-Parts\\top.sldprt"),
            make_folder(id=11, name="Sub", path="\\Made-Parts\\Sub", parent_folder_id=10),
        ]
        rig.gateway.folders[11] = [
            make_object(id=2, path="\\Made-Parts\\Sub\\nested.sldprt", parent_folder_id=11)
        ]

        summary = await rig.use_case.execute()

        assert summary.files_seen == 1
        assert 11 not in rig.gateway.browse_calls
        assert summary.folders_walked == 1

    async def test_deleted_file_is_ignored(self) -> None:
        rig = Rig()
        rig.gateway.folders[MADE_FOLDER_ID] = [
            make_object(id=1, path="\\Made-Parts\\gone.sldprt", is_deleted=True),
            make_object(id=2, path="\\Made-Parts\\kept.sldprt"),
        ]

        summary = await rig.use_case.execute()

        assert summary.files_seen == 1
        assert rig.ingest.calls[0].file_id == 2

    async def test_deleted_subfolder_is_not_recursed_into(self) -> None:
        rig = Rig()
        rig.gateway.folders[MADE_FOLDER_ID] = [
            make_folder(
                id=11,
                name="Gone",
                path="\\Made-Parts\\Gone",
                parent_folder_id=10,
                is_deleted=True,
            )
        ]
        rig.gateway.folders[11] = [make_object(id=1, path="\\Made-Parts\\Gone\\x.sldprt")]

        summary = await rig.use_case.execute()

        assert summary.files_seen == 0
        assert 11 not in rig.gateway.browse_calls

    async def test_cycle_is_not_walked_twice(self) -> None:
        rig = Rig()
        rig.gateway.folders[MADE_FOLDER_ID] = [
            make_folder(id=11, name="Sub", path="\\Made-Parts\\Sub", parent_folder_id=10)
        ]
        # Sub's own listing points back at the watched root itself.
        rig.gateway.folders[11] = [
            make_folder(id=10, name="Made-Parts", path="\\Made-Parts", parent_folder_id=1),
            make_object(id=1, path="\\Made-Parts\\Sub\\x.sldprt", parent_folder_id=11),
        ]

        summary = await rig.use_case.execute()

        assert summary.files_seen == 1
        assert rig.gateway.browse_calls.count(10) == 1
        assert summary.folders_walked == 2

    async def test_watched_folder_path_resolves_through_multiple_segments(self) -> None:
        nested = PdmWatchedFolder(
            path="\\Made-Parts\\Sub", kind="made", recursive=True, enabled=True
        )
        rig = Rig(settings=make_pdm_settings(watched_folders=[nested]))
        # \Made-Parts (10) already resolves at the root; register its
        # child "Sub" (11) so the second path segment resolves too.
        rig.gateway.folders[MADE_FOLDER_ID] = [
            make_folder(id=11, name="Sub", path="\\Made-Parts\\Sub", parent_folder_id=10)
        ]
        rig.gateway.folders[11] = [
            make_object(id=1, path="\\Made-Parts\\Sub\\x.sldprt", parent_folder_id=11)
        ]

        summary = await rig.use_case.execute()

        assert summary.files_seen == 1
        # Two resolution browses (root, then 10) plus one walk browse (11);
        # only the walk browse counts toward folders_walked.
        assert rig.gateway.browse_calls == [ROOT_ID, MADE_FOLDER_ID, 11]
        assert summary.folders_walked == 1


class TestFolderIdWalk:
    """A watched folder with a stored `folder_id` still resolves its
    configured path every run. The two agreeing walks quietly; a stored id
    the path no longer leads to, or a path that no longer resolves, is walked
    from whichever still works and recorded as an error entry."""

    async def test_folder_id_matching_its_path_walks_without_an_error(self) -> None:
        with_id = PdmWatchedFolder(
            path="\\Made-Parts",
            kind="made",
            recursive=True,
            enabled=True,
            folder_id=MADE_FOLDER_ID,
        )
        rig = Rig(settings=make_pdm_settings(watched_folders=[with_id]))
        rig.gateway.folders[MADE_FOLDER_ID] = [make_object(id=1, path="\\Made-Parts\\part.sldprt")]

        summary = await rig.use_case.execute()

        assert summary.files_seen == 1
        assert summary.errors == 0
        assert rig.gateway.browse_calls == [ROOT_ID, MADE_FOLDER_ID]

    async def test_recreated_folder_is_walked_by_its_path(self) -> None:
        """The stored id belongs to a folder deleted in PDM and recreated
        under the same path, which the walk must follow."""
        stale_id = PdmWatchedFolder(
            path="\\Made-Parts", kind="made", recursive=True, enabled=True, folder_id=55
        )
        rig = Rig(settings=make_pdm_settings(watched_folders=[stale_id]))
        rig.gateway.folders[MADE_FOLDER_ID] = [make_object(id=1, path="\\Made-Parts\\part.sldprt")]

        summary = await rig.use_case.execute()

        assert summary.files_seen == 1
        assert 55 not in rig.gateway.browse_calls
        assert summary.errors == 1
        run_id = next(iter(rig.run_repo.runs))
        [entry] = [e for e in rig.run_repo.entries[run_id] if e.action == "error"]
        assert "no longer matches the configured path" in entry.message

    async def test_renamed_folder_is_walked_by_its_id_and_flagged(self) -> None:
        renamed = PdmWatchedFolder(
            path="\\OldName", kind="made", recursive=True, enabled=True, folder_id=MADE_FOLDER_ID
        )
        rig = Rig(settings=make_pdm_settings(watched_folders=[renamed]))
        rig.gateway.folders[MADE_FOLDER_ID] = [make_object(id=1, path="\\NewName\\part.sldprt")]

        summary = await rig.use_case.execute()

        assert summary.files_seen == 1
        assert summary.errors == 1
        run_id = next(iter(rig.run_repo.runs))
        [entry] = [e for e in rig.run_repo.entries[run_id] if e.action == "error"]
        assert "configured path no longer resolves" in entry.message

    async def test_folder_id_survives_a_stale_path_for_both_walk_and_attribution(self) -> None:
        """The stored `path` is wrong (as if the folder were renamed in
        PDM after being configured); the walk still finds the folder by
        id, and a snapshot's own parent_folder_id still attributes it
        correctly for the missing sweep."""
        renamed = PdmWatchedFolder(
            path="\\OldName", kind="made", recursive=True, enabled=True, folder_id=MADE_FOLDER_ID
        )
        stale = make_snapshot(
            file_id=99, path="\\OldName\\gone.sldprt", parent_folder_id=MADE_FOLDER_ID
        )
        rig = Rig(settings=make_pdm_settings(watched_folders=[renamed]), snapshots=[stale])
        rig.gateway.folders[MADE_FOLDER_ID] = [make_object(id=1, path="\\NewName\\part.sldprt")]

        summary = await rig.use_case.execute()

        assert summary.files_seen == 1
        assert rig.ingest.calls[0].file_id == 1
        # The stale snapshot (a different file, no longer seen) is still
        # correctly attributed to this folder by id and marked missing.
        assert summary.missing == 1
        row = rig.snapshot_repo.get("V1", 99)
        assert row is not None
        assert row.sync_state == PdmFileSyncState.MISSING.value

    async def test_no_folder_id_falls_back_to_the_name_walk(self) -> None:
        rig = Rig()  # MADE_FOLDER has no folder_id
        rig.gateway.folders[MADE_FOLDER_ID] = [make_object(id=1, path="\\Made-Parts\\part.sldprt")]

        summary = await rig.use_case.execute()

        assert summary.files_seen == 1
        assert rig.gateway.browse_calls == [ROOT_ID, MADE_FOLDER_ID]


class TestWalkErrors:
    async def test_subfolder_browse_error_is_recorded_and_the_walk_continues(self) -> None:
        rig = Rig()
        rig.gateway.folders[MADE_FOLDER_ID] = [
            make_object(id=1, path="\\Made-Parts\\top.sldprt"),
            make_folder(id=11, name="Sub", path="\\Made-Parts\\Sub", parent_folder_id=10),
        ]
        rig.gateway.browse_errors[11] = PdmApiError(
            "PDM call failed with HTTP 500.", status_code=500, body=""
        )

        summary = await rig.use_case.execute()

        assert summary.files_seen == 1  # the direct file was still found
        assert summary.errors == 1
        assert summary.folders_walked == 1  # only the root, not the failed subfolder
        run_id = next(iter(rig.run_repo.runs))
        error_entries = [e for e in rig.run_repo.entries[run_id] if e.action == "error"]
        assert len(error_entries) == 1
        assert "Sub" in error_entries[0].path or "Sub" in error_entries[0].name

    async def test_root_browse_error_skips_the_missing_sweep_for_that_folder(self) -> None:
        stale = make_snapshot(file_id=99, path="\\Made-Parts\\gone.sldprt")
        rig = Rig(snapshots=[stale])
        rig.gateway.browse_errors[MADE_FOLDER_ID] = PdmApiError(
            "PDM call failed with HTTP 500.", status_code=500, body=""
        )

        summary = await rig.use_case.execute()

        assert summary.errors == 1
        assert summary.folders_walked == 0
        assert summary.missing == 0
        row = rig.snapshot_repo.get("V1", 99)
        assert row is not None
        assert row.sync_state != PdmFileSyncState.MISSING.value

    async def test_unresolvable_watched_folder_is_recorded_as_error_and_skips_the_sweep(
        self,
    ) -> None:
        """The watched folder's name no longer exists under its parent at
        all (renamed or deleted in PDM); _resolve_folder_id itself fails,
        before any browse of the folder's own id is even attempted."""
        stale = make_snapshot(file_id=99, path="\\Made-Parts\\gone.sldprt")
        rig = Rig(snapshots=[stale])
        rig.gateway.folders[ROOT_ID] = []  # "Made-Parts" no longer resolves

        summary = await rig.use_case.execute()

        assert summary.errors == 1
        assert summary.missing == 0
        run_id = next(iter(rig.run_repo.runs))
        assert any(e.action == "error" for e in rig.run_repo.entries[run_id])


class TestNewAndUnchanged:
    async def test_new_file_is_ingested(self) -> None:
        rig = Rig()
        rig.gateway.folders[MADE_FOLDER_ID] = [make_object(id=1)]

        summary = await rig.use_case.execute()

        assert summary.files_seen == 1
        assert summary.changed == 1
        assert summary.ingested == 1
        assert len(rig.ingest.calls) == 1
        assert rig.ingest.calls[0].kind == "made"

    async def test_unchanged_file_is_left_entirely_untouched(self) -> None:
        existing = make_snapshot(file_id=1, version=5, state_id=10)
        rig = Rig(snapshots=[existing])
        rig.gateway.folders[MADE_FOLDER_ID] = [make_object(id=1, version=5, state_id=10)]

        summary = await rig.use_case.execute()

        assert summary.files_seen == 1
        assert summary.changed == 0
        assert rig.ingest.calls == []
        assert rig.gateway.variables_calls == []
        assert 1 not in rig.snapshot_repo.written_file_ids

    async def test_missing_file_level_configuration_is_skipped_without_ingest(self) -> None:
        # Every SolidWorks file always carries a file-level "@" card, so a
        # file whose card lacks one is skipped instead of ingested off
        # whichever configuration was returned first ("Default" here).
        rig = Rig()
        rig.gateway.folders[MADE_FOLDER_ID] = [make_object(id=1)]
        rig.gateway.variables[1] = [
            PdmConfigVariables(
                configuration_name="Default", configuration_id=1, variables={"A": "1"}
            )
        ]

        summary = await rig.use_case.execute()

        assert summary.skipped == 1
        assert rig.ingest.calls == []
        row = rig.snapshot_repo.get("V1", 1)
        assert row is not None
        assert row.sync_state == PdmFileSyncState.SKIPPED.value
        assert row.last_error == "no file-level datacard configuration"


class TestChangeDetection:
    async def test_version_bump_triggers_reingest(self) -> None:
        existing = make_snapshot(file_id=1, version=4, state_id=10)
        rig = Rig(snapshots=[existing])
        rig.gateway.folders[MADE_FOLDER_ID] = [make_object(id=1, version=5, state_id=10)]

        summary = await rig.use_case.execute()

        assert summary.changed == 1
        assert len(rig.ingest.calls) == 1

    async def test_state_change_triggers_reingest(self) -> None:
        existing = make_snapshot(file_id=1, version=5, state_id=10)
        rig = Rig(snapshots=[existing])
        rig.gateway.folders[MADE_FOLDER_ID] = [make_object(id=1, version=5, state_id=20)]

        summary = await rig.use_case.execute()

        assert summary.changed == 1
        assert len(rig.ingest.calls) == 1

    async def test_pending_sync_state_triggers_reingest(self) -> None:
        existing = make_snapshot(
            file_id=1, version=5, state_id=10, sync_state=PdmFileSyncState.PENDING
        )
        rig = Rig(snapshots=[existing])
        rig.gateway.folders[MADE_FOLDER_ID] = [make_object(id=1, version=5, state_id=10)]

        summary = await rig.use_case.execute()

        assert summary.changed == 1
        assert len(rig.ingest.calls) == 1

    async def test_error_sync_state_triggers_reingest(self) -> None:
        existing = make_snapshot(
            file_id=1, version=5, state_id=10, sync_state=PdmFileSyncState.ERROR
        )
        rig = Rig(snapshots=[existing])
        rig.gateway.folders[MADE_FOLDER_ID] = [make_object(id=1, version=5, state_id=10)]

        summary = await rig.use_case.execute()

        assert summary.changed == 1
        assert len(rig.ingest.calls) == 1


class TestManualTriggerForcesReevaluation:
    """A MANUAL trigger bypasses the version/state_id/sync_state diff
    entirely, so a file skipped for a settings reason (unmapped identity,
    unwatched folder, non-matching part number pattern) gets a fresh
    ingest attempt without waiting for its PDM version to also change. It
    also bypasses the "reappeared unchanged" shortcut for a missing file
    coming back at the same version."""

    async def test_manual_trigger_reingests_an_unchanged_skipped_file(self) -> None:
        existing = make_snapshot(
            file_id=1, version=5, state_id=10, sync_state=PdmFileSyncState.SKIPPED
        )
        rig = Rig(snapshots=[existing])
        rig.gateway.folders[MADE_FOLDER_ID] = [make_object(id=1, version=5, state_id=10)]

        summary = await rig.use_case.execute(trigger=PdmSyncTrigger.MANUAL)

        assert summary.changed == 1
        assert len(rig.ingest.calls) == 1

    async def test_manual_trigger_reingests_an_unchanged_ingested_file(self) -> None:
        existing = make_snapshot(
            file_id=1, version=5, state_id=10, sync_state=PdmFileSyncState.INGESTED
        )
        rig = Rig(snapshots=[existing])
        rig.gateway.folders[MADE_FOLDER_ID] = [make_object(id=1, version=5, state_id=10)]

        summary = await rig.use_case.execute(trigger=PdmSyncTrigger.MANUAL)

        assert summary.changed == 1
        assert len(rig.ingest.calls) == 1

    async def test_manual_trigger_bypasses_the_reappeared_shortcut(self) -> None:
        existing = make_snapshot(
            file_id=1,
            version=5,
            state_id=10,
            sync_state=PdmFileSyncState.MISSING,
            item_id=42,
        )
        rig = Rig(snapshots=[existing], made_items=[make_made_item(42)])
        rig.gateway.folders[MADE_FOLDER_ID] = [make_object(id=1, version=5, state_id=10)]

        summary = await rig.use_case.execute(trigger=PdmSyncTrigger.MANUAL)

        assert summary.changed == 1
        assert len(rig.ingest.calls) == 1  # full re-ingest, not the "synced" shortcut

    async def test_scheduled_trigger_keeps_the_diff_for_an_unchanged_file(self) -> None:
        existing = make_snapshot(
            file_id=1, version=5, state_id=10, sync_state=PdmFileSyncState.SKIPPED
        )
        rig = Rig(snapshots=[existing])
        rig.gateway.folders[MADE_FOLDER_ID] = [make_object(id=1, version=5, state_id=10)]

        summary = await rig.use_case.execute(trigger=PdmSyncTrigger.SCHEDULED)

        assert summary.changed == 0
        assert rig.ingest.calls == []

    async def test_default_trigger_also_keeps_the_diff(self) -> None:
        existing = make_snapshot(file_id=1, version=5, state_id=10)
        rig = Rig(snapshots=[existing])
        rig.gateway.folders[MADE_FOLDER_ID] = [make_object(id=1, version=5, state_id=10)]

        summary = await rig.use_case.execute()

        assert summary.changed == 0
        assert rig.ingest.calls == []


class TestErrorRecording:
    async def test_error_is_recorded_and_the_run_continues(self) -> None:
        rig = Rig(ingest=FakeIngest(raises={1: RuntimeError("boom")}))
        rig.gateway.folders[MADE_FOLDER_ID] = [
            make_object(id=1, name="bad.sldprt", path="\\Made-Parts\\bad.sldprt"),
            make_object(id=2, name="good.sldprt", path="\\Made-Parts\\good.sldprt"),
        ]

        summary = await rig.use_case.execute()

        assert summary.errors == 1
        assert summary.ingested == 1
        assert len(rig.ingest.calls) == 2  # both files were attempted
        failed_snapshot = rig.snapshot_repo.get("V1", 1)
        assert failed_snapshot is not None
        assert failed_snapshot.sync_state == PdmFileSyncState.ERROR.value
        assert "boom" in (failed_snapshot.last_error or "")

    async def test_ingest_exception_rolls_back_before_the_error_commit(self) -> None:
        """_record_error is the only call site of uow.rollback() in this
        use case, so any rollback the fake records here can only have come
        from that method, and it rolls back before it commits the error;
        see _record_error's own docstring for why."""
        rig = Rig(ingest=FakeIngest(raises={1: RuntimeError("boom")}))
        rig.gateway.folders[MADE_FOLDER_ID] = [make_object(id=1)]

        await rig.use_case.execute()

        assert rig.uow.rollbacks >= 1


class TestUnreadableFiles:
    """403 on file_variables (or an empty-state listing that never gets that
    far) is an expected, transient condition, not a failure; see
    docs/OPERATIONS.md section 8."""

    async def test_403_on_variables_is_recorded_as_skipped(self) -> None:
        rig = Rig()
        rig.gateway.folders[MADE_FOLDER_ID] = [make_object(id=1)]
        rig.gateway.variable_errors[1] = PdmApiError(
            "PDM call failed with HTTP 403.", status_code=403, body=""
        )

        summary = await rig.use_case.execute()

        assert summary.changed == 1
        assert summary.skipped == 1
        assert summary.errors == 0
        assert rig.ingest.calls == []

        row = rig.snapshot_repo.get("V1", 1)
        assert row is not None
        assert row.sync_state == PdmFileSyncState.SKIPPED.value
        assert row.last_error is not None
        assert "not readable" in row.last_error

        run_id = next(iter(rig.run_repo.runs))
        entries = rig.run_repo.entries[run_id]
        assert len(entries) == 1
        assert entries[0].action == "skipped"
        assert entries[0].file_id == 1
        assert "not readable" in entries[0].message

    async def test_empty_state_listing_is_skipped_without_calling_variables(self) -> None:
        rig = Rig()
        rig.gateway.folders[MADE_FOLDER_ID] = [make_object(id=2, state="", state_id=0)]

        summary = await rig.use_case.execute()

        assert summary.skipped == 1
        assert rig.gateway.variables_calls == []
        assert rig.ingest.calls == []

        row = rig.snapshot_repo.get("V1", 2)
        assert row is not None
        assert row.sync_state == PdmFileSyncState.SKIPPED.value
        assert row.last_error is not None
        assert "not readable" in row.last_error

    async def test_500_on_variables_stays_an_error(self) -> None:
        rig = Rig()
        rig.gateway.folders[MADE_FOLDER_ID] = [make_object(id=3)]
        rig.gateway.variable_errors[3] = PdmApiError(
            "PDM call failed with HTTP 500.", status_code=500, body=""
        )

        summary = await rig.use_case.execute()

        assert summary.errors == 1
        assert summary.skipped == 0

        row = rig.snapshot_repo.get("V1", 3)
        assert row is not None
        assert row.sync_state == PdmFileSyncState.ERROR.value
        assert row.last_error is not None

    async def test_skipped_file_with_unchanged_version_is_not_refetched(self) -> None:
        existing = make_snapshot(
            file_id=4, version=5, state_id=10, sync_state=PdmFileSyncState.SKIPPED
        )
        rig = Rig(snapshots=[existing])
        rig.gateway.folders[MADE_FOLDER_ID] = [make_object(id=4, version=5, state_id=10)]

        summary = await rig.use_case.execute()

        assert summary.changed == 0
        assert rig.gateway.variables_calls == []
        assert rig.ingest.calls == []
