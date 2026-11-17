"""
Unit tests for the pure, repository-free category helpers behind
ReconcilePdmVault (application.services.pdm_reconciliation). No database,
no HTTP, no fakes needed for a repository: every function here takes
plain domain entities and CadRowRef instances and returns
ReconciliationFinding rows, so these tests build that data directly.
"""

from datetime import UTC
from datetime import datetime
from datetime import timedelta

import pytest

from src.modules.catalogue.domain.entities.part_number_registry import PartNumberRegistryEntry
from src.modules.catalogue.domain.value_objects.item_kind import ItemKind
from src.modules.external_data.application.services.pdm_reconciliation import CadRowRef
from src.modules.external_data.application.services.pdm_reconciliation import find_document_missing
from src.modules.external_data.application.services.pdm_reconciliation import (
    find_document_unmatched,
)
from src.modules.external_data.application.services.pdm_reconciliation import (
    find_duplicate_snapshot_part_numbers,
)
from src.modules.external_data.application.services.pdm_reconciliation import (
    find_items_without_registry_entry,
)
from src.modules.external_data.application.services.pdm_reconciliation import find_kind_mismatches
from src.modules.external_data.application.services.pdm_reconciliation import find_orphaned_cad_rows
from src.modules.external_data.application.services.pdm_reconciliation import (
    find_orphaned_registry_entries,
)
from src.modules.external_data.application.services.pdm_reconciliation import find_part_number_drift
from src.modules.external_data.application.services.pdm_reconciliation import (
    find_replaced_without_successor,
)
from src.modules.external_data.application.services.pdm_reconciliation import find_revision_lag
from src.modules.external_data.application.services.pdm_reconciliation import find_status_mismatches
from src.modules.external_data.application.services.pdm_reconciliation import find_stuck_files
from src.modules.external_data.application.services.pdm_reconciliation import (
    find_successor_without_replaced,
)
from src.modules.external_data.application.services.pdm_reconciliation import (
    index_snapshots_by_file,
)
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.entities.pdm_document_link import PdmDocumentLink
from src.modules.external_data.domain.entities.pdm_file_snapshot import PdmFileSnapshot
from src.modules.external_data.domain.value_objects.pdm_file_sync_state import PdmFileSyncState
from src.modules.external_data.domain.value_objects.pdm_reconciliation_category import (
    PdmReconciliationCategory,
)

NOW = datetime(2026, 9, 5, 12, 0, 0, tzinfo=UTC)


def make_snapshot(
    *,
    vault_id: str = "V1",
    file_id: int,
    kind: str | None = "made",
    version: int = 5,
    state_id: int = 10,
    sync_state: PdmFileSyncState = PdmFileSyncState.INGESTED,
    last_seen_at: datetime = NOW,
    last_error: str | None = None,
    item_id: int | None = None,
    part_number: str | None = "CAD-1",
    parked_payload: dict[str, str] | None = None,
) -> PdmFileSnapshot:
    return PdmFileSnapshot(
        id=1,
        vault_id=vault_id,
        file_id=file_id,
        kind=kind,
        name="part.sldprt",
        path="\\Made-Parts\\part.sldprt",
        parent_folder_id=1,
        version=version,
        state_id=state_id,
        state="Released",
        modified_at=None,
        first_seen_at=NOW,
        last_seen_at=last_seen_at,
        last_ingested_version=version,
        sync_state=sync_state,
        last_error=last_error,
        part_number=part_number,
        revision="A",
        item_id=item_id,
        parked_payload=parked_payload,
    )


def make_row(
    *,
    item_id: int = 1,
    kind: str = "made",
    vault_id: str | None = "V1",
    pdm_file_id: int | None = 100,
    pdm_file_version: int | None = 5,
    part_number: str | None = "CAD-1",
    revision: str | None = "A",
    status: str = "active",
    successor_item_id: int | None = None,
) -> CadRowRef:
    return CadRowRef(
        item_id=item_id,
        kind=kind,
        vault_id=vault_id,
        pdm_file_id=pdm_file_id,
        pdm_file_version=pdm_file_version,
        part_number=part_number,
        revision=revision,
        status=status,
        successor_item_id=successor_item_id,
    )


