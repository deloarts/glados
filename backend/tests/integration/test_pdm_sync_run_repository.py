"""
DB-backed coverage for SqlAlchemyPdmSyncRunRepository: start (insert and
flush for the id), finish (stage final counts/error/summary), add_entries
(matched to the right run), get_multi (newest-first paging),
get_by_id, get_entries (paging + action filter), list_file_history (one
vault's entries of the given files across runs, newest first, with their
run) and prune (deletes runs started before the cutoff, cascading the
deletion to their entries).
"""

from datetime import UTC
from datetime import datetime
from datetime import timedelta

from src.modules.external_data.adapters.outbound.persistence.repositories.pdm_sync_run_repository import (
    SqlAlchemyPdmSyncRunRepository,
)
from src.modules.external_data.domain.entities.pdm_sync_run import PdmSyncRun
from src.modules.external_data.domain.entities.pdm_sync_run import PdmSyncRunEntry
from src.modules.external_data.domain.value_objects.pdm_sync_trigger import PdmSyncTrigger

_NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def _run(
    *,
    started_at: datetime = _NOW,
    trigger: PdmSyncTrigger = PdmSyncTrigger.SCHEDULED,
    **overrides: object,
) -> PdmSyncRun:
    defaults: dict[str, object] = dict(
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
    )
    defaults.update(overrides)
    return PdmSyncRun(**defaults)  # type: ignore[arg-type]


def _entry(
    *, run_id: int, file_id: int = 1, action: str = "created", **overrides: object
) -> PdmSyncRunEntry:
    defaults: dict[str, object] = dict(
        id=0,
        run_id=run_id,
        vault_id="V1",
        file_id=file_id,
        name="Bracket.SLDPRT",
        path="\\Made-Parts\\Bracket.SLDPRT",
        kind="made",
        action=action,
        item_id=None,
        message="ok",
        created_at=_NOW,
    )
    defaults.update(overrides)
    return PdmSyncRunEntry(**defaults)  # type: ignore[arg-type]


class TestStartAndFinish:
    async def test_start_inserts_and_returns_the_id(self, db):
        repo = SqlAlchemyPdmSyncRunRepository(db)

        saved = await repo.start(_run())

        assert saved.id != 0
        assert saved.trigger == "scheduled"
        assert saved.finished_at is None
        again = SqlAlchemyPdmSyncRunRepository(db)
        assert await again.get_by_id(saved.id) is not None

    async def test_finish_persists_final_counts_and_summary(self, db):
        repo = SqlAlchemyPdmSyncRunRepository(db)
        saved = await repo.start(_run())

        saved.finished_at = _NOW + timedelta(minutes=1)
        saved.files_seen = 3
        saved.changed = 2
        saved.ingested = 1
        saved.skipped = 1
        saved.error = "boom"
        saved.summary = "3 files seen"
        await repo.finish(saved)

        reloaded = await repo.get_by_id(saved.id)
        assert reloaded is not None
        assert reloaded.finished_at is not None
        assert reloaded.files_seen == 3
        assert reloaded.changed == 2
        assert reloaded.ingested == 1
        assert reloaded.skipped == 1
        assert reloaded.error == "boom"
        assert reloaded.summary == "3 files seen"


class TestAddEntries:
    async def test_adds_entries_under_the_right_run(self, db):
        repo = SqlAlchemyPdmSyncRunRepository(db)
        run_a = await repo.start(_run())
        run_b = await repo.start(_run())

        await repo.add_entries(
            run_a.id, [_entry(run_id=run_a.id, file_id=1), _entry(run_id=run_a.id, file_id=2)]
        )
        await repo.add_entries(run_b.id, [_entry(run_id=run_b.id, file_id=3)])
        await db.commit()

        total_a, entries_a = await repo.get_entries(run_a.id, None, None, None)
        total_b, entries_b = await repo.get_entries(run_b.id, None, None, None)
        assert total_a == 2
        assert {e.file_id for e in entries_a} == {1, 2}
        assert total_b == 1
        assert entries_b[0].file_id == 3

    async def test_does_not_commit_by_itself(self, db):
        repo = SqlAlchemyPdmSyncRunRepository(db)
        run = await repo.start(_run())

        await repo.add_entries(run.id, [_entry(run_id=run.id)])
        await db.rollback()

        total, entries = await repo.get_entries(run.id, None, None, None)
        assert total == 0
        assert entries == []


class TestGetMulti:
    async def test_newest_first(self, db):
        repo = SqlAlchemyPdmSyncRunRepository(db)
        older = await repo.start(_run(started_at=_NOW - timedelta(hours=1)))
        newer = await repo.start(_run(started_at=_NOW))

        total, rows = await repo.get_multi(None, None)

        assert total == 2
        assert [r.id for r in rows] == [newer.id, older.id]

    async def test_paging(self, db):
        repo = SqlAlchemyPdmSyncRunRepository(db)
        for i in range(3):
            await repo.start(_run(started_at=_NOW + timedelta(minutes=i)))

        total, page = await repo.get_multi(1, 1)

        assert total == 3
        assert len(page) == 1


class TestGetById:
    async def test_returns_none_when_missing(self, db):
        repo = SqlAlchemyPdmSyncRunRepository(db)
        assert await repo.get_by_id(999999) is None


