"""
Unit tests for RunPdmPollIfDue: the cheap gate PdmPollScheduler calls every
60 seconds. There is no database and no HTTP: PollPdmVault and ReconcilePdmVault
are both fakes that just record whether/how they ran.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC
from datetime import datetime
from datetime import timedelta

from src.modules.external_data.application.use_cases.pdm.poll_pdm_vault import PollSummary
from src.modules.external_data.application.use_cases.pdm.reconcile_pdm_vault import (
    PdmReconciliationSummary,
)
from src.modules.external_data.application.use_cases.pdm.run_pdm_poll_if_due import RunPdmPollIfDue
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.value_objects.pdm_sync_trigger import PdmSyncTrigger
from tests.unit.fakes import FakeUnitOfWork


def make_pdm_settings(**overrides: object) -> AdminPdmSettings:
    defaults: dict[str, object] = dict(
        id=1,
        made_item_variable_map={},
        bought_item_variable_map={},
        enabled=True,
        base_url="http://pdm-host:65453",
        vault_name="MyVault",
        username="svc-account",
        password="secret",
        verify_certificate=True,
        timeout_seconds=15,
        session_token=None,
        session_user_id=None,
        session_obtained_at=None,
        watched_folders=[],
        made_released_state_ids=[10],
        made_obsolete_state_ids=[20],
        made_replaced_state_ids=[20],
        bought_released_state_ids=[10],
        bought_obsolete_state_ids=[20],
        bought_replaced_state_ids=[20],
        poll_interval_minutes=15,
        vault_id="",
        cad_items_read_only=True,
        last_poll_at=None,
        last_poll_error=None,
        last_poll_summary=None,
        writeback_enabled=False,
        made_item_extensions=["sldprt"],
        bought_item_extensions=["sldprt", "sldasm"],
        document_categories={"pdf": "drawing", "dxf": "dxf", "step": "step", "stp": "step"},
        thumbnails_enabled=False,
        stuck_after_days=7,
        reconcile_requested_deep=None,
        required_fields={"made": [], "bought": []},
    )
    defaults.update(overrides)
    return AdminPdmSettings(**defaults)  # type: ignore[arg-type]


class FakeAdminSettingsRepository:
    def __init__(self, pdm: AdminPdmSettings) -> None:
        self._pdm = pdm
        self.reconcile_requested_calls: list[bool | None] = []

    @property
    def pdm(self) -> AdminPdmSettings:
        """The stored PDM settings, for assertions."""
        return self._pdm

    async def get_pdm(self) -> AdminPdmSettings:
        return self._pdm

    async def save_pdm_reconcile_requested(self, deep: bool | None) -> None:
        self.reconcile_requested_calls.append(deep)
        self._pdm.reconcile_requested_deep = deep


class FakeLock:
    def __init__(self, *, acquirable: bool = True) -> None:
        self.acquirable = acquirable
        self.attempts = 0

    @asynccontextmanager
    async def lock(self) -> AsyncIterator[bool]:
        self.attempts += 1
        yield self.acquirable


class FakePoll:
    def __init__(self) -> None:
        self.calls = 0
        self.triggers: list[PdmSyncTrigger] = []

    async def execute(self, trigger: PdmSyncTrigger = PdmSyncTrigger.SCHEDULED) -> PollSummary:
        self.calls += 1
        self.triggers.append(trigger)
        return PollSummary(
            files_seen=1,
            changed=1,
            ingested=1,
            skipped=0,
            conflicts=0,
            errors=0,
            missing=0,
            folders_walked=1,
            folders_skipped_cold=0,
            written_back=0,
            ignored_by_type=0,
            documents=0,
            document_errors=0,
            thumbnails=0,
        )


class FakeReconcile:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.calls: list[bool] = []
        self.error = error

    async def execute(self, deep: bool) -> PdmReconciliationSummary:
        self.calls.append(deep)
        if self.error is not None:
            raise self.error
        return PdmReconciliationSummary(counts={})


class FakeSyncRunRepository:
    """Only latest_by_trigger, the one method _resolve_trigger calls.
    `recorded_triggers` seeds which trigger values
    already have a prior run, so a test can simulate "this vault has
    polled before" without a real PdmSyncRun."""

    def __init__(self, recorded_triggers: set[str] | None = None) -> None:
        self.recorded_triggers = recorded_triggers or set()

    async def latest_by_trigger(self, trigger: str) -> object | None:
        return object() if trigger in self.recorded_triggers else None


