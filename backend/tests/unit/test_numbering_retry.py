"""
Unit tests for src/modules/platform/application/services/retry_on_conflict.py: a benign
lot_number / production_order_number race must surface as a transparent
retry (where the write is reconstructible) or a clean 409
NumberingConflictError, never as a raw unhandled IntegrityError.
"""

from collections.abc import Awaitable
from collections.abc import Callable

import pytest
from sqlalchemy.exc import IntegrityError

from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.platform.adapters.outbound.persistence.constraint_violation import (
    SqlConstraintViolationError,
)
from src.modules.platform.application.services.retry_on_conflict import (
    commit_or_raise_numbering_conflict,
)
from src.modules.platform.application.services.retry_on_conflict import commit_with_number_retry
from src.modules.platform.application.services.retry_on_conflict import is_numbering_conflict
from src.modules.platform.domain.exceptions import NumberingConflictError
from tests.unit.fakes import FakeEventBus
from tests.unit.lifecycle.fake_world import FakeWorld


def make_integrity_error(constraint: str) -> SqlConstraintViolationError:
    """An IntegrityError shaped like the one SQLAlchemy raises, whose `orig`
    renders the violated constraint name (the fallback path; drivers that
    expose a structured `diag.constraint_name` are covered separately)."""
    return SqlConstraintViolationError(
        statement="INSERT INTO ...",
        params={},
        orig=Exception(f'duplicate key value violates unique constraint "{constraint}"'),
    )


class _Diag:
    def __init__(self, constraint_name: str) -> None:
        self.constraint_name = constraint_name


class _OrigWithDiag(Exception):
    """Mimics psycopg's error object, which exposes a structured `diag`."""

    def __init__(self, constraint_name: str) -> None:
        super().__init__("some opaque driver message")
        self.diag = _Diag(constraint_name)


class FakeUnitOfWork:
    def __init__(self, fail_on: list[int] | None = None, error: IntegrityError | None = None):
        """fail_on: 1-based commit attempt numbers that should raise."""
        self._fail_on = fail_on or []
        self._error = error or make_integrity_error("lot_table_lot_number_key")
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1
        if self.commits in self._fail_on:
            raise self._error

    async def rollback(self) -> None:
        self.rollbacks += 1


# ── is_numbering_conflict ─────────────────────────────────────────────


class TestIsNumberingConflict:
    def test_matches_lot_number(self):
        assert is_numbering_conflict(make_integrity_error("lot_table_lot_number_key"))

    def test_matches_production_order_number(self):
        assert is_numbering_conflict(
            make_integrity_error("production_order_table_production_order_number_key")
        )

    def test_does_not_match_an_unrelated_constraint(self):
        assert not is_numbering_conflict(make_integrity_error("fk_production_order_machine_id"))

    def test_reads_the_structured_constraint_name_when_the_driver_exposes_one(self):
        error = SqlConstraintViolationError(
            statement="INSERT INTO ...",
            params={},
            orig=_OrigWithDiag("lot_table_lot_number_key"),
        )
        assert is_numbering_conflict(error)


# ── commit_with_number_retry ──────────────────────────────────────────


def _write(calls: list[int]) -> Callable[[], Awaitable[str]]:
    """A write callback that records each run and returns the saved value."""

    async def write() -> str:
        calls.append(1)
        return "lot"

    return write


class TestCommitWithNumberRetry:
    async def test_commits_once_on_the_happy_path(self):
        uow = FakeUnitOfWork()
        calls: list[int] = []

        result = await commit_with_number_retry(uow, _write(calls))

        assert result == "lot"
        assert uow.commits == 1
        assert uow.rollbacks == 0
        assert len(calls) == 1

    async def test_retries_once_on_integrity_error_and_succeeds(self):
        uow = FakeUnitOfWork(fail_on=[1])
        calls: list[int] = []

        result = await commit_with_number_retry(uow, _write(calls))

        assert result == "lot"
        # The write was re-run exactly once to re-derive the number.
        assert len(calls) == 2
        assert uow.commits == 2
        assert uow.rollbacks == 1

    async def test_reraises_after_the_retry_budget(self):
        uow = FakeUnitOfWork(fail_on=[1, 2])
        calls: list[int] = []

        with pytest.raises(NumberingConflictError):
            await commit_with_number_retry(uow, _write(calls))

        assert len(calls) == 2
        assert uow.commits == 2
        assert uow.rollbacks == 2

    async def test_does_not_retry_on_an_unrelated_integrity_error(self):
        uow = FakeUnitOfWork(
            fail_on=[1], error=make_integrity_error("fk_production_order_machine_id")
        )
        calls: list[int] = []

        with pytest.raises(IntegrityError):
            await commit_with_number_retry(uow, _write(calls))

        # Written once, never replayed, never rolled back by the helper.
        assert len(calls) == 1
        assert uow.commits == 1
        assert uow.rollbacks == 0


# ── commit_or_raise_numbering_conflict ────────────────────────────────


class TestCommitOrRaiseNumberingConflict:
    async def test_commits_cleanly_on_the_happy_path(self):
        uow = FakeUnitOfWork()
        await commit_or_raise_numbering_conflict(uow)
        assert uow.commits == 1
        assert uow.rollbacks == 0

    async def test_maps_a_numbering_conflict_to_a_clean_domain_error(self):
        uow = FakeUnitOfWork(
            fail_on=[1],
            error=make_integrity_error("production_order_table_production_order_number_key"),
        )
        with pytest.raises(NumberingConflictError):
            await commit_or_raise_numbering_conflict(uow)
        # Never replayed: this variant exists precisely because the write
        # cannot be safely re-run.
        assert uow.commits == 1
        assert uow.rollbacks == 1

    async def test_propagates_an_unrelated_integrity_error_unchanged(self):
        uow = FakeUnitOfWork(fail_on=[1], error=make_integrity_error("ck_some_check"))
        with pytest.raises(IntegrityError):
            await commit_or_raise_numbering_conflict(uow)
        assert uow.rollbacks == 0


async def test_a_retry_locks_the_lifecycle_rows_again_after_the_rollback() -> None:
    # The rollback released the locks, so a retry that took the rows as
    # still held would write them unlocked.
    world = FakeWorld()
    demand = world.bought_demand()
    reconciler = LifecycleReconciler(world.repositories, FakeEventBus())

    async def write() -> None:
        reconciler.touch_demands(LifecycleAggregate.BOUGHT_DEMANDS, [demand.id])
        await reconciler.lock_touched()

    await commit_with_number_retry(FakeUnitOfWork(fail_on=[1]), write, reconciler=reconciler)

    assert world.lock_log == [
        (LifecycleAggregate.BOUGHT_DEMANDS, (demand.id,)),
        (LifecycleAggregate.BOUGHT_DEMANDS, (demand.id,)),
    ]
