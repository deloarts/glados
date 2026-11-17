"""
Process-wide async Redis client, created lazily from cfg.redis and shared
by the adapters and background workers of one process.

It carries socket timeouts, TCP keepalive, a bounded connection pool and a
single short retry on connection errors and timeouts, so a hung or
restarting Redis turns into a fast error rather than a stalled request.
Every option the code relies on is passed explicitly, because redis-py 8
changed its defaults to a 5 second timeout, a pool of 100 and ten retries.
No health_check_interval: the socket timeout already bounds every command,
and in redis-py 5 the health-check ping ran inside connection setup, where
a server that accepts but never answers made it recurse without bound.
The readiness probe and the metrics collector each keep their own client
from `new_probe_redis_client()`, with a stricter one-second budget.
"""

from functools import lru_cache
from typing import Any

import redis
import redis.asyncio
from redis.asyncio.retry import Retry as AsyncRetry
from redis.backoff import ExponentialBackoff
from redis.backoff import NoBackoff

from src.modules.platform.infrastructure.config.settings import RedisSettings
from src.modules.platform.infrastructure.config.settings import cfg

_BACKOFF_BASE_SECONDS = 0.05
_BACKOFF_CAP_SECONDS = 0.5

PROBE_SOCKET_CONNECT_TIMEOUT_SECONDS = 1
PROBE_SOCKET_TIMEOUT_SECONDS = 1


def client_options(settings: RedisSettings) -> dict[str, Any]:
    """Connection options shared by the sync and async clients."""
    return {
        "decode_responses": True,
        "socket_timeout": settings.socket_timeout_seconds,
        "socket_connect_timeout": settings.socket_connect_timeout_seconds,
        "socket_keepalive": True,
        "max_connections": settings.max_connections,
        "retry_on_error": [redis.ConnectionError, redis.TimeoutError],
    }


def _backoff() -> ExponentialBackoff:
    return ExponentialBackoff(cap=_BACKOFF_CAP_SECONDS, base=_BACKOFF_BASE_SECONDS)


@lru_cache(maxsize=1)
def get_async_redis_client() -> redis.asyncio.Redis:
    client: redis.asyncio.Redis = redis.asyncio.Redis.from_url(
        cfg.redis.url,
        retry=AsyncRetry(_backoff(), cfg.redis.retries),
        **client_options(cfg.redis),
    )
    return client


def new_probe_redis_client() -> redis.asyncio.Redis:
    """A fresh client with one-second connect and socket timeouts and no
    retry, so a hung Redis fails a probe or a metrics scrape within a second
    instead of holding it for the application client's longer budget. It is
    not cached here: each caller caches its own instance, so a slow probe and
    a slow scrape never compete for the same connection pool."""
    client: redis.asyncio.Redis = redis.asyncio.Redis.from_url(
        cfg.redis.url,
        socket_connect_timeout=PROBE_SOCKET_CONNECT_TIMEOUT_SECONDS,
        socket_timeout=PROBE_SOCKET_TIMEOUT_SECONDS,
        retry=AsyncRetry(NoBackoff(), 0),
    )
    return client
