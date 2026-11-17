"""
Readiness probe for `GET /ready` (main.py), distinct from liveness
(`/health`, always `{"status": "ok"}`, touches nothing). Docker's own
HEALTHCHECK stays on `/health` so a dead Redis never restarts the backend
(that would drop every SSE client without even fixing Redis); `/ready` is
what an external prober/alert should watch instead, and it is proxied by
nginx and public.

`readiness_report` looks `check_database`/`check_redis` up as bare names,
resolved from this module's globals at call time rather than bound into a
closure or default argument at import time, so a test can
`monkeypatch.setattr(readiness, "check_database", ...)` and have this
function pick up the replacement on the next call.

`check_redis` deliberately does not reuse `get_async_redis_client()`
(src/modules/platform/infrastructure/redis_client.py): that client's timeouts and retry
are sized for application traffic and add up to several seconds against a
hung Redis, longer than the one-second budget a prober expects. The
database check gets the same budget for connecting plus one round trip,
enforced with asyncio.wait_for, so a saturated pool or a stalled server
fails the probe quickly instead of holding it for the pool timeout.

`backup_warnings_report` adds what the backup configuration lacks (see
domain/services/backup_rules.py) without touching the status: a deployment
without backups still serves requests, so the warnings inform an alert but
never turn the probe into a 503. `check_backups` is looked up the same way
as the dependency checks, so tests can replace it.

`background_task_warnings_report` adds one `background_task_stopped:<task>`
warning for each long-running background task that ended in any worker
(infrastructure/background_tasks.py). It does not change the status either:
the requests still get served, while the events, schedules or relay that
task ran wait until the backend is restarted.
"""

import asyncio
from functools import lru_cache

import redis.asyncio
from sqlalchemy import text

from src.modules.platform.adapters.outbound.persistence.repositories.platform_settings_repository import (
    SqlAlchemyPlatformSettingsRepository,
)
from src.modules.platform.adapters.outbound.persistence.session import SessionLocal
from src.modules.platform.domain.services.backup_rules import backup_warnings
from src.modules.platform.infrastructure.background_tasks import stopped_tasks
from src.modules.platform.infrastructure.config.settings import cfg
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.infrastructure.redis_client import PROBE_SOCKET_CONNECT_TIMEOUT_SECONDS
from src.modules.platform.infrastructure.redis_client import PROBE_SOCKET_TIMEOUT_SECONDS
from src.modules.platform.infrastructure.redis_client import new_probe_redis_client

_DATABASE_TIMEOUT_SECONDS = PROBE_SOCKET_CONNECT_TIMEOUT_SECONDS + PROBE_SOCKET_TIMEOUT_SECONDS


@lru_cache(maxsize=1)
def _get_readiness_redis_client() -> redis.asyncio.Redis:
    """The readiness probe's own Redis client, with the one-second socket
    timeouts `get_async_redis_client()` doesn't set (see module docstring).
    Cached so repeated probes (every 10-30s) reuse one connection pool
    rather than opening a fresh TCP connection each time."""
    return new_probe_redis_client()


async def _select_one() -> None:
    async with SessionLocal() as db:
        await db.execute(text("SELECT 1"))


async def check_database() -> None:
    """Raises if the database is unreachable, unhealthy, or too slow to
    answer within the budget above."""
    await asyncio.wait_for(_select_one(), timeout=_DATABASE_TIMEOUT_SECONDS)


async def check_redis() -> None:
    """Raises if Redis is unreachable, unhealthy, or too slow to answer
    within the one-second probe client timeouts."""
    await _get_readiness_redis_client().ping()


async def readiness_report() -> tuple[bool, dict[str, str]]:
    """Runs every dependency check, swallowing exceptions into a
    per-component ok/fail report: one dependency being down must not
    crash the probe itself. A failing component is logged at WARNING with
    its name and the exception (rate-limiting isn't needed; probes run
    every 10-30s, not per-request).
    """
    checks: dict[str, str] = {}
    all_ok = True
    for name, run_check in (("database", check_database), ("redis", check_redis)):
        try:
            await run_check()
            checks[name] = "ok"
        except Exception:
            checks[name] = "fail"
            all_ok = False
            log.warning("Readiness check failed: %s", name, exc_info=True)
    return all_ok, checks


async def _read_backup_warnings() -> list[str]:
    async with SessionLocal() as db:
        settings = await SqlAlchemyPlatformSettingsRepository(db).get_storage()
    warnings = backup_warnings(
        settings, encryption_key_configured=bool(cfg.security.backup_encryption_key)
    )
    return [warning.value for warning in warnings]


async def check_backups() -> list[str]:
    """The backup warnings, read within the database check's budget."""
    return await asyncio.wait_for(_read_backup_warnings(), timeout=_DATABASE_TIMEOUT_SECONDS)


async def backup_warnings_report() -> list[str]:
    """The backup warnings, or none when the settings cannot be read. That
    case needs no warning of its own, because the database check already
    fails the probe."""
    try:
        return await check_backups()
    except Exception:
        log.debug("Readiness: the backup settings could not be read.", exc_info=True)
        return []


async def background_task_warnings_report() -> list[str]:
    """One warning per background task that ended in any worker, or none
    when the metric files cannot be read."""
    try:
        stopped = await asyncio.to_thread(stopped_tasks)
    except Exception:
        log.debug("Readiness: the background task states could not be read.", exc_info=True)
        return []
    return [f"background_task_stopped:{name}" for name in stopped]
