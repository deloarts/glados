"""
Unit tests for BackupScheduler: the background-task wiring (interval jobs,
each firing immediately at start then on their own cadence, never
overlapping itself so a slow tick can never pile up) and both ticks'
fail-open exception handling. RunDueBackup's own claim/run/finish
orchestration is covered by test_run_due_backup.py, CheckDiskSpace's own
threshold/dedupe/cooldown logic by test_check_disk_space.py; this only
covers the scheduler shell around both.
"""

import asyncio
import logging
from collections.abc import Awaitable
from collections.abc import Callable
from dataclasses import replace
from datetime import timedelta

import src.modules.platform.adapters.outbound.external.schedules.system_schedule as system_schedule_module
from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.platform.adapters.outbound.external.schedules.system_schedule import (
    BackupScheduler,
)
from src.modules.platform.adapters.outbound.external.schedules.system_schedule import IntervalJob
from src.modules.platform.adapters.outbound.persistence.session import SessionLocal


async def _cancel(tasks: list[asyncio.Task[None]]) -> None:
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


class _RecordedJobs:
    """Stands in for run_every and records what start() hands it, keyed by
    job name, so a test can read each job's interval without running it."""

    def __init__(self) -> None:
        self.intervals: dict[str, float] = {}

    async def __call__(self, interval_seconds: float, job: object, name: str) -> None:
        self.intervals[name] = interval_seconds


async def _noop() -> None:
    return None


def _scheduler_running(
    name: str, run: Callable[[], Awaitable[None]], *, interval_seconds: float | None = None
) -> BackupScheduler:
    """A scheduler whose job `name` runs `run` instead of its own body, on
    its own interval unless `interval_seconds` is given, and whose other
    jobs do nothing."""
    jobs = [
        replace(
            job,
            run=run,
            interval_seconds=job.interval_seconds if interval_seconds is None else interval_seconds,
        )
        if job.name == name
        else replace(job, run=_noop)
        for job in BackupScheduler().jobs
    ]
    return BackupScheduler(jobs=jobs)


def _job(scheduler: BackupScheduler, name: str) -> IntervalJob:
    return next(job for job in scheduler.jobs if job.name == name)


class _GatedRun:
    """A job body that holds each run open until the test releases it, so
    the test can step the loop one run at a time and see whether a second
    run ever starts beside an open one."""

    def __init__(self) -> None:
        self.active = 0
        self.max_active = 0
        self.runs = 0
        self._started: asyncio.Queue[None] = asyncio.Queue()
        self._released: asyncio.Queue[None] = asyncio.Queue()

    async def __call__(self) -> None:
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        self._started.put_nowait(None)
        await self._released.get()
        self.active -= 1
        self.runs += 1

    async def step(self, runs: int) -> None:
        """Waits for each of `runs` runs to start, yields to the loop so an
        overlapping run would have the chance to start, then releases it;
        returns once the run after the last released one has started."""
        for _ in range(runs):
            await self._started.get()
            for _ in range(10):
                await asyncio.sleep(0)
            self._released.put_nowait(None)
        await self._started.get()


class TestStart:
    async def test_schedules_one_interval_job_every_60s(self, monkeypatch):
        recorded = _RecordedJobs()
        monkeypatch.setattr(system_schedule_module, "run_every", recorded)

        await asyncio.gather(*BackupScheduler().start())

        assert recorded.intervals["backup_tick"] == timedelta(seconds=60).total_seconds()

    async def test_the_job_never_overlaps_itself(self):
        """The APScheduler job used coalesce=True and max_instances=1; the
        asyncio loop gives the same guarantee by starting the next run only
        after the previous one has finished."""
        tick = _GatedRun()
        tasks = _scheduler_running("backup_tick", tick, interval_seconds=0).start()
        try:
            # The timeout only guards against a hang; the steps themselves
            # wait on the job, never on the wall clock.
            await asyncio.wait_for(tick.step(runs=3), timeout=5)
        finally:
            await _cancel(tasks)

        assert tick.runs > 1
        assert tick.max_active == 1

    async def test_the_first_run_is_immediate_not_60s_out(self):
        ran = asyncio.Event()

        async def _tick() -> None:
            ran.set()

        scheduler = _scheduler_running("backup_tick", _tick)
        tasks = scheduler.start()
        try:
            # Immediate means "now", not one full interval (60s) away.
            await asyncio.wait_for(ran.wait(), timeout=5)
        finally:
            await _cancel(tasks)

    async def test_cancelling_the_started_tasks_stops_them_cleanly(self):
        scheduler = BackupScheduler(
            jobs=[replace(job, run=_noop) for job in BackupScheduler().jobs]
        )
        tasks = scheduler.start()

        await asyncio.sleep(0)
        await _cancel(tasks)

        assert all(task.cancelled() for task in tasks)

    async def test_schedules_a_second_interval_job_for_disk_space_every_15_minutes(
        self, monkeypatch
    ):
        recorded = _RecordedJobs()
        monkeypatch.setattr(system_schedule_module, "run_every", recorded)

        await asyncio.gather(*BackupScheduler().start())

        assert recorded.intervals["disk_space_check"] == timedelta(minutes=15).total_seconds()

    async def test_the_disk_space_job_never_overlaps_itself(self):
        check = _GatedRun()
        tasks = _scheduler_running("disk_space_check", check, interval_seconds=0).start()
        try:
            await asyncio.wait_for(check.step(runs=3), timeout=5)
        finally:
            await _cancel(tasks)

        assert check.runs > 1
        assert check.max_active == 1

    async def test_the_disk_space_job_first_run_is_also_immediate(self):
        ran = asyncio.Event()

        async def _check() -> None:
            ran.set()

        scheduler = _scheduler_running("disk_space_check", _check)
        tasks = scheduler.start()
        try:
            await asyncio.wait_for(ran.wait(), timeout=5)
        finally:
            await _cancel(tasks)