def make_settings(
    *,
    made_released_state_ids: list[int] | None = None,
    made_obsolete_state_ids: list[int] | None = None,
    made_replaced_state_ids: list[int] | None = None,
    bought_released_state_ids: list[int] | None = None,
    bought_obsolete_state_ids: list[int] | None = None,
    bought_replaced_state_ids: list[int] | None = None,
) -> AdminPdmSettings:
    """Minimal AdminPdmSettings for find_status_mismatches, which only
    reads the released/obsolete/replaced state id lists per kind."""
    return AdminPdmSettings(
        id=1,
        made_item_variable_map={},
        bought_item_variable_map={},
        enabled=True,
        base_url="http://pdm.example.local:65453",
        vault_name="MainVault",
        username="svc-glados",
        password="secret",
        verify_certificate=True,
        timeout_seconds=15,
        session_token=None,
        session_user_id=None,
        session_obtained_at=None,
        watched_folders=[],
        made_released_state_ids=made_released_state_ids
        if made_released_state_ids is not None
        else [10],
        made_obsolete_state_ids=made_obsolete_state_ids
        if made_obsolete_state_ids is not None
        else [20],
        made_replaced_state_ids=made_replaced_state_ids
        if made_replaced_state_ids is not None
        else [30],
        bought_released_state_ids=(
            bought_released_state_ids if bought_released_state_ids is not None else [10]
        ),
        bought_obsolete_state_ids=(
            bought_obsolete_state_ids if bought_obsolete_state_ids is not None else [20]
        ),
        bought_replaced_state_ids=(
            bought_replaced_state_ids if bought_replaced_state_ids is not None else [30]
        ),
        poll_interval_minutes=15,
        vault_id="V1",
        cad_items_read_only=True,
        last_poll_at=None,
        last_poll_error=None,
        last_poll_summary=None,
        writeback_enabled=False,
        made_item_extensions=["sldprt"],
        bought_item_extensions=["sldprt", "sldasm"],
        document_categories={},
        thumbnails_enabled=False,
        stuck_after_days=7,
        reconcile_requested_deep=None,
        required_fields={"made": [], "bought": []},
    )


class TestFindOrphanedCadRows:
    def test_no_file_id_is_orphaned(self):
        row = make_row(pdm_file_id=None)
        findings = find_orphaned_cad_rows([row], {})
        assert len(findings) == 1
        assert findings[0].category == PdmReconciliationCategory.ORPHANED_CAD_ROW.value
        assert findings[0].message == "CAD item has no linked PDM file id"

    def test_missing_snapshot_is_orphaned(self):
        row = make_row(pdm_file_id=100)
        findings = find_orphaned_cad_rows([row], {})
        assert len(findings) == 1
        assert "no snapshot found" in findings[0].message

    def test_missing_sync_state_is_orphaned(self):
        row = make_row(pdm_file_id=100)
        snapshot = make_snapshot(file_id=100, sync_state=PdmFileSyncState.MISSING)
        findings = find_orphaned_cad_rows([row], index_snapshots_by_file([snapshot]))
        assert len(findings) == 1
        assert "is missing" in findings[0].message

    def test_healthy_row_is_not_orphaned(self):
        row = make_row(pdm_file_id=100)
        snapshot = make_snapshot(file_id=100, sync_state=PdmFileSyncState.INGESTED)
        findings = find_orphaned_cad_rows([row], index_snapshots_by_file([snapshot]))
        assert findings == []

    def test_file_id_without_vault_id_is_reported_as_data_inconsistency(self, glados_caplog):
        # pdm_file_id set with vault_id None must never be
        # looked up with an empty-string vault_id key. It is its own
        # distinct, logged finding.
        row = make_row(pdm_file_id=100, vault_id=None)
        snapshot = make_snapshot(vault_id="", file_id=100)

        findings = find_orphaned_cad_rows([row], index_snapshots_by_file([snapshot]))

        assert len(findings) == 1
        assert "data inconsistency" in findings[0].message
        assert any("data inconsistency" in r.message for r in glados_caplog.records)