class TestRunPdmPollIfDue:
    async def test_not_enabled_does_nothing(self) -> None:
        repo = FakeAdminSettingsRepository(make_pdm_settings(enabled=False))
        lock = FakeLock()
        poll = FakePoll()

        result = await RunPdmPollIfDue(
            repo, lock, poll, FakeReconcile(), FakeSyncRunRepository(), uow=FakeUnitOfWork()
        ).execute()

        assert result is None
        assert poll.calls == 0
        assert lock.attempts == 0

    async def test_not_configured_does_nothing(self) -> None:
        repo = FakeAdminSettingsRepository(make_pdm_settings(password=None))
        lock = FakeLock()
        poll = FakePoll()

        result = await RunPdmPollIfDue(
            repo, lock, poll, FakeReconcile(), FakeSyncRunRepository(), uow=FakeUnitOfWork()
        ).execute()

        assert result is None
        assert poll.calls == 0

    async def test_not_yet_due_does_nothing(self) -> None:
        recent = datetime.now(UTC) - timedelta(minutes=1)
        repo = FakeAdminSettingsRepository(
            make_pdm_settings(last_poll_at=recent, poll_interval_minutes=15)
        )
        lock = FakeLock()
        poll = FakePoll()

        result = await RunPdmPollIfDue(
            repo, lock, poll, FakeReconcile(), FakeSyncRunRepository(), uow=FakeUnitOfWork()
        ).execute()

        assert result is None
        assert poll.calls == 0
        assert lock.attempts == 0

    async def test_never_polled_is_due(self) -> None:
        repo = FakeAdminSettingsRepository(make_pdm_settings(last_poll_at=None))
        lock = FakeLock()
        poll = FakePoll()

        result = await RunPdmPollIfDue(
            repo, lock, poll, FakeReconcile(), FakeSyncRunRepository(), uow=FakeUnitOfWork()
        ).execute()

        assert result is not None
        assert poll.calls == 1

    async def test_genuinely_never_polled_derives_initial_trigger(self) -> None:
        """A vault with last_poll_at=None AND no prior scheduled/manual run
        recorded at all is genuinely on its first poll ever, so it must not
        be labelled `manual`."""
        repo = FakeAdminSettingsRepository(make_pdm_settings(last_poll_at=None))
        lock = FakeLock()
        poll = FakePoll()

        await RunPdmPollIfDue(
            repo, lock, poll, FakeReconcile(), FakeSyncRunRepository(), uow=FakeUnitOfWork()
        ).execute()

        assert poll.triggers == [PdmSyncTrigger.INITIAL]

    async def test_manually_cleared_last_poll_at_derives_manual_trigger(self) -> None:
        """RequestPdmPoll (the admin "sync now" action) clears
        last_poll_at to force an immediate poll, indistinguishable from a
        genuinely-first-ever poll by last_poll_at alone, so RunPdmPollIfDue
        also checks the run log: a prior scheduled run here means the
        vault has been polled before, so this clear must be the manual
        request, not a first poll."""
        repo = FakeAdminSettingsRepository(make_pdm_settings(last_poll_at=None))
        lock = FakeLock()
        poll = FakePoll()
        run_repo = FakeSyncRunRepository(recorded_triggers={"scheduled"})

        await RunPdmPollIfDue(
            repo, lock, poll, FakeReconcile(), run_repo, uow=FakeUnitOfWork()
        ).execute()

        assert poll.triggers == [PdmSyncTrigger.MANUAL]

    async def test_prior_manual_run_also_derives_manual_trigger(self) -> None:
        repo = FakeAdminSettingsRepository(make_pdm_settings(last_poll_at=None))
        lock = FakeLock()
        poll = FakePoll()
        run_repo = FakeSyncRunRepository(recorded_triggers={"manual"})

        await RunPdmPollIfDue(
            repo, lock, poll, FakeReconcile(), run_repo, uow=FakeUnitOfWork()
        ).execute()

        assert poll.triggers == [PdmSyncTrigger.MANUAL]

    async def test_due_and_lock_acquired_runs_poll(self) -> None:
        stale = datetime.now(UTC) - timedelta(minutes=30)
        repo = FakeAdminSettingsRepository(
            make_pdm_settings(last_poll_at=stale, poll_interval_minutes=15)
        )
        lock = FakeLock(acquirable=True)
        poll = FakePoll()

        result = await RunPdmPollIfDue(
            repo, lock, poll, FakeReconcile(), FakeSyncRunRepository(), uow=FakeUnitOfWork()
        ).execute()

        assert poll.calls == 1
        assert lock.attempts == 1
        assert result is not None
        assert result.files_seen == 1

    async def test_ordinary_due_tick_derives_scheduled_trigger(self) -> None:
        stale = datetime.now(UTC) - timedelta(minutes=30)
        repo = FakeAdminSettingsRepository(
            make_pdm_settings(last_poll_at=stale, poll_interval_minutes=15)
        )
        lock = FakeLock(acquirable=True)
        poll = FakePoll()

        await RunPdmPollIfDue(
            repo, lock, poll, FakeReconcile(), FakeSyncRunRepository(), uow=FakeUnitOfWork()
        ).execute()

        assert poll.triggers == [PdmSyncTrigger.SCHEDULED]

    async def test_due_but_lock_not_acquired_skips(self) -> None:
        stale = datetime.now(UTC) - timedelta(minutes=30)
        repo = FakeAdminSettingsRepository(
            make_pdm_settings(last_poll_at=stale, poll_interval_minutes=15)
        )
        lock = FakeLock(acquirable=False)
        poll = FakePoll()

        result = await RunPdmPollIfDue(
            repo, lock, poll, FakeReconcile(), FakeSyncRunRepository(), uow=FakeUnitOfWork()
        ).execute()

        assert result is None
        assert poll.calls == 0
        assert lock.attempts == 1