class TestTickFailsOpen:
    async def test_a_tick_that_raises_is_caught_and_logged_not_propagated(
        self, monkeypatch, glados_caplog
    ):
        def _raising_session_local():
            raise RuntimeError("DB unreachable")

        monkeypatch.setattr(system_schedule_module, "SessionLocal", _raising_session_local)
        scheduler = BackupScheduler()

        await _job(scheduler, "backup_tick").run()  # must not raise

        assert [r for r in glados_caplog.records if r.levelno == logging.ERROR]

    async def test_a_disk_check_that_raises_is_caught_and_logged_not_propagated(
        self, monkeypatch, glados_caplog
    ):
        def _raising_session_local():
            raise RuntimeError("DB unreachable")

        monkeypatch.setattr(system_schedule_module, "SessionLocal", _raising_session_local)
        scheduler = BackupScheduler()

        await _job(scheduler, "disk_space_check").run()  # must not raise

        assert [r for r in glados_caplog.records if r.levelno == logging.ERROR]

    async def test_the_tick_failure_alert_itself_never_raises_when_sessionlocal_is_broken(
        self, monkeypatch, glados_caplog
    ):
        """_notify_tick_failure builds its own fresh SessionLocal(). If
        that is also broken (the same outage that broke the tick itself),
        it must log and swallow, never propagate out of the except block
        that called it."""

        def _raising_session_local():
            raise RuntimeError("DB unreachable")

        monkeypatch.setattr(system_schedule_module, "SessionLocal", _raising_session_local)
        scheduler = BackupScheduler()

        await scheduler._notify_tick_failure("tick failed")  # must not raise

        assert [r for r in glados_caplog.records if r.levelno == logging.ERROR]


class TestNotifierBuildFailureNeverBlocksTheBackupCheck:
    """_tick() must run RunDueBackup even when building the ops-alert
    notifier (which calls settings_repo.get_mail()) fails, for example on a
    not-yet-seeded admin_mail_settings row: a notifier failure that aborted
    the whole tick would silently skip the actual due-backup check. See
    test_api_backup_runs.py for the run-now endpoint's equivalent
    background task."""

    async def test_tick_still_calls_run_due_backup_when_building_the_notifier_fails(
        self, monkeypatch
    ):
        calls: list[object] = []

        class FakeRunDueBackup:
            def __init__(self, **kwargs: object) -> None:
                calls.append(kwargs.get("notifier"))

            async def execute(self) -> None:
                calls.append("executed")

        monkeypatch.setattr(system_schedule_module, "RunDueBackup", FakeRunDueBackup)
        scheduler = BackupScheduler()

        # No schema in the unit-test DB (see this module's own note that
        # unit tests get none, unlike the integration suite): get_mail()
        # raises "no such table", exercising the real failure path with
        # nothing mocked.
        await _job(scheduler, "backup_tick").run()

        assert calls == [None, "executed"]

    async def test_build_notifier_returns_none_and_logs_a_warning_on_failure(self, glados_caplog):
        scheduler = BackupScheduler()

        async with SessionLocal() as db:
            notifier = await scheduler._build_notifier(SqlAlchemyAdminSettingsRepository(db))

        assert notifier is None
        warnings = [r for r in glados_caplog.records if r.levelno == logging.WARNING]
        assert any("notifier" in r.getMessage() for r in warnings)
