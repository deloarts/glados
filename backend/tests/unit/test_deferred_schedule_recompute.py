"""
The schedule recompute in the request and in the background: deferred, a
write's request draws a generation and stages one event without walking; the
worker's walk skips a generation a walk covered and walks one it did not;
every walk takes the lock, also without a coordinator; and the periodic tick
walks every 15 minutes and on a new tenant day only.
"""

from contextlib import asynccontextmanager
from datetime import UTC
from datetime import date
from datetime import datetime
from typing import Any

import pytest

from src.modules.fulfillment.adapters.outbound.external.schedules.schedule_tick import ScheduleTick
from src.modules.fulfillment.application.use_cases.production_schedule.recompute_machine_schedule import (
    RecomputeMachineSchedule,
)
from src.modules.fulfillment.domain.events.schedule_events import ScheduleRecomputeRequested


class _Counter:
    def __init__(self, processed: int = 0) -> None:
        self.generation = 0
        self.processed = processed

    async def increment_generation(self) -> int:
        self.generation += 1
        return self.generation

    async def processed_generation(self) -> int:
        return self.processed

    async def current_generation(self) -> int:
        return self.generation

    async def mark_processed(self, generation: int) -> None:
        self.processed = generation

    stale: datetime | None = None

    async def mark_stale(self, at: datetime) -> None:
        self.stale = self.stale or at

    async def take_stale_since(self) -> datetime | None:
        taken, self.stale = self.stale, None
        return taken

    async def stale_since(self) -> datetime | None:
        return self.stale


class _Lock:
    def __init__(self) -> None:
        self.taken = 0

    @asynccontextmanager
    async def lock(self) -> Any:
        self.taken += 1
        yield


class _Bus:
    def __init__(self) -> None:
        self.published: list[object] = []

    async def publish(self, event: object) -> None:
        self.published.append(event)


class _Uow:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        pass


class _Orders:
    def __init__(self) -> None:
        self.reads = 0

    async def get_all_non_terminal(self) -> list[object]:
        self.reads += 1
        return []


class _Repos:
    def __init__(self) -> None:
        self.orders = _Orders()


def _recompute(**kwargs: Any) -> RecomputeMachineSchedule:
    return RecomputeMachineSchedule(
        _Repos(),  # type: ignore[arg-type]
        machine_repo=None,  # type: ignore[arg-type]
        calendar_repo=None,  # type: ignore[arg-type]
        settings_repo=None,  # type: ignore[arg-type]
        **kwargs,
    )


def _walks(recompute: RecomputeMachineSchedule) -> int:
    return recompute._repos.orders.reads  # type: ignore[attr-defined]


async def test_a_deferred_request_stages_one_event_and_does_not_walk() -> None:
    bus, uow, counter = _Bus(), _Uow(), _Counter()
    recompute = _recompute(
        uow=uow, generation_counter=counter, recompute_lock=_Lock(), event_bus=bus, defer=True
    )

    await recompute.execute_all()

    assert bus.published == [ScheduleRecomputeRequested(generation=1)]
    assert uow.commits == 1
    assert _walks(recompute) == 0


async def test_the_worker_skips_a_generation_a_walk_covered() -> None:
    lock = _Lock()
    recompute = _recompute(
        uow=_Uow(), generation_counter=_Counter(processed=5), recompute_lock=lock
    )

    await recompute.walk_covering(4)

    assert _walks(recompute) == 0
    assert lock.taken == 1


async def test_a_covered_generation_clears_a_mark_no_walk_will_take() -> None:
    counter = _Counter(processed=5)
    counter.generation = 5
    counter.stale = datetime(2026, 10, 27, 8, 0, tzinfo=UTC)
    recompute = _recompute(uow=_Uow(), generation_counter=counter, recompute_lock=_Lock())

    await recompute.walk_covering(5)

    assert _walks(recompute) == 0
    assert counter.stale is None


async def test_a_covered_generation_keeps_the_mark_of_a_newer_request() -> None:
    counter = _Counter(processed=5)
    counter.generation = 6
    counter.stale = datetime(2026, 10, 27, 8, 0, tzinfo=UTC)
    recompute = _recompute(uow=_Uow(), generation_counter=counter, recompute_lock=_Lock())

    await recompute.walk_covering(5)

    assert _walks(recompute) == 0
    assert counter.stale is not None


async def test_the_worker_walks_a_generation_no_walk_covered() -> None:
    counter = _Counter(processed=3)
    counter.generation = 6
    recompute = _recompute(uow=_Uow(), generation_counter=counter, recompute_lock=_Lock())

    await recompute.walk_covering(4)

    assert _walks(recompute) == 1
    assert counter.processed == 6


