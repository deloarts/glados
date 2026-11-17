"""
Unit tests for GetPdmReconciliation and ListPdmReconciliationFindings.
Both back the admin "View reconciliation" dialog's read side; ReconcilePdmVault (what actually
produces the findings) has its own thorough unit coverage in
tests/unit/test_pdm_reconciliation.py and its own repository integration
test in tests/integration/test_pdm_reconciliation_finding_repository.py,
neither of which exercises these two read-only use cases or their own
"latest run wins, never accumulates" rule.

No database, no HTTP. Fakes are local and intentionally minimal (matching
FakePdmFileSnapshotRepository's precedent in tests/unit/admin_settings/fakes.py):
each only implements the one or two methods these use cases actually call.
"""

from datetime import UTC
from datetime import datetime

import pytest

from src.modules.external_data.application.use_cases.admin_settings.get_pdm_reconciliation import (
    GetPdmReconciliation,
)
from src.modules.external_data.application.use_cases.admin_settings.list_pdm_reconciliation_findings import (
    ListPdmReconciliationFindings,
)
from src.modules.external_data.domain.entities.pdm_reconciliation_finding import (
    PdmReconciliationFinding,
)
from src.modules.external_data.domain.entities.pdm_sync_run import PdmSyncRun
from src.modules.external_data.domain.value_objects.pdm_reconciliation_category import (
    PdmReconciliationCategory,
)
from src.modules.external_data.domain.value_objects.pdm_reconciliation_severity import (
    PdmReconciliationSeverity,
)
from src.modules.external_data.domain.value_objects.pdm_sync_trigger import PdmSyncTrigger
from src.modules.external_data.ports.outbound.repositories.pdm_reconciliation_finding_repository import (
    PdmReconciliationFindingFilterDto,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user

# ── Helpers ───────────────────────────────────────────────────────────


def make_actor(permissions: list[str] | None = None) -> User:
    return make_user(username="admin", full_name="Admin User", permissions=permissions)


def make_run(id: int, trigger: PdmSyncTrigger, started_at: datetime) -> PdmSyncRun:
    return PdmSyncRun(
        id=id,
        started_at=started_at,
        finished_at=started_at,
        trigger=trigger,
        files_seen=10,
        changed=2,
        ingested=1,
        skipped=8,
        conflicts=0,
        errors=0,
        missing=0,
        error=None,
        summary="reconciliation run",
        folders_walked=3,
    )


def make_finding(
    run_id: int,
    category: PdmReconciliationCategory = PdmReconciliationCategory.STUCK_FILE,
    count: int = 1,
    part_number: str | None = "PN-1",
) -> PdmReconciliationFinding:
    return PdmReconciliationFinding(
        id=0,
        run_id=run_id,
        category=category,
        severity=PdmReconciliationSeverity.WARNING,
        kind="made",
        item_id=None,
        file_id=None,
        part_number=part_number,
        revision=None,
        message="looks stuck",
        count=count,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


class FakePdmSyncRunRepository:
    """Minimal fake: both use cases here only ever call latest_by_trigger()."""

    def __init__(self, runs: list[PdmSyncRun] | None = None) -> None:
        self._runs = list(runs or [])

    async def latest_by_trigger(self, trigger: str) -> PdmSyncRun | None:
        matches = [r for r in self._runs if r.trigger == trigger]
        return max(matches, key=lambda r: r.started_at) if matches else None


class FakePdmReconciliationFindingRepository:
    def __init__(
        self, findings: list[PdmReconciliationFinding] | None = None, counts: dict | None = None
    ) -> None:
        self._findings = list(findings or [])
        self.counts = counts or {}
        self.get_multi_calls: list[tuple[int, PdmReconciliationFindingFilterDto]] = []

    async def get_multi(
        self, run_id: int, filters: PdmReconciliationFindingFilterDto
    ) -> tuple[int, list[PdmReconciliationFinding]]:
        self.get_multi_calls.append((run_id, filters))
        rows = [f for f in self._findings if f.run_id == run_id]
        if filters.category:
            rows = [f for f in rows if f.category == filters.category]
        if filters.kind:
            rows = [f for f in rows if f.kind == filters.kind]
        total = len(rows)
        skip = filters.skip or 0
        limit = filters.limit
        return total, rows[skip : skip + limit if limit else None]

    async def counts_for_run(self, run_id: int) -> dict[str, int]:
        return self.counts


# ── GetPdmReconciliation ─────────────────────────────────────────────


class TestGetPdmReconciliation:
    async def test_requires_read_settings(self):
        use_case = GetPdmReconciliation(
            FakePdmSyncRunRepository(), FakePdmReconciliationFindingRepository()
        )

        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(actor=make_actor(permissions=[]))

    async def test_no_reconciliation_run_yet_returns_empty_report(self):
        use_case = GetPdmReconciliation(
            FakePdmSyncRunRepository(), FakePdmReconciliationFindingRepository()
        )

        result = await use_case.execute(actor=make_actor([Permission.READ_SETTINGS]))

        assert result.run is None
        assert result.counts == {}

    async def test_returns_the_latest_reconciliation_run_and_its_counts(self):
        older = make_run(1, PdmSyncTrigger.RECONCILIATION, datetime(2026, 1, 1, tzinfo=UTC))
        newer = make_run(2, PdmSyncTrigger.RECONCILIATION, datetime(2026, 2, 1, tzinfo=UTC))
        # A newer *scheduled* run must not be picked over the latest
        # reconciliation run. GetPdmReconciliation asks specifically for
        # trigger="reconciliation", never "the newest run of any kind".
        newest_scheduled = make_run(3, PdmSyncTrigger.SCHEDULED, datetime(2026, 3, 1, tzinfo=UTC))
        runs = FakePdmSyncRunRepository([older, newer, newest_scheduled])
        findings = FakePdmReconciliationFindingRepository(counts={"stuck_file": 4})
        use_case = GetPdmReconciliation(runs, findings)

        result = await use_case.execute(actor=make_actor([Permission.READ_SETTINGS]))

        assert result.run is not None
        assert result.run.id == newer.id
        assert result.counts == {"stuck_file": 4}


# ── ListPdmReconciliationFindings ────────────────────────────────────


class TestListPdmReconciliationFindings:
    async def test_requires_read_settings(self):
        use_case = ListPdmReconciliationFindings(
            FakePdmSyncRunRepository(), FakePdmReconciliationFindingRepository()
        )

        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(
                actor=make_actor(permissions=[]),
                filters=PdmReconciliationFindingFilterDto(),
            )

    async def test_no_reconciliation_run_yet_returns_an_empty_page(self):
        findings = FakePdmReconciliationFindingRepository()
        use_case = ListPdmReconciliationFindings(FakePdmSyncRunRepository(), findings)

        total, rows = await use_case.execute(
            actor=make_actor([Permission.READ_SETTINGS]),
            filters=PdmReconciliationFindingFilterDto(),
        )

        assert total == 0
        assert rows == []
        # Never even asked the findings repository, there is no run id to ask about.
        assert findings.get_multi_calls == []

    async def test_lists_only_the_latest_runs_findings_filtered_by_category(self):
        older = make_run(1, PdmSyncTrigger.RECONCILIATION, datetime(2026, 1, 1, tzinfo=UTC))
        newer = make_run(2, PdmSyncTrigger.RECONCILIATION, datetime(2026, 2, 1, tzinfo=UTC))
        runs = FakePdmSyncRunRepository([older, newer])
        stale_finding = make_finding(run_id=older.id, category=PdmReconciliationCategory.STUCK_FILE)
        current_stuck = make_finding(
            run_id=newer.id, category=PdmReconciliationCategory.STUCK_FILE, part_number="PN-2"
        )
        current_drift = make_finding(
            run_id=newer.id, category=PdmReconciliationCategory.PART_NUMBER_DRIFT
        )
        findings = FakePdmReconciliationFindingRepository(
            [stale_finding, current_stuck, current_drift]
        )
        use_case = ListPdmReconciliationFindings(runs, findings)

        total, rows = await use_case.execute(
            actor=make_actor([Permission.READ_SETTINGS]),
            filters=PdmReconciliationFindingFilterDto(category="stuck_file"),
        )

        assert total == 1
        assert len(rows) == 1
        assert rows[0].part_number == "PN-2"
        assert rows[0].run_id == newer.id
        # Only the latest run was ever queried, by id.
        assert findings.get_multi_calls[0][0] == newer.id
