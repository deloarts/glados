"""
Unit tests for OutboxRelay: ordering, at-least-once delivery, the stable
event_id that keeps at-least-once from becoming at-least-twice-observed, the
advisory-lock guard, and the supervisor loop's resilience.

No Redis and no database: the outbox is a fake implementing IEventOutbox, and
the transport is the same FakeRedis the transport tests use, wrapped in the
real RedisStreamEventBus so publish_raw's field layout is exercised for real.
"""

import asyncio
import logging

import pytest
import redis

from src.modules.platform.adapters.outbound.external.event_bus.redis_stream_event_bus import (
    RedisStreamEventBus,
)
from src.modules.platform.infrastructure.events import outbox_relay as relay_module
from src.modules.platform.infrastructure.events.outbox_relay import OutboxRelay
from src.modules.platform.ports.outbound.event_outbox_port import OutboxMessage
from tests.unit.test_event_bus import FakeRedis


class FakeOutbox:
    """In-memory IEventOutbox. `rows` is the table, oldest id first."""

    def __init__(
        self,
        rows: list[OutboxMessage] | None = None,
        *,
        locked_by_someone_else: bool = False,
    ) -> None:
        self.rows = list(rows or [])
        self.published: dict[int, bool] = {}
        self.failures: list[tuple[int, str]] = []
        self.attempts: dict[int, int] = {}
        self.purged_before: list[object] = []
        self.opened = 0
        self.closed = 0
        self._locked_by_someone_else = locked_by_someone_else

    # IEventOutbox
    async def try_lock(self) -> bool:
        return not self._locked_by_someone_else

    async def fetch_unpublished(self, limit: int) -> list[OutboxMessage]:
        pending = [r for r in self.rows if not self.published.get(r.id)]
        return sorted(pending, key=lambda r: r.id)[:limit]

    async def mark_published(self, ids) -> None:
        for message_id in ids:
            self.published[message_id] = True

    async def record_failure(self, message_id: int, error: str) -> int:
        self.failures.append((message_id, error))
        self.attempts[message_id] = self.attempts.get(message_id, 0) + 1
        return self.attempts[message_id]

    async def purge_published(self, older_than) -> int:
        self.purged_before.append(older_than)
        return 0

    # context-manager factory shape the relay is constructed with
    def factory(self):
        outbox = self

        class _Ctx:
            async def __aenter__(self):
                outbox.opened += 1
                return outbox

            async def __aexit__(self, *exc):
                outbox.closed += 1
                return False

        return _Ctx()


def _message(message_id: int, event_id: str | None = None, attempts: int = 0) -> OutboxMessage:
    return OutboxMessage(
        id=message_id,
        event_id=event_id or f"evt-{message_id}",
        event_type="ProjectCreated",
        payload=f'{{"project_id": {message_id}}}',
        attempts=attempts,
    )


def _relay(outbox: FakeOutbox, fake_redis: FakeRedis) -> OutboxRelay:
    transport = RedisStreamEventBus(fake_redis)  # type: ignore[arg-type]

    async def publish(message: OutboxMessage) -> None:
        await transport.publish_raw(
            event_id=message.event_id,
            event_type=message.event_type,
            payload=message.payload,
        )

    return OutboxRelay(outbox.factory, publish)


async def test_relay_publishes_unpublished_rows_in_id_order():
    """Rows are inserted out of order to prove the relay sorts by id, which is
    the intended publish order, not by whatever the fetch happened to return."""
    outbox = FakeOutbox([_message(3), _message(1), _message(2)])
    fake = FakeRedis()

    relayed = await _relay(outbox, fake)._tick()

    assert relayed == 3
    assert [fields["event_id"] for _stream, fields in fake.calls] == ["evt-1", "evt-2", "evt-3"]
    assert all(fields["type"] == "ProjectCreated" for _stream, fields in fake.calls)


async def test_relay_marks_rows_published_and_does_not_republish_them():
    outbox = FakeOutbox([_message(1), _message(2)])
    fake = FakeRedis()
    relay = _relay(outbox, fake)

    await relay._tick()
    second_tick = await relay._tick()

    assert second_tick == 0
    assert len(fake.calls) == 2  # no XADD on the second tick
    assert outbox.published == {1: True, 2: True}