class TestFindRevisionLag:
    def test_snapshot_ahead_of_item(self):
        row = make_row(pdm_file_id=100, pdm_file_version=3)
        snapshot = make_snapshot(file_id=100, version=5)
        findings = find_revision_lag([row], index_snapshots_by_file([snapshot]))
        assert len(findings) == 1
        assert "PDM file is at version 5" in findings[0].message

    def test_item_ahead_of_snapshot(self):
        row = make_row(pdm_file_id=100, pdm_file_version=9)
        snapshot = make_snapshot(file_id=100, version=5)
        findings = find_revision_lag([row], index_snapshots_by_file([snapshot]))
        assert len(findings) == 1
        assert "ahead of the PDM" in findings[0].message

    def test_matching_versions_no_finding(self):
        row = make_row(pdm_file_id=100, pdm_file_version=5)
        snapshot = make_snapshot(file_id=100, version=5)
        findings = find_revision_lag([row], index_snapshots_by_file([snapshot]))
        assert findings == []

    def test_no_file_id_skipped(self):
        row = make_row(pdm_file_id=None)
        assert find_revision_lag([row], {}) == []

    def test_file_id_without_vault_id_is_skipped_and_logged(self, glados_caplog):
        row = make_row(pdm_file_id=100, vault_id=None, pdm_file_version=3)
        snapshot = make_snapshot(vault_id="", file_id=100, version=5)

        findings = find_revision_lag([row], index_snapshots_by_file([snapshot]))

        assert findings == []
        assert any("data inconsistency" in r.message for r in glados_caplog.records)


class TestFindKindMismatches:
    def test_mismatch_reported(self):
        row = make_row(pdm_file_id=100, kind="made")
        snapshot = make_snapshot(file_id=100, kind="bought")
        findings = find_kind_mismatches([row], index_snapshots_by_file([snapshot]))
        assert len(findings) == 1
        assert findings[0].severity == "error"

    def test_matching_kind_no_finding(self):
        row = make_row(pdm_file_id=100, kind="made")
        snapshot = make_snapshot(file_id=100, kind="made")
        findings = find_kind_mismatches([row], index_snapshots_by_file([snapshot]))
        assert findings == []

    def test_unresolved_snapshot_kind_no_finding(self):
        row = make_row(pdm_file_id=100, kind="made")
        snapshot = make_snapshot(file_id=100, kind=None)
        findings = find_kind_mismatches([row], index_snapshots_by_file([snapshot]))
        assert findings == []

    def test_file_id_without_vault_id_is_skipped_and_logged(self, glados_caplog):
        row = make_row(pdm_file_id=100, vault_id=None, kind="made")
        snapshot = make_snapshot(vault_id="", file_id=100, kind="bought")

        findings = find_kind_mismatches([row], index_snapshots_by_file([snapshot]))

        assert findings == []
        assert any("data inconsistency" in r.message for r in glados_caplog.records)


class TestFindStatusMismatches:
    def test_active_status_matches_released_state_no_finding(self):
        row = make_row(pdm_file_id=100, kind="made", status="active")
        snapshot = make_snapshot(file_id=100, state_id=10)
        findings = find_status_mismatches(
            [row], index_snapshots_by_file([snapshot]), make_settings()
        )
        assert findings == []

    def test_active_status_but_obsolete_state_is_a_mismatch(self):
        row = make_row(pdm_file_id=100, kind="made", status="active")
        snapshot = make_snapshot(file_id=100, state_id=20)
        findings = find_status_mismatches(
            [row], index_snapshots_by_file([snapshot]), make_settings()
        )
        assert len(findings) == 1
        assert findings[0].category == "status_mismatch"
        assert findings[0].severity == "warning"

    def test_replaced_status_but_released_state_is_a_mismatch(self):
        row = make_row(pdm_file_id=100, kind="made", status="replaced")
        snapshot = make_snapshot(file_id=100, state_id=10)
        findings = find_status_mismatches(
            [row], index_snapshots_by_file([snapshot]), make_settings()
        )
        assert len(findings) == 1

    def test_state_outside_every_list_is_ignored(self):
        row = make_row(pdm_file_id=100, kind="made", status="active")
        snapshot = make_snapshot(file_id=100, state_id=999)
        findings = find_status_mismatches(
            [row], index_snapshots_by_file([snapshot]), make_settings()
        )
        assert findings == []

    def test_no_pdm_file_id_is_skipped(self):
        row = make_row(pdm_file_id=None, kind="made", status="active")
        findings = find_status_mismatches([row], {}, make_settings())
        assert findings == []

    def test_no_snapshot_is_skipped(self):
        row = make_row(pdm_file_id=100, kind="made", status="active")
        findings = find_status_mismatches([row], {}, make_settings())
        assert findings == []

    def test_checked_against_the_rows_own_kind(self):
        # A made state_id watched as bought-released only never implies a
        # status for a made row.
        row = make_row(pdm_file_id=100, kind="made", status="active")
        snapshot = make_snapshot(file_id=100, state_id=10)
        settings = make_settings(made_released_state_ids=[], bought_released_state_ids=[10])
        findings = find_status_mismatches([row], index_snapshots_by_file([snapshot]), settings)
        assert findings == []


