"""App-wide "one storage migration at a time" mutex plus the shared run state,
a RunRegistry (run_registry.py) on its own Redis key. Two migrations at once
would both copy every file and race to switch the settings, so a second one is
refused while the first holds the key. Without Redis the migration still runs,
only unguarded.
"""

import redis.asyncio

from src.modules.platform.infrastructure.redis_client import get_async_redis_client
from src.modules.platform.infrastructure.run_registry import RunRegistry

RUN_KEY = "glados:storage-migration:run"


def _client() -> redis.asyncio.Redis:
    # Looked up on every call, so swapping this module's
    # get_async_redis_client also swaps the registry's client.
    return get_async_redis_client()


_registry = RunRegistry(RUN_KEY, "Storage migration", _client)

try_acquire = _registry.try_acquire
heartbeat_once = _registry.heartbeat_once
release = _registry.release
read = _registry.read
