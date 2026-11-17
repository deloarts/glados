"""App-wide "one run at a time" mutex plus the shared run state of a
long-running background job, in one Redis key per job kind. Auto-Plan and the
storage migration each own a registry. It is a UX gate only, and without Redis
everything here degrades to a logged no-op.

The key holds the run state as JSON, acquired with SET NX PX and kept alive
by a heartbeat. Release and heartbeat compare the run_id in a Lua script, so
a late release can never delete the next holder's lock. The snapshot is
updated in memory only, under a threading lock never held across an await,
so a run can call it cheaply from any point of its work, including while it
holds row locks.
"""

import json
import threading
import uuid
from collections.abc import Awaitable
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field
from typing import cast

import redis
import redis.asyncio

from src.modules.platform.infrastructure.logging.logger import log
from src.shared_kernel.domain.services.clock import now_utc

# Kept next to the TTL it must stay well under.
HEARTBEAT_INTERVAL_S = 10.0

TTL_MS = 30_000

# KEYS[1] = run key, ARGV[1] = our run_id. Deletes only while the key still
# names our run.
_RELEASE_SCRIPT = """
local raw = redis.call('GET', KEYS[1])
if not raw then
  return 0
end
local ok, decoded = pcall(cjson.decode, raw)
if not ok or decoded['run_id'] ~= ARGV[1] then
  return 0
end
redis.call('DEL', KEYS[1])
return 1
"""

# KEYS[1] = run key, ARGV[1] = run_id, ARGV[2] = value, ARGV[3] = TTL in ms.
# Refreshes only while we still hold the key.
_HEARTBEAT_SCRIPT = """
local raw = redis.call('GET', KEYS[1])
if not raw then
  return 0
end
local ok, decoded = pcall(cjson.decode, raw)
if not ok or decoded['run_id'] ~= ARGV[1] then
  return 0
end
redis.call('SET', KEYS[1], ARGV[2], 'PX', ARGV[3])
return 1
"""


@dataclass
class RunSnapshot:
    """The in-memory progress state a run's handle carries. `detail` names
    the item being worked on, such as the file a migration is copying."""

    stage: str | None = None
    current: int | None = None
    total: int | None = None
    detail: str | None = None


@dataclass
class RunHandle:
    """A run's handle. A degraded handle, minted after a Redis error, makes
    every later call a no-op.
    """

    run_id: str
    user_id: int
    user_name: str
    started_at: str
    degraded: bool = False
    snapshot: RunSnapshot = field(default_factory=RunSnapshot)
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)


@dataclass
class RunState:
    """The run key's contents, decoded: what `read()` returns for a status
    endpoint, available to any authenticated caller."""

    run_id: str
    user_id: int
    user_name: str
    started_at: str
    stage: str | None
    current: int | None
    total: int | None
    detail: str | None = None


def update_snapshot(
    handle: RunHandle,
    stage: str,
    current: int | None,
    total: int | None,
    detail: str | None = None,
) -> None:
    """In-memory only, so it is safe while row locks are held."""
    with handle.lock:
        handle.snapshot.stage = stage
        handle.snapshot.current = current
        handle.snapshot.total = total
        handle.snapshot.detail = detail


def _encode(handle: RunHandle) -> str:
    with handle.lock:
        snapshot = handle.snapshot
        payload = {
            "run_id": handle.run_id,
            "user_id": handle.user_id,
            "user_name": handle.user_name,
            "started_at": handle.started_at,
            "stage": snapshot.stage,
            "current": snapshot.current,
            "total": snapshot.total,
            "detail": snapshot.detail,
        }
    return json.dumps(payload)


class RunRegistry:
    """The mutex and run state of one job kind. `client` is called on every
    command rather than once, so the owning module can swap its Redis client
    at runtime, which the tests rely on."""

    def __init__(self, key: str, label: str, client: Callable[[], redis.asyncio.Redis]) -> None:
        self.key = key
        self._label = label
        self._client = client

    async def _eval(self, script: str, *args: str) -> object:
        # redis-py types eval on the async client as "awaitable or plain
        # value"; on redis.asyncio it is always awaitable.
        return await cast("Awaitable[object]", self._client().eval(script, 1, self.key, *args))

    async def try_acquire(self, user_id: int, user_name: str) -> RunHandle | None:
        """Tries to become the sole runner; None when another run holds the
        mutex. On a Redis error the run proceeds unguarded with a degraded
        handle.
        """
        handle = RunHandle(
            run_id=uuid.uuid4().hex,
            user_id=user_id,
            user_name=user_name,
            started_at=now_utc().isoformat(),
        )
        try:
            acquired = await self._client().set(self.key, _encode(handle), nx=True, px=TTL_MS)
        except redis.RedisError:
            log.warning(
                "%s run registry: try_acquire failed, degrading to unguarded run.", self._label
            )
            handle.degraded = True
            return handle
        return handle if acquired else None

    async def heartbeat_once(self, handle: RunHandle) -> None:
        """Persists the snapshot and refreshes the TTL, silently skipping a
        key that no longer names our run.
        """
        if handle.degraded:
            return
        try:
            await self._eval(_HEARTBEAT_SCRIPT, handle.run_id, _encode(handle), str(TTL_MS))
        except redis.RedisError:
            log.warning("%s run registry: heartbeat failed for run %s.", self._label, handle.run_id)

    async def release(self, handle: RunHandle) -> None:
        """Compare-and-delete on run_id, so a late release never deletes the
        next holder's lock."""
        if handle.degraded:
            return
        try:
            await self._eval(_RELEASE_SCRIPT, handle.run_id)
        except redis.RedisError:
            log.warning("%s run registry: release failed for run %s.", self._label, handle.run_id)

    async def read(self) -> RunState | None:
        """The current run for a status endpoint; an unreadable key counts as
        no run."""
        try:
            raw = await self._client().get(self.key)
        except redis.RedisError:
            log.warning("%s run registry: read failed.", self._label)
            return None
        if raw is None:
            return None
        if not isinstance(raw, str):
            log.warning(
                "%s run registry: read got a non-string value, treating as no run.", self._label
            )
            return None
        try:
            data = json.loads(raw)
            return RunState(
                run_id=data["run_id"],
                user_id=data["user_id"],
                user_name=data["user_name"],
                started_at=data["started_at"],
                stage=data.get("stage"),
                current=data.get("current"),
                total=data.get("total"),
                detail=data.get("detail"),
            )
        except (json.JSONDecodeError, KeyError, TypeError):
            log.warning("%s run registry: malformed run state, treating as no run.", self._label)
            return None