class TestFindReplacedWithoutSuccessor:
    def test_replaced_with_no_successor_is_a_finding(self):
        row = make_row(status="replaced", successor_item_id=None)
        findings = find_replaced_without_successor([row])
        assert len(findings) == 1
        assert findings[0].category == "replaced_without_successor"

    def test_replaced_with_a_successor_is_not_a_finding(self):
        row = make_row(status="replaced", successor_item_id=5)
        assert find_replaced_without_successor([row]) == []

    def test_non_replaced_status_is_never_a_finding(self):
        row = make_row(status="active", successor_item_id=None)
        assert find_replaced_without_successor([row]) == []


class TestFindSuccessorWithoutReplaced:
    def test_successor_set_but_not_replaced_is_a_finding(self):
        row = make_row(status="active", successor_item_id=5)
        findings = find_successor_without_replaced([row])
        assert len(findings) == 1
        assert findings[0].category == "successor_without_replaced"

    def test_successor_set_and_replaced_is_not_a_finding(self):
        row = make_row(status="replaced", successor_item_id=5)
        assert find_successor_without_replaced([row]) == []

    def test_no_successor_is_never_a_finding(self):
        row = make_row(status="active", successor_item_id=None)
        assert find_successor_without_replaced([row]) == []


class TestFindPartNumberDrift:
    def test_made_item_drift_is_reported(self):
        row = make_row(pdm_file_id=100, kind="made", part_number="OLD-1")
        snapshot = make_snapshot(file_id=100, part_number="NEW-1")
        findings = find_part_number_drift([row], index_snapshots_by_file([snapshot]))
        assert len(findings) == 1
        assert findings[0].category == PdmReconciliationCategory.PART_NUMBER_DRIFT.value
        assert findings[0].severity == "warning"
        assert findings[0].part_number == "OLD-1"
        assert findings[0].count == 1

    def test_bought_item_drift_is_reported(self):
        row = make_row(pdm_file_id=100, kind="bought", revision=None, part_number="OLD-B")
        snapshot = make_snapshot(file_id=100, kind="bought", part_number="NEW-B")
        findings = find_part_number_drift([row], index_snapshots_by_file([snapshot]))
        assert len(findings) == 1
        assert findings[0].kind == "bought"

    def test_equal_part_numbers_no_finding(self):
        row = make_row(pdm_file_id=100, part_number="SAME-1")
        snapshot = make_snapshot(file_id=100, part_number="SAME-1")
        findings = find_part_number_drift([row], index_snapshots_by_file([snapshot]))
        assert findings == []

    def test_unlinked_row_skipped(self):
        row = make_row(pdm_file_id=None)
        assert find_part_number_drift([row], {}) == []

    def test_snapshot_without_part_number_skipped(self):
        row = make_row(pdm_file_id=100, part_number="OLD-1")
        snapshot = make_snapshot(file_id=100, part_number=None)
        findings = find_part_number_drift([row], index_snapshots_by_file([snapshot]))
        assert findings == []

    def test_made_family_of_three_rows_gives_exactly_one_finding(self):
        rows = [
            make_row(item_id=1, pdm_file_id=100, part_number="OLD-1", revision="A"),
            make_row(item_id=2, pdm_file_id=100, part_number="OLD-1", revision="B"),
            make_row(item_id=3, pdm_file_id=100, part_number="OLD-1", revision="C"),
        ]
        snapshot = make_snapshot(file_id=100, part_number="NEW-1")
        findings = find_part_number_drift(rows, index_snapshots_by_file([snapshot]))
        assert len(findings) == 1
        assert findings[0].item_id == 1  # first row of the family, not re-sorted
        assert findings[0].count == 3

    def test_whitespace_only_difference_is_not_drift(self):
        row = make_row(pdm_file_id=100, part_number="  SAME-1  ")
        snapshot = make_snapshot(file_id=100, part_number="SAME-1")
        findings = find_part_number_drift([row], index_snapshots_by_file([snapshot]))
        assert findings == []

    def test_file_id_without_vault_id_is_skipped_and_logged(self, glados_caplog):
        row = make_row(pdm_file_id=100, vault_id=None, part_number="OLD-1")
        snapshot = make_snapshot(vault_id="", file_id=100, part_number="NEW-1")

        findings = find_part_number_drift([row], index_snapshots_by_file([snapshot]))

        assert findings == []
        assert any("data inconsistency" in r.message for r in glados_caplog.records)


