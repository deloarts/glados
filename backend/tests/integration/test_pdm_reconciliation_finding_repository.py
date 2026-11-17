"""
DB-backed coverage for SqlAlchemyPdmReconciliationFindingRepository:
add_many (no commit, matched to the right run), get_multi (category/kind/
search filters, paging), and counts_for_run (sums `count`, not row count).
A finding row always belongs to a real PdmSyncRun (the FK the table
enforces), so every test seeds one via SqlAlchemyPdmSyncRunRepository first.
"""

from datetime import UTC
from datetime import datetime

from src.modules.external_data.adapters.outbound.persistence.repositories.pdm_reconciliation_finding_repository import (
    SqlAlchemyPdmReconciliationFindingRepository,
)
from src.modules.external_data.adapters.outbound.persistence.repositories.pdm_sync_run_repository import (
    SqlAlchemyPdmSyncRunRepository,
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

_NOW = datetime(2026, 9, 5, 12, 0, tzinfo=UTC)


async def _run(db) -> PdmSyncRun:
    return await SqlAlchemyPdmSyncRunRepository(db).start(
        PdmSyncRun(
            id=0,
            started_at=_NOW,
            finished_at=None,
            trigger=PdmSyncTrigger.RECONCILIATION,
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
        )
    )


def _finding(*, run_id: int, **overrides: object) -> PdmReconciliationFinding:
    defaults: dict[str, object] = dict(
        id=0,
        run_id=run_id,
        category=PdmReconciliationCategory.ORPHANED_CAD_ROW,
        severity=PdmReconciliationSeverity.WARNING,
        kind="made",
        item_id=1,
        file_id=100,
        part_number="CAD-1",
        revision="A",
        message="linked PDM file is missing",
        count=1,
        created_at=_NOW,
    )
    defaults.update(overrides)
    return PdmReconciliationFinding(**defaults)  # type: ignore[arg-type]


class TestAddMany:
    async def test_adds_findings_under_the_right_run(self, db):
        run_a = await _run(db)
        run_b = await _run(db)
        repo = SqlAlchemyPdmReconciliationFindingRepository(db)

        await repo.add_many(
            [_finding(run_id=run_a.id, file_id=1), _finding(run_id=run_a.id, file_id=2)]
        )
        await repo.add_many([_finding(run_id=run_b.id, file_id=3)])
        await db.commit()

        total_a, rows_a = await repo.get_multi(run_a.id, PdmReconciliationFindingFilterDto())
        total_b, rows_b = await repo.get_multi(run_b.id, PdmReconciliationFindingFilterDto())
        assert total_a == 2
        assert {r.file_id for r in rows_a} == {1, 2}
        assert total_b == 1
        assert rows_b[0].file_id == 3

    async def test_does_not_commit_by_itself(self, db):
        run = await _run(db)
        repo = SqlAlchemyPdmReconciliationFindingRepository(db)

        await repo.add_many([_finding(run_id=run.id)])
        await db.rollback()

        total, rows = await repo.get_multi(run.id, PdmReconciliationFindingFilterDto())
        assert total == 0
        assert rows == []


class TestGetMulti:
    async def test_filters_by_category(self, db):
        run = await _run(db)
        repo = SqlAlchemyPdmReconciliationFindingRepository(db)
        await repo.add_many(
            [
                _finding(
                    run_id=run.id, file_id=1, category=PdmReconciliationCategory.ORPHANED_CAD_ROW
                ),
                _finding(run_id=run.id, file_id=2, category=PdmReconciliationCategory.REVISION_LAG),
            ]
        )
        await db.commit()

        total, rows = await repo.get_multi(
            run.id, PdmReconciliationFindingFilterDto(category="revision_lag")
        )

        assert total == 1
        assert rows[0].file_id == 2

    async def test_filters_by_kind(self, db):
        run = await _run(db)
        repo = SqlAlchemyPdmReconciliationFindingRepository(db)
        await repo.add_many(
            [
                _finding(run_id=run.id, file_id=1, kind="made"),
                _finding(run_id=run.id, file_id=2, kind="bought"),
            ]
        )
        await db.commit()

        total, rows = await repo.get_multi(run.id, PdmReconciliationFindingFilterDto(kind="bought"))

        assert total == 1
        assert rows[0].file_id == 2

    async def test_search_matches_part_number_and_message(self, db):
        run = await _run(db)
        repo = SqlAlchemyPdmReconciliationFindingRepository(db)
        await repo.add_many(
            [
                _finding(run_id=run.id, file_id=1, part_number="ABC-123", message="ok"),
                _finding(run_id=run.id, file_id=2, part_number="XYZ-999", message="weird case"),
            ]
        )
        await db.commit()

        by_part_number = await repo.get_multi(
            run.id, PdmReconciliationFindingFilterDto(search="ABC")
        )
        by_message = await repo.get_multi(run.id, PdmReconciliationFindingFilterDto(search="weird"))

        assert by_part_number[0] == 1
        assert by_part_number[1][0].file_id == 1
        assert by_message[0] == 1
        assert by_message[1][0].file_id == 2

    async def test_paging(self, db):
        run = await _run(db)
        repo = SqlAlchemyPdmReconciliationFindingRepository(db)
        await repo.add_many([_finding(run_id=run.id, file_id=i) for i in range(1, 4)])
        await db.commit()

        total, page = await repo.get_multi(
            run.id, PdmReconciliationFindingFilterDto(skip=1, limit=1)
        )

        assert total == 3
        assert len(page) == 1

    async def test_scoped_to_the_given_run(self, db):
        run_a = await _run(db)
        run_b = await _run(db)
        repo = SqlAlchemyPdmReconciliationFindingRepository(db)
        await repo.add_many([_finding(run_id=run_a.id), _finding(run_id=run_b.id)])
        await db.commit()

        total, _ = await repo.get_multi(run_a.id, PdmReconciliationFindingFilterDto())

        assert total == 1


class TestCountsForRun:
    async def test_sums_count_not_row_count(self, db):
        run = await _run(db)
        repo = SqlAlchemyPdmReconciliationFindingRepository(db)
        await repo.add_many(
            [
                _finding(
                    run_id=run.id, file_id=1, category=PdmReconciliationCategory.STUCK_FILE, count=3
                ),
                _finding(
                    run_id=run.id, file_id=2, category=PdmReconciliationCategory.STUCK_FILE, count=2
                ),
                _finding(
                    run_id=run.id,
                    file_id=3,
                    category=PdmReconciliationCategory.REVISION_LAG,
                    count=1,
                ),
            ]
        )
        await db.commit()

        counts = await repo.counts_for_run(run.id)

        assert counts == {"stuck_file": 5, "revision_lag": 1}

    async def test_empty_run_has_no_counts(self, db):
        run = await _run(db)
        repo = SqlAlchemyPdmReconciliationFindingRepository(db)

        assert await repo.counts_for_run(run.id) == {}
