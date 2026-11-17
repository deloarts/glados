"""
Unit tests for src/modules/fulfillment/infrastructure/autoplan_run_registry.py: the app-wide
"one auto-plan run at a time" mutex plus the shared run state everyone
else reads. No Redis server: the client is replaced with an in-memory
fake extending the shared FakeRedis from test_event_bus.py, the way
test_outbox_relay.py does, with just enough of SET/GET/DEL/EVAL added to
exercise the module's own CAS Lua scripts without a real Lua interpreter.
"""

import json

import pytest
import redis

from src.modules.fulfillment.infrastructure import autoplan_run_registry as registry
from tests.unit.test_event_bus import FakeRedis as StreamFakeRedis


class FakeRedis(StreamFakeRedis):
    """Extends the shared stream-publisher fake (xadd, `self.calls`,
    `self.fail`) with the string commands the run registry needs.

    Simulates the exact CAS semantics of both Lua scripts the module
    ships (_RELEASE_SCRIPT deletes iff the stored run_id matches ours;
    _HEARTBEAT_SCRIPT rewrites+re-arms the TTL iff the stored run_id
    matches ours) by dispatching on argument count: release passes
    (key, run_id) and heartbeat passes (key, run_id, value, ttl_ms), rather
    than running real Lua, since neither script's behaviour depends on
    anything beyond that one comparison.
    """

    def __init__(self, fail: bool = False) -> None:
        super().__init__(fail=fail)
        self.store: dict[str, str] = {}
        self.ttls: dict[str, int] = {}
        # Every non-xadd command invoked, in order, so tests can assert
        # "zero Redis I/O" for update_snapshot, which must never touch this at all.
        self.commands: list[str] = []

    def _maybe_fail(self) -> None:
        if self.fail:
            raise redis.ConnectionError("redis is down")

    async def set(self, name, value, nx=False, px=None):
        self.commands.append("SET")
        self._maybe_fail()
        if nx and name in self.store:
            return None
        self.store[name] = value
        if px is not None:
            self.ttls[name] = px
        return True

    async def get(self, name):
        self.commands.append("GET")
        self._maybe_fail()
        return self.store.get(name)

    async def delete(self, name):
        self.commands.append("DEL")
        self._maybe_fail()
        existed = name in self.store
        self.store.pop(name, None)
        self.ttls.pop(name, None)
        return 1 if existed else 0

    async def eval(self, script, numkeys, *keys_and_args):
        self.commands.append("EVAL")
        self._maybe_fail()
        key, run_id = keys_and_args[0], keys_and_args[1]
        raw = self.store.get(key)
        if raw is None:
            return 0
        decoded = json.loads(raw)
        if decoded.get("run_id") != run_id:
            return 0
        if len(keys_and_args) == 2:  # _RELEASE_SCRIPT: (key, run_id)
            self.store.pop(key, None)
            self.ttls.pop(key, None)
        else:  # _HEARTBEAT_SCRIPT: (key, run_id, value, ttl_ms)
            value, ttl_ms = keys_and_args[2], keys_and_args[3]
            self.store[key] = value
            self.ttls[key] = int(ttl_ms)
        return 1


@pytest.fixture
def fake_redis(monkeypatch) -> FakeRedis:
    fake = FakeRedis()
    monkeypatch.setattr(registry, "get_async_redis_client", lambda: fake)
    return fake


# ── Acquire / release ───────────────────────────────────────────────────


async def test_acquire_second_acquire_returns_none_then_release_frees_it(fake_redis):
    first = await registry.try_acquire(user_id=1, user_name="Alice")
    assert first is not None
    assert not first.degraded

    second = await registry.try_acquire(user_id=2, user_name="Bob")
    assert second is None  # the mutex is already held

    await registry.release(first)

    third = await registry.try_acquire(user_id=2, user_name="Bob")
    assert third is not None  # freed by the release above


async def test_release_does_not_delete_a_slot_retaken_under_a_different_run_id(fake_redis):
    first = await registry.try_acquire(user_id=1, user_name="Alice")
    assert first is not None

    # Simulate the TTL lapsing (a killed worker never got to release) by
    # dropping the key directly, the same end state that PX 30000 reaches.
    fake_redis.store.pop(registry.RUN_KEY, None)

    second = await registry.try_acquire(user_id=2, user_name="Bob")
    assert second is not None
    assert second.run_id != first.run_id

    # The first run's release call, arriving late, must be a no-op: it
    # must NOT delete the second run's still-active slot.
    await registry.release(first)

    state = await registry.read()
    assert state is not None
    assert state.run_id == second.run_id


# ── Heartbeat ────────────────────────────────────────────────────────────