class TestFindStuckFiles:
    def test_stuck_snapshot_older_than_threshold_is_reported(self):
        old = NOW - timedelta(days=10)
        snapshot = make_snapshot(file_id=1, sync_state=PdmFileSyncState.PENDING, last_seen_at=old)
        findings = find_stuck_files([snapshot], stuck_after_days=7, now=NOW)
        assert len(findings) == 1
        assert findings[0].count == 1
        assert findings[0].message == "stuck in pending"

    def test_recent_snapshot_not_reported(self):
        recent = NOW - timedelta(days=1)
        snapshot = make_snapshot(
            file_id=1, sync_state=PdmFileSyncState.PENDING, last_seen_at=recent
        )
        assert find_stuck_files([snapshot], stuck_after_days=7, now=NOW) == []

    def test_ingested_snapshot_never_stuck(self):
        old = NOW - timedelta(days=100)
        snapshot = make_snapshot(file_id=1, sync_state=PdmFileSyncState.INGESTED, last_seen_at=old)
        assert find_stuck_files([snapshot], stuck_after_days=7, now=NOW) == []

    @pytest.mark.parametrize(
        "reason",
        [
            "state not watched",
            "not readable for the PDM user (private state or missing read permission)",
            "dismissed by admin",
        ],
    )
    def test_deliberate_skip_is_not_stuck(self, reason):
        old = NOW - timedelta(days=30)
        snapshot = make_snapshot(
            file_id=1,
            sync_state=PdmFileSyncState.SKIPPED,
            last_error=reason,
            last_seen_at=old,
        )
        assert find_stuck_files([snapshot], stuck_after_days=7, now=NOW) == []

    def test_skip_for_a_data_problem_is_still_stuck(self):
        old = NOW - timedelta(days=30)
        snapshot = make_snapshot(
            file_id=1,
            sync_state=PdmFileSyncState.SKIPPED,
            last_error="identity variables missing",
            last_seen_at=old,
        )
        assert len(find_stuck_files([snapshot], stuck_after_days=7, now=NOW)) == 1

    def test_documents_are_left_to_the_unmatched_category(self):
        old = NOW - timedelta(days=30)
        snapshot = make_snapshot(
            file_id=1,
            kind="document",
            sync_state=PdmFileSyncState.SKIPPED,
            last_error="no matching item",
            last_seen_at=old,
        )
        assert find_stuck_files([snapshot], stuck_after_days=7, now=NOW) == []

    def test_aggregates_one_row_per_reason_and_kind(self):
        old = NOW - timedelta(days=10)
        snapshots = [
            make_snapshot(
                file_id=1,
                kind="made",
                sync_state=PdmFileSyncState.ERROR,
                last_error="boom",
                last_seen_at=old,
            ),
            make_snapshot(
                file_id=2,
                kind="made",
                sync_state=PdmFileSyncState.ERROR,
                last_error="boom",
                last_seen_at=old,
            ),
            make_snapshot(
                file_id=3,
                kind="bought",
                sync_state=PdmFileSyncState.ERROR,
                last_error="boom",
                last_seen_at=old,
            ),
        ]
        findings = find_stuck_files(snapshots, stuck_after_days=7, now=NOW)
        assert len(findings) == 2  # (boom, made) and (boom, bought)
        by_kind = {f.kind: f.count for f in findings}
        assert by_kind == {"made": 2, "bought": 1}
        for f in findings:
            assert f.item_id is None
            assert f.file_id is None


class TestFindDuplicateSnapshotPartNumbers:
    def test_two_files_sharing_a_part_number(self):
        snapshots = [
            make_snapshot(file_id=1, part_number="DUP-1"),
            make_snapshot(file_id=2, part_number="DUP-1"),
        ]
        findings = find_duplicate_snapshot_part_numbers(snapshots)
        assert len(findings) == 1
        assert findings[0].count == 2
        assert findings[0].part_number == "DUP-1"

    def test_unique_part_numbers_no_finding(self):
        snapshots = [
            make_snapshot(file_id=1, part_number="A"),
            make_snapshot(file_id=2, part_number="B"),
        ]
        assert find_duplicate_snapshot_part_numbers(snapshots) == []

    def test_blank_part_number_ignored(self):
        snapshots = [
            make_snapshot(file_id=1, part_number=None),
            make_snapshot(file_id=2, part_number=None),
        ]
        assert find_duplicate_snapshot_part_numbers(snapshots) == []