class TestReconciliationTick:
    async def test_queued_quick_reconciliation_runs_and_clears_the_flag(self) -> None:
        repo = FakeAdminSettingsRepository(
            make_pdm_settings(last_poll_at=datetime.now(UTC), reconcile_requested_deep=False)
        )
        lock = FakeLock()
        poll = FakePoll()
        reconcile = FakeReconcile()

        await RunPdmPollIfDue(
            repo, lock, poll, reconcile, FakeSyncRunRepository(), uow=FakeUnitOfWork()
        ).execute()

        assert reconcile.calls == [False]
        assert repo.reconcile_requested_calls == [None]
        assert repo.pdm.reconcile_requested_deep is None

    async def test_queued_deep_reconciliation_passes_deep_flag(self) -> None:
        repo = FakeAdminSettingsRepository(
            make_pdm_settings(last_poll_at=datetime.now(UTC), reconcile_requested_deep=True)
        )
        lock = FakeLock()
        poll = FakePoll()
        reconcile = FakeReconcile()

        await RunPdmPollIfDue(
            repo, lock, poll, reconcile, FakeSyncRunRepository(), uow=FakeUnitOfWork()
        ).execute()

        assert reconcile.calls == [True]

    async def test_nothing_queued_never_calls_reconcile(self) -> None:
        repo = FakeAdminSettingsRepository(
            make_pdm_settings(last_poll_at=datetime.now(UTC), reconcile_requested_deep=None)
        )
        lock = FakeLock()
        poll = FakePoll()
        reconcile = FakeReconcile()

        await RunPdmPollIfDue(
            repo, lock, poll, reconcile, FakeSyncRunRepository(), uow=FakeUnitOfWork()
        ).execute()

        assert reconcile.calls == []
        assert repo.reconcile_requested_calls == []

    async def test_lock_not_acquired_leaves_the_flag_queued(self) -> None:
        repo = FakeAdminSettingsRepository(
            make_pdm_settings(last_poll_at=datetime.now(UTC), reconcile_requested_deep=False)
        )
        lock = FakeLock(acquirable=False)
        poll = FakePoll()
        reconcile = FakeReconcile()

        await RunPdmPollIfDue(
            repo, lock, poll, reconcile, FakeSyncRunRepository(), uow=FakeUnitOfWork()
        ).execute()

        assert reconcile.calls == []
        assert repo.reconcile_requested_calls == []
        assert repo.pdm.reconcile_requested_deep is False

    async def test_failed_reconciliation_still_clears_the_flag(self) -> None:
        repo = FakeAdminSettingsRepository(
            make_pdm_settings(last_poll_at=datetime.now(UTC), reconcile_requested_deep=True)
        )
        lock = FakeLock()
        poll = FakePoll()
        reconcile = FakeReconcile(error=RuntimeError("vault unreachable"))

        # Must not raise: RunPdmPollIfDue is the scheduler's own tick
        # handler, a reconciliation failure must never take the tick down.
        await RunPdmPollIfDue(
            repo, lock, poll, reconcile, FakeSyncRunRepository(), uow=FakeUnitOfWork()
        ).execute()

        assert reconcile.calls == [True]
        assert repo.pdm.reconcile_requested_deep is None

    async def test_disabled_integration_never_touches_the_flag(self) -> None:
        repo = FakeAdminSettingsRepository(
            make_pdm_settings(enabled=False, reconcile_requested_deep=False)
        )
        lock = FakeLock()
        poll = FakePoll()
        reconcile = FakeReconcile()

        await RunPdmPollIfDue(
            repo, lock, poll, reconcile, FakeSyncRunRepository(), uow=FakeUnitOfWork()
        ).execute()

        assert reconcile.calls == []
        assert repo.reconcile_requested_calls == []

    async def test_reconciliation_runs_before_the_poll_due_check(self) -> None:
        """A queued reconciliation runs even when the poll itself is not
        yet due: the two checks are independent, per the module
        docstring."""
        recent = datetime.now(UTC) - timedelta(minutes=1)
        repo = FakeAdminSettingsRepository(
            make_pdm_settings(
                last_poll_at=recent, poll_interval_minutes=15, reconcile_requested_deep=False
            )
        )
        lock = FakeLock()
        poll = FakePoll()
        reconcile = FakeReconcile()

        result = await RunPdmPollIfDue(
            repo, lock, poll, reconcile, FakeSyncRunRepository(), uow=FakeUnitOfWork()
        ).execute()

        assert reconcile.calls == [False]
        assert result is None  # the poll itself still was not due
        assert poll.calls == 0

    async def test_reconciliation_and_a_due_poll_both_run_on_the_same_tick(self) -> None:
        stale = datetime.now(UTC) - timedelta(minutes=30)
        repo = FakeAdminSettingsRepository(
            make_pdm_settings(
                last_poll_at=stale, poll_interval_minutes=15, reconcile_requested_deep=False
            )
        )
        lock = FakeLock()
        poll = FakePoll()
        reconcile = FakeReconcile()

        result = await RunPdmPollIfDue(
            repo, lock, poll, reconcile, FakeSyncRunRepository(), uow=FakeUnitOfWork()
        ).execute()

        assert reconcile.calls == [False]
        assert result is not None
        assert poll.calls == 1
        # Reconciliation and the poll each take the tick lock separately.
        assert lock.attempts == 2