async def test_heartbeat_refreshes_the_ttl_and_persists_the_snapshot(fake_redis):
    handle = await registry.try_acquire(user_id=1, user_name="Alice")
    assert handle is not None
    fake_redis.ttls[registry.RUN_KEY] = 1  # pretend the TTL is about to lapse

    registry.update_snapshot(handle, stage="candidates", current=3, total=10)
    await registry.heartbeat_once(handle)

    assert fake_redis.ttls[registry.RUN_KEY] == registry._TTL_MS
    stored = json.loads(fake_redis.store[registry.RUN_KEY])
    assert stored["run_id"] == handle.run_id
    assert stored["stage"] == "candidates"
    assert stored["current"] == 3
    assert stored["total"] == 10


async def test_heartbeat_does_not_refresh_a_slot_retaken_by_someone_else(fake_redis):
    first = await registry.try_acquire(user_id=1, user_name="Alice")
    assert first is not None
    fake_redis.store.pop(registry.RUN_KEY, None)  # TTL lapsed
    second = await registry.try_acquire(user_id=2, user_name="Bob")
    assert second is not None

    await registry.heartbeat_once(first)  # late heartbeat from the dead run

    state = await registry.read()
    assert state is not None
    assert state.run_id == second.run_id  # untouched by the stale heartbeat


# ── update_snapshot is in-memory only ────────────────────────────────────


async def test_update_snapshot_performs_no_redis_io(fake_redis):
    handle = await registry.try_acquire(user_id=1, user_name="Alice")
    assert handle is not None
    fake_redis.commands.clear()

    registry.update_snapshot(handle, stage="scoring", current=5, total=20)

    assert fake_redis.commands == []  # zero Redis calls
    assert handle.snapshot.stage == "scoring"
    assert handle.snapshot.current == 5
    assert handle.snapshot.total == 20


# ── Redis unavailable ─────────────────────────────────────────────────────


async def test_try_acquire_returns_a_degraded_handle_on_redis_error(fake_redis):
    fake_redis.fail = True

    handle = await registry.try_acquire(user_id=1, user_name="Alice")

    assert handle is not None
    assert handle.degraded


async def test_heartbeat_once_does_not_raise_when_redis_fails(fake_redis):
    handle = await registry.try_acquire(user_id=1, user_name="Alice")
    assert handle is not None
    fake_redis.fail = True

    await registry.heartbeat_once(handle)  # must not raise

    # The failed heartbeat leaves the run's key as it was.
    fake_redis.fail = False
    state = await registry.read()
    assert state is not None
    assert state.run_id == handle.run_id


async def test_release_does_not_raise_when_redis_fails(fake_redis):
    handle = await registry.try_acquire(user_id=1, user_name="Alice")
    assert handle is not None
    fake_redis.fail = True

    await registry.release(handle)  # must not raise

    # The failed release leaves the key to expire with its TTL.
    fake_redis.fail = False
    state = await registry.read()
    assert state is not None
    assert state.run_id == handle.run_id


async def test_read_returns_none_when_redis_fails(fake_redis):
    fake_redis.fail = True

    assert await registry.read() is None


async def test_operations_on_a_degraded_handle_are_noops(fake_redis):
    fake_redis.fail = True
    handle = await registry.try_acquire(user_id=1, user_name="Alice")
    assert handle is not None
    assert handle.degraded

    fake_redis.fail = False  # Redis "recovers", the degraded handle stays inert
    fake_redis.commands.clear()  # drop the failed SET attempt from try_acquire above
    await registry.heartbeat_once(handle)
    await registry.release(handle)

    assert fake_redis.store == {}
    assert fake_redis.commands == []


# ── read() ────────────────────────────────────────────────────────────────


async def test_read_returns_none_when_no_run_is_active(fake_redis):
    assert await registry.read() is None


async def test_read_returns_the_current_run_state(fake_redis):
    handle = await registry.try_acquire(user_id=1, user_name="Alice")
    assert handle is not None
    registry.update_snapshot(handle, stage="candidates", current=1, total=4)
    await registry.heartbeat_once(handle)

    state = await registry.read()

    assert state is not None
    assert state.run_id == handle.run_id
    assert state.user_id == 1
    assert state.user_name == "Alice"
    assert state.started_at == handle.started_at
    assert state.stage == "candidates"
    assert state.current == 1
    assert state.total == 4


async def test_read_returns_none_on_a_malformed_value(fake_redis):
    fake_redis.store[registry.RUN_KEY] = "not json"

    assert await registry.read() is None


async def test_read_returns_none_when_the_value_is_valid_json_but_missing_fields(fake_redis):
    fake_redis.store[registry.RUN_KEY] = json.dumps({"unexpected": "shape"})

    assert await registry.read() is None