class TestFindOrphanedRegistryEntries:
    def test_entry_with_no_live_item_is_reported(self):
        entry = PartNumberRegistryEntry(part_number="X-1", kind=ItemKind.MADE, created=NOW.date())
        findings = find_orphaned_registry_entries(
            [entry], live_made_part_numbers=frozenset(), live_bought_part_numbers=frozenset()
        )
        assert len(findings) == 1
        assert findings[0].severity == "info"

    def test_entry_with_live_item_not_reported(self):
        entry = PartNumberRegistryEntry(part_number="X-1", kind=ItemKind.MADE, created=NOW.date())
        findings = find_orphaned_registry_entries(
            [entry],
            live_made_part_numbers=frozenset({"X-1"}),
            live_bought_part_numbers=frozenset(),
        )
        assert findings == []


class TestFindItemsWithoutRegistryEntry:
    def test_unregistered_item_is_reported(self):
        row = make_row(part_number="X-1")
        findings = find_items_without_registry_entry([row], {})
        assert len(findings) == 1
        assert findings[0].message == "item has no registry entry"

    def test_registered_under_other_kind_is_reported(self):
        row = make_row(part_number="X-1", kind="made")
        findings = find_items_without_registry_entry([row], {"X-1": "bought"})
        assert len(findings) == 1
        assert "registered to" in findings[0].message

    def test_registered_under_same_kind_not_reported(self):
        row = make_row(part_number="X-1", kind="made")
        assert find_items_without_registry_entry([row], {"X-1": "made"}) == []

    def test_blank_part_number_skipped(self):
        row = make_row(part_number=None)
        assert find_items_without_registry_entry([row], {}) == []


class TestFindDocumentMissing:
    def test_missing_snapshot_reported(self):
        link = PdmDocumentLink(
            id=1,
            kind=ItemKind.MADE,
            item_id=1,
            item_file_id=1,
            vault_id="V1",
            file_id=200,
            version=1,
        )
        findings = find_document_missing([link], {})
        assert len(findings) == 1
        assert "no snapshot found" in findings[0].message

    def test_missing_sync_state_reported(self):
        link = PdmDocumentLink(
            id=1,
            kind=ItemKind.MADE,
            item_id=1,
            item_file_id=1,
            vault_id="V1",
            file_id=200,
            version=1,
        )
        snapshot = make_snapshot(file_id=200, kind="document", sync_state=PdmFileSyncState.MISSING)
        findings = find_document_missing([link], index_snapshots_by_file([snapshot]))
        assert len(findings) == 1
        assert findings[0].message == "linked document is missing"

    def test_present_snapshot_not_reported(self):
        link = PdmDocumentLink(
            id=1,
            kind=ItemKind.MADE,
            item_id=1,
            item_file_id=1,
            vault_id="V1",
            file_id=200,
            version=1,
        )
        snapshot = make_snapshot(file_id=200, kind="document", sync_state=PdmFileSyncState.INGESTED)
        findings = find_document_missing([link], index_snapshots_by_file([snapshot]))
        assert findings == []


class TestFindDocumentUnmatched:
    def test_unmatched_documents_aggregated_by_reason(self):
        snapshots = [
            make_snapshot(
                file_id=1,
                kind="document",
                item_id=None,
                sync_state=PdmFileSyncState.SKIPPED,
                last_error="no matching item",
            ),
            make_snapshot(
                file_id=2,
                kind="document",
                item_id=None,
                sync_state=PdmFileSyncState.SKIPPED,
                last_error="no matching item",
            ),
        ]
        findings = find_document_unmatched(snapshots)
        assert len(findings) == 1
        assert findings[0].count == 2
        assert findings[0].kind == "document"

    def test_document_waiting_for_a_released_state_not_reported(self):
        snapshot = make_snapshot(
            file_id=1,
            kind="document",
            item_id=None,
            sync_state=PdmFileSyncState.SKIPPED,
            last_error="state not released for documents",
        )
        assert find_document_unmatched([snapshot]) == []

    def test_matched_document_not_reported(self):
        snapshot = make_snapshot(
            file_id=1,
            kind="document",
            item_id=5,
            sync_state=PdmFileSyncState.INGESTED,
        )
        assert find_document_unmatched([snapshot]) == []

    def test_non_document_kind_not_reported(self):
        snapshot = make_snapshot(
            file_id=1,
            kind="bought",
            item_id=None,
            sync_state=PdmFileSyncState.SKIPPED,
            last_error="identity variables missing",
        )
        assert find_document_unmatched([snapshot]) == []