async def test_a_walk_takes_the_lock_also_without_a_coordinator() -> None:
    lock = _Lock()
    recompute = _recompute(uow=_Uow(), recompute_lock=lock)

    await recompute.execute_all()

    assert (lock.taken, _walks(recompute)) == (1, 1)


async def test_a_request_marks_the_schedule_stale_until_a_walk_begins() -> None:
    counter = _Counter()
    deferred = _recompute(
        uow=_Uow(),
        generation_counter=counter,
        recompute_lock=_Lock(),
        event_bus=_Bus(),
        defer=True,
    )
    await deferred.execute_all()
    marked = counter.stale
    await deferred.execute_all()

    assert marked is not None and counter.stale == marked
    await _recompute(uow=_Uow(), generation_counter=counter, recompute_lock=_Lock()).walk_covering(
        None
    )
    assert counter.stale is None


def test_a_deferred_recompute_needs_the_event_bus() -> None:
    with pytest.raises(ValueError, match="event bus"):
        _recompute(uow=_Uow(), defer=True)


async def test_the_tick_walks_every_15_minutes_and_on_a_new_day() -> None:
    walks: list[float] = []
    now = [0.0]
    today = [date(2026, 10, 25)]

    async def walk() -> None:
        walks.append(now[0])

    async def tenant_today() -> date:
        return today[0]

    tick = ScheduleTick(walk, tenant_today, clock=lambda: now[0])
    for at in (0.0, 60.0, 899.0, 900.0):
        now[0] = at
        await tick()
    today[0] = date(2026, 10, 26)
    now[0] = 960.0
    await tick()

    assert walks == [0.0, 900.0, 960.0]


class _HeldUow(_Uow):
    """A unit of work whose commits are held, as on an Idempotency-Key
    route: effects wait for the commit that ends the hold."""

    def __init__(self) -> None:
        super().__init__()
        self.deferred: list[Any] = []
        self.held = True

    def defer_until_committed(self, effect: Any) -> bool:
        if not self.held:
            return False
        self.deferred.append(effect)
        return True


async def test_a_request_while_commits_are_held_waits_for_the_commit() -> None:
    """The generation must be drawn after the work commits: a walk that
    sampled it before would cover it without seeing the work."""
    bus, uow, counter = _Bus(), _HeldUow(), _Counter()
    recompute = _recompute(
        uow=uow, generation_counter=counter, recompute_lock=_Lock(), event_bus=bus, defer=True
    )

    await recompute.execute_all()

    assert counter.generation == 0
    assert bus.published == []
    assert counter.stale is None
    assert len(uow.deferred) == 1

    uow.held = False
    await uow.deferred[0]()

    assert bus.published == [ScheduleRecomputeRequested(generation=1)]
    assert counter.stale is not None


class _FailingOrders(_Orders):
    async def get_all_non_terminal(self) -> list[object]:
        raise RuntimeError("the walk failed")


async def test_a_failed_walk_puts_the_stale_mark_back() -> None:
    counter = _Counter()
    since = datetime(2026, 10, 26, 9, 0)
    counter.stale = since
    recompute = _recompute(uow=_Uow(), generation_counter=counter, recompute_lock=_Lock())
    recompute._repos.orders = _FailingOrders()  # type: ignore[attr-defined]

    with pytest.raises(RuntimeError):
        await recompute.walk_covering(None)

    assert counter.stale == since


async def test_a_failed_walk_without_a_mark_marks_the_schedule_stale() -> None:
    counter = _Counter()
    recompute = _recompute(uow=_Uow(), generation_counter=counter, recompute_lock=_Lock())
    recompute._repos.orders = _FailingOrders()  # type: ignore[attr-defined]

    with pytest.raises(RuntimeError):
        await recompute.walk_covering(None)

    assert counter.stale is not None


async def test_a_deferred_request_marks_stale_before_it_draws_its_generation() -> None:
    """A walk that covers the generation then takes the mark with it, so no
    false stale mark outlives the walk."""
    calls: list[str] = []

    class _Recording(_Counter):
        async def increment_generation(self) -> int:
            calls.append("increment")
            return await super().increment_generation()

        async def mark_stale(self, at: datetime) -> None:
            calls.append("mark")
            await super().mark_stale(at)

    recompute = _recompute(
        uow=_Uow(),
        generation_counter=_Recording(),
        recompute_lock=_Lock(),
        event_bus=_Bus(),
        defer=True,
    )

    await recompute.execute_all()

    assert calls == ["mark", "increment"]
