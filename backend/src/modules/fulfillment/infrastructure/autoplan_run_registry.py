"""App-wide "one Auto-Plan run at a time" mutex plus the shared run state, a
RunRegistry (run_registry.py) on its own Redis key. A UX gate only; the
advisory locks in auto_plan.py protect the data, and without Redis
everything here degrades to a logged no-op.
"""

import redis.asyncio

from src.modules.platform.infrastructure.redis_client import get_async_redis_client
from src.modules.platform.infrastructure.run_registry import HEARTBEAT_INTERVAL_S
from src.modules.platform.infrastructure.run_registry import TTL_MS
from src.modules.platform.infrastructure.run_registry import RunHandle
from src.modules.platform.infrastructure.run_registry import RunRegistry
from src.modules.platform.infrastructure.run_registry import RunSnapshot
from src.modules.platform.infrastructure.run_registry import RunState
from src.modules.platform.infrastructure.run_registry import update_snapshot

__all__ = [
    "HEARTBEAT_INTERVAL_S",
    "RUN_KEY",
    "RunHandle",
    "RunSnapshot",
    "RunState",
    "heartbeat_once",
    "read",
    "release",
    "try_acquire",
    "update_snapshot",
]

RUN_KEY = "glados:autoplan:run"

# The key's TTL, which the tests read next to RUN_KEY.
_TTL_MS = TTL_MS


def _client() -> redis.asyncio.Redis:
    # Looked up on every call, so swapping this module's
    # get_async_redis_client also swaps the registry's client.
    return get_async_redis_client()


_registry = RunRegistry(RUN_KEY, "Auto-plan", _client)

try_acquire = _registry.try_acquire
heartbeat_once = _registry.heartbeat_once
release = _registry.release
read = _registry.read
