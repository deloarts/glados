"""
PollPdmVault at scale: with a worker factory, changed files are drained by
several workers at once, each holding the file's lock, a changed file is
marked pending before it is ingested, snapshots are read per walked folder,
the run reports live progress, and a large conflict backlog is retried at a
slower pace.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC
from datetime import datetime
from datetime import timedelta

from src.modules.external_data.application.dto.pdm_dto import IngestOutcome
from src.modules.external_data.application.dto.pdm_dto import PdmFilePayload
from src.modules.external_data.application.use_cases.pdm.poll_pdm_vault import PollPdmVault
from src.modules.external_data.domain.value_objects.pdm_file_sync_state import PdmFileSyncState
from src.modules.external_data.domain.value_objects.pdm_sync_trigger import PdmSyncTrigger
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.poll_pdm_vault._helpers import MADE_FOLDER_ID
from tests.unit.poll_pdm_vault._helpers import make_object
from tests.unit.poll_pdm_vault._helpers import make_pdm_settings
from tests.unit.poll_pdm_vault._helpers import make_snapshot
from tests.unit.poll_pdm_vault.rig import FakeIngest
from tests.unit.poll_pdm_vault.rig import Rig


class _SlowIngest(FakeIngest):
    """Yields to the event loop mid-ingest, so parallel workers interleave,
    and records the highest number of ingests in flight at once."""

    def __init__(self) -> None:
        super().__init__()
        self.in_flight = 0
        self.max_in_flight = 0

    async def execute(self, payload: PdmFilePayload) -> IngestOutcome:
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        self.in_flight -= 1
        return await super().execute(payload)


class _RecordingLock:
    def __init__(self) -> None:
        self.held: set[int] = set()
        self.acquired: list[int] = []

    @asynccontextmanager
    async def hold(self, file_id: int) -> AsyncIterator[None]:
        assert file_id not in self.held, "the same file must never be ingested twice at once"
        self.held.add(file_id)
        self.acquired.append(file_id)
        try:
            yield
        finally:
            self.held.discard(file_id)


def _parallel_rig(*, concurrency: int, files: int) -> tuple[Rig, _SlowIngest, _RecordingLock, list]:
    ingest = _SlowIngest()
    rig = Rig(settings=make_pdm_settings(ingest_concurrency=concurrency), ingest=ingest)
    rig.gateway.folders[MADE_FOLDER_ID] = [
        make_object(id=i, path=f"\\Made-Parts\\p{i}.sldprt") for i in range(1, files + 1)
    ]
    lock = _RecordingLock()
    workers: list[PollPdmVault] = []

    @asynccontextmanager
    async def worker_factory() -> AsyncIterator[PollPdmVault]:
        # Same fakes, own unit of work, the way production gives each
        # worker its own database session.
        worker = PollPdmVault(
            session=rig.session,  # type: ignore[arg-type]
            admin_settings_repo=rig.admin_settings_repo,  # type: ignore[arg-type]
            snapshot_repo=rig.snapshot_repo,  # type: ignore[arg-type]
            made_item_repo=rig.made_item_repo,  # type: ignore[arg-type]
            bought_item_repo=rig.bought_item_repo,  # type: ignore[arg-type]
            ingest=ingest,  # type: ignore[arg-type]
            write_back=rig.write_back,
            document_sync=rig.document_sync,  # type: ignore[arg-type]
            thumbnails=rig.thumbnails,  # type: ignore[arg-type]
            run_repo=rig.run_repo,  # type: ignore[arg-type]
            folder_poll_state_repo=rig.folder_poll_state_repo,  # type: ignore[arg-type]
            uow=FakeUnitOfWork(),
        )
        workers.append(worker)
        yield worker

    rig.use_case = PollPdmVault(
        session=rig.session,  # type: ignore[arg-type]
        admin_settings_repo=rig.admin_settings_repo,  # type: ignore[arg-type]
        snapshot_repo=rig.snapshot_repo,  # type: ignore[arg-type]
        made_item_repo=rig.made_item_repo,  # type: ignore[arg-type]
        bought_item_repo=rig.bought_item_repo,  # type: ignore[arg-type]
        ingest=ingest,  # type: ignore[arg-type]
        write_back=rig.write_back,
        document_sync=rig.document_sync,  # type: ignore[arg-type]
        thumbnails=rig.thumbnails,  # type: ignore[arg-type]
        run_repo=rig.run_repo,  # type: ignore[arg-type]
        folder_poll_state_repo=rig.folder_poll_state_repo,  # type: ignore[arg-type]
        uow=rig.uow,
        worker_factory=worker_factory,
        file_lock=lock,  # type: ignore[arg-type]
    )
    return rig, ingest, lock, workers


class TestParallelIngest:
    async def test_workers_drain_every_file_in_parallel(self) -> None:
        rig, ingest, lock, workers = _parallel_rig(concurrency=3, files=7)

        summary = await rig.use_case.execute()

        assert summary.ingested == 7
        assert sorted(p.file_id for p in ingest.calls) == list(range(1, 8))
        assert len(workers) == 3
        assert 1 < ingest.max_in_flight <= 3
        assert sorted(lock.acquired) == list(range(1, 8))
        run_id = next(iter(rig.run_repo.runs))
        assert len(rig.run_repo.entries[run_id]) == 7

    async def test_concurrency_of_one_stays_on_the_poller_itself(self) -> None:
        rig, ingest, lock, workers = _parallel_rig(concurrency=1, files=4)

        summary = await rig.use_case.execute()

        assert summary.ingested == 4
        assert workers == []
        assert ingest.max_in_flight == 1
        assert sorted(lock.acquired) == [1, 2, 3, 4]


class TestChangedFileIsQueuedAsPending:
    async def test_snapshot_reads_pending_while_its_new_version_waits_for_ingest(self) -> None:
        """A run that dies between the scan and the ingest must leave a row
        the next run still sees as changed."""
        seen_states: list[str] = []
        rig = Rig(
            snapshots=[
                make_snapshot(file_id=1, version=4, sync_state=PdmFileSyncState.INGESTED, item_id=1)
            ]
        )

        class _Probe(FakeIngest):
            async def execute(self, payload: PdmFilePayload) -> IngestOutcome:
                row = rig.snapshot_repo.get("V1", payload.file_id)
                seen_states.append(row.sync_state if row else "none")
                return await super().execute(payload)

        rig.ingest.__class__ = _Probe
        rig.gateway.folders[MADE_FOLDER_ID] = [make_object(id=1, version=5)]

        await rig.use_case.execute()

        assert seen_states == [PdmFileSyncState.PENDING.value]


class TestLiveProgress:
    async def test_run_reports_its_phases_folder_and_counts_while_it_runs(self) -> None:
        rig, _ingest, _lock, _workers = _parallel_rig(concurrency=2, files=3)

        await rig.use_case.execute()

        progress = rig.run_repo.progress
        walking = [p for p in progress if p.phase == "walking"]
        ingesting = [p for p in progress if p.phase == "ingesting"]
        assert walking[0].current_path == "\\Made-Parts"
        assert ingesting[0].files_queued == 3
        assert progress[-1].phase == "finishing"
        assert all(p.progress_at is not None for p in progress)
        run = next(iter(rig.run_repo.runs.values()))
        assert run.finished_at is not None
        assert run.phase is None
        assert (run.files_queued, run.files_processed) == (3, 3)


class TestPerFolderSnapshotLoading:
    async def test_poll_never_reads_the_whole_vault(self) -> None:
        rig = Rig(snapshots=[make_snapshot(file_id=1, version=5)])

        async def whole_vault(vault_id: str) -> list:
            raise AssertionError("the poll must read snapshots per walked folder")

        rig.snapshot_repo.get_all_for_vault = whole_vault  # type: ignore[method-assign]
        rig.gateway.folders[MADE_FOLDER_ID] = [make_object(id=1, version=5)]

        summary = await rig.use_case.execute()

        assert summary.files_seen == 1
        assert summary.changed == 0

    async def test_a_file_that_moved_in_keeps_its_item_link(self) -> None:
        moved = make_snapshot(
            file_id=7,
            version=5,
            parent_folder_id=999,
            path="\\Elsewhere\\p7.sldprt",
            sync_state=PdmFileSyncState.INGESTED,
            item_id=42,
        )
        rig = Rig(snapshots=[moved])
        rig.gateway.folders[MADE_FOLDER_ID] = [
            make_object(id=7, version=6, path="\\Made-Parts\\p7.sldprt")
        ]

        await rig.use_case.execute()

        row = rig.snapshot_repo.get("V1", 7)
        assert row is not None
        assert row.item_id == 42
        assert row.parent_folder_id == MADE_FOLDER_ID


def _conflict_backlog_rig(count: int, *, stale_file_id: int | None = None) -> Rig:
    """`count` parked conflicts, all unchanged in PDM and last attempted just
    now, except `stale_file_id`, last attempted two hours ago."""
    stale = datetime.now(UTC) - timedelta(hours=2)
    snapshots = [
        make_snapshot(
            file_id=i,
            path=f"\\Made-Parts\\c{i}.sldprt",
            sync_state=PdmFileSyncState.CONFLICT,
            last_seen_at=stale if i == stale_file_id else None,
        )
        for i in range(1, count + 1)
    ]
    rig = Rig(snapshots=snapshots)
    objects = [make_object(id=i, path=f"\\Made-Parts\\c{i}.sldprt") for i in range(1, count + 1)]
    rig.gateway.folders[MADE_FOLDER_ID] = objects
    for obj in objects:
        rig.gateway.by_id[obj.id] = obj
    return rig


class TestConflictBacklogThrottle:
    async def test_small_backlog_retries_every_conflict_each_run(self) -> None:
        rig = _conflict_backlog_rig(3)

        await rig.use_case.execute()

        assert sorted(p.file_id for p in rig.ingest.calls) == [1, 2, 3]

    async def test_large_backlog_retries_only_conflicts_due_again(self) -> None:
        rig = _conflict_backlog_rig(101, stale_file_id=50)

        await rig.use_case.execute()

        assert [p.file_id for p in rig.ingest.calls] == [50]

    async def test_manual_run_retries_the_whole_backlog(self) -> None:
        rig = _conflict_backlog_rig(101)

        await rig.use_case.execute(PdmSyncTrigger.MANUAL)

        retried = {p.file_id for p in rig.ingest.calls}
        assert retried == set(range(1, 102))