class TestLatestByTrigger:
    async def test_returns_the_newest_matching_run(self, db):
        repo = SqlAlchemyPdmSyncRunRepository(db)
        await repo.start(
            _run(started_at=_NOW - timedelta(hours=2), trigger=PdmSyncTrigger.RECONCILIATION)
        )
        newest = await repo.start(_run(started_at=_NOW, trigger=PdmSyncTrigger.RECONCILIATION))
        await repo.start(
            _run(started_at=_NOW + timedelta(hours=1), trigger=PdmSyncTrigger.SCHEDULED)
        )

        found = await repo.latest_by_trigger("reconciliation")

        assert found is not None
        assert found.id == newest.id

    async def test_returns_none_when_no_run_of_that_trigger_exists(self, db):
        repo = SqlAlchemyPdmSyncRunRepository(db)
        await repo.start(_run(trigger=PdmSyncTrigger.SCHEDULED))

        assert await repo.latest_by_trigger("reconciliation") is None


class TestGetEntries:
    async def test_filters_by_action(self, db):
        repo = SqlAlchemyPdmSyncRunRepository(db)
        run = await repo.start(_run())
        await repo.add_entries(
            run.id,
            [
                _entry(run_id=run.id, file_id=1, action="created"),
                _entry(run_id=run.id, file_id=2, action="missing"),
                _entry(run_id=run.id, file_id=3, action="missing"),
            ],
        )
        await db.commit()

        total, rows = await repo.get_entries(run.id, None, None, "missing")

        assert total == 2
        assert {r.file_id for r in rows} == {2, 3}

    async def test_paging(self, db):
        repo = SqlAlchemyPdmSyncRunRepository(db)
        run = await repo.start(_run())
        await repo.add_entries(run.id, [_entry(run_id=run.id, file_id=i) for i in range(1, 4)])
        await db.commit()

        total, page = await repo.get_entries(run.id, 1, 1, None)

        assert total == 3
        assert len(page) == 1


class TestPrune:
    async def test_deletes_runs_started_before_the_cutoff_and_their_entries(self, db):
        repo = SqlAlchemyPdmSyncRunRepository(db)
        kept_runs = []
        for i in range(2):
            run = await repo.start(_run(started_at=_NOW + timedelta(minutes=i)))
            await repo.add_entries(run.id, [_entry(run_id=run.id)])
            await db.commit()
            kept_runs.append(run)

        pruned_runs = []
        for i in range(3):
            run = await repo.start(_run(started_at=_NOW - timedelta(minutes=1 + i)))
            await repo.add_entries(run.id, [_entry(run_id=run.id)])
            await db.commit()
            pruned_runs.append(run)

        deleted = await repo.prune(_NOW)

        assert deleted == 3
        total, remaining = await repo.get_multi(None, None)
        assert total == 2
        assert {r.id for r in remaining} == {r.id for r in kept_runs}
        for run in pruned_runs:
            assert await repo.get_by_id(run.id) is None
            _, entries = await repo.get_entries(run.id, None, None, None)
            assert entries == []

    async def test_nothing_older_than_the_cutoff_deletes_nothing(self, db):
        repo = SqlAlchemyPdmSyncRunRepository(db)
        await repo.start(_run(started_at=_NOW))
        await repo.start(_run(started_at=_NOW + timedelta(days=1)))

        deleted = await repo.prune(_NOW)

        assert deleted == 0
        total, _remaining = await repo.get_multi(None, None)
        assert total == 2


class TestListFileHistory:
    async def test_merges_the_files_entries_across_runs_newest_first_with_their_run(self, db):
        repo = SqlAlchemyPdmSyncRunRepository(db)
        poll = await repo.start(_run(started_at=_NOW))
        await repo.add_entries(
            poll.id,
            [
                _entry(run_id=poll.id, file_id=1, created_at=_NOW),
                _entry(run_id=poll.id, file_id=3, created_at=_NOW + timedelta(seconds=1)),
            ],
        )
        trigger = await repo.start(
            _run(
                started_at=_NOW + timedelta(minutes=5),
                trigger=PdmSyncTrigger.FILE_TRIGGER,
                change_reason="state_change",
                change_state="Released",
                requested_by_name="Ada Lovelace",
            )
        )
        await repo.add_entries(
            trigger.id,
            [
                _entry(
                    run_id=trigger.id,
                    file_id=2,
                    action="revised",
                    created_at=_NOW + timedelta(minutes=5),
                )
            ],
        )
        await db.commit()

        rows = await repo.list_file_history("V1", [1, 2], limit=10)

        assert [(entry.file_id, entry.action) for entry, _run_row in rows] == [
            (2, "revised"),
            (1, "created"),
        ]
        newest_run = rows[0][1]
        assert newest_run.id == trigger.id
        assert newest_run.trigger == PdmSyncTrigger.FILE_TRIGGER
        assert newest_run.change_reason == "state_change"
        assert newest_run.change_state == "Released"
        assert newest_run.requested_by_name == "Ada Lovelace"
        assert rows[1][1].change_reason is None

    async def test_respects_the_vault_and_the_limit(self, db):
        repo = SqlAlchemyPdmSyncRunRepository(db)
        run = await repo.start(_run())
        await repo.add_entries(
            run.id,
            [
                _entry(run_id=run.id, file_id=1, created_at=_NOW),
                _entry(run_id=run.id, file_id=1, created_at=_NOW + timedelta(seconds=1)),
                _entry(run_id=run.id, file_id=1, vault_id="V2", created_at=_NOW),
            ],
        )
        await db.commit()

        rows = await repo.list_file_history("V1", [1], limit=1)

        assert len(rows) == 1
        assert rows[0][0].vault_id == "V1"
        assert rows[0][0].created_at == _NOW + timedelta(seconds=1)

    async def test_no_file_ids_returns_nothing(self, db):
        repo = SqlAlchemyPdmSyncRunRepository(db)

        assert await repo.list_file_history("V1", [], limit=10) == []
