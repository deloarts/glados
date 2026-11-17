"""
Runs an async job on a fixed interval as a lifespan background task on the
event loop, without a scheduler thread. The first run happens
immediately, so a due time missed while the process was down is caught up
right after boot. Runs never overlap: the next one starts `interval`
seconds after the previous one finished. A failing run is logged and the
loop carries on; only cancellation (lifespan shutdown) ends it.
"""

import asyncio
from collections.abc import Awaitable
from collections.abc import Callable

from src.modules.platform.infrastructure.logging.logger import log


async def run_every(interval_seconds: float, job: Callable[[], Awaitable[None]], name: str) -> None:
    try:
        while True:
            try:
                await job()
            except Exception:
                log.exception("Scheduled job %r failed; next run in %ss.", name, interval_seconds)
            await asyncio.sleep(interval_seconds)
    except asyncio.CancelledError:
        log.info("Scheduled job %r stopped.", name)
        raise