async def test_relay_leaves_the_row_unpublished_when_xadd_fails():
    outbox = FakeOutbox([_message(1)])
    fake = FakeRedis(fail=True)
    relay = _relay(outbox, fake)

    with pytest.raises(redis.RedisError):
        await relay._tick()

    assert outbox.published == {}  # still NULL published_at
    assert outbox.attempts == {1: 1}
    assert outbox.failures[0][0] == 1
    assert "ConnectionError" in outbox.failures[0][1]

    # Next tick retries the same row once the transport recovers.
    async def recovered_publish(message: OutboxMessage) -> None:
        fake.calls.append((None, {"event_id": message.event_id}))

    relay._publish = recovered_publish
    assert await relay._tick() == 1


async def test_relay_stops_the_batch_at_the_first_failure_to_preserve_order():
    class FlakyRedis(FakeRedis):
        async def xadd(self, stream, fields, maxlen=None, approximate=None):
            if fields["event_id"] == "evt-2":
                raise redis.ConnectionError("redis is down")
            return await super().xadd(stream, fields, maxlen=maxlen, approximate=approximate)

    outbox = FakeOutbox([_message(1), _message(2), _message(3)])
    fake = FlakyRedis()

    with pytest.raises(redis.RedisError):
        await _relay(outbox, fake)._tick()

    assert [fields["event_id"] for _stream, fields in fake.calls] == ["evt-1"]
    assert outbox.published == {1: True}  # row 3 is NOT jumped ahead of row 2


async def test_relay_republish_after_a_crash_reuses_the_same_event_id():
    """The idempotency guarantee. A crash between the XADD and the
    published_at mark leaves the row unpublished, so the next tick publishes
    it again: two stream messages with DIFFERENT Redis ids but the SAME
    producer-assigned event_id, which is what every consumer's guard keys on.
    """
    outbox = FakeOutbox([_message(1, event_id="stable-1")])
    fake = FakeRedis()
    relay = _relay(outbox, fake)

    # First attempt: XADD succeeds, then the process dies before marking it.
    original_mark = outbox.mark_published

    async def crash_before_mark(ids) -> None:
        return None

    outbox.mark_published = crash_before_mark  # type: ignore[method-assign]
    await relay._tick()
    outbox.mark_published = original_mark  # type: ignore[method-assign]

    await relay._tick()  # after restart

    assert len(fake.calls) == 2  # a duplicate stream MESSAGE, as designed
    assert {fields["event_id"] for _stream, fields in fake.calls} == {"stable-1"}


async def test_relay_skips_the_tick_when_the_advisory_lock_is_held():
    outbox = FakeOutbox([_message(1)], locked_by_someone_else=True)
    fake = FakeRedis()

    relayed = await _relay(outbox, fake)._tick()

    assert relayed == 0
    assert fake.calls == []
    assert outbox.published == {}
    assert outbox.closed == 1  # the session is still released


async def test_relay_logs_event_outbox_stuck_once_the_attempt_budget_is_passed(glados_caplog):
    outbox = FakeOutbox([_message(1)])
    outbox.attempts[1] = relay_module._STUCK_AFTER_ATTEMPTS - 1
    fake = FakeRedis(fail=True)

    with pytest.raises(redis.RedisError):
        await _relay(outbox, fake)._tick()

    (record,) = [r for r in glados_caplog.records if r.levelno == logging.ERROR]
    assert "EVENT_OUTBOX_STUCK" in record.getMessage()
    assert "evt-1" in record.getMessage()


async def test_relay_survives_an_unexpected_exception_and_backs_off(monkeypatch):
    """Mirrors EventWorker's guard: the component that exists so events are
    never lost must not be killable by one unexpected exception."""
    real_sleep = asyncio.sleep
    slept: list[float] = []
    ticks = []

    async def fake_sleep(delay, *args, **kwargs):
        slept.append(delay)
        if len(slept) >= 3:
            raise asyncio.CancelledError
        return await real_sleep(0)

    monkeypatch.setattr(relay_module.asyncio, "sleep", fake_sleep)

    outbox = FakeOutbox()
    relay = _relay(outbox, FakeRedis())

    async def exploding_tick() -> int:
        ticks.append(1)
        raise TypeError("unexpected outbox reply shape")

    monkeypatch.setattr(relay, "_tick", exploding_tick)

    with pytest.raises(asyncio.CancelledError):
        await relay.run()

    assert len(ticks) >= 2  # kept going after the first failure
    assert slept[0] == relay_module._ERROR_BACKOFF_S


async def test_relay_still_propagates_cancellation(monkeypatch):
    relay = _relay(FakeOutbox(), FakeRedis())

    async def cancelling_tick() -> int:
        raise asyncio.CancelledError

    monkeypatch.setattr(relay, "_tick", cancelling_tick)

    with pytest.raises(asyncio.CancelledError):
        await relay.run()
