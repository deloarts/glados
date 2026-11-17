"""
The tools a race test interleaves two requests with. Each request runs in
its own asyncio task on its own engine and session, and names its side in
a context variable that the task inherits. A Gate stops the request of one
side inside a repository method, after the locks it wants to hold, until
the test lets it go; meanwhile the other request starts, and wait_for_lock
proves from pg_stat_activity that it is blocked on a lock and not merely
slow. Everything a test asserts afterwards is read back on a fresh session.
"""

import asyncio
import contextvars
import functools
from collections.abc import Awaitable
from collections.abc import Callable
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.modules.platform.adapters.inbound.api.deps.bindings import (
    get_schedule_recompute_generation_counter,
)
from tests.pg._wiring import build

SIDE: contextvars.ContextVar[str | None] = contextvars.ContextVar("race_side", default=None)

# Long enough for a loaded CI runner, short enough that a request that
# never blocks fails the test quickly.
WAIT_SECONDS = 15.0


class LocalGenerationCounter:
    """The schedule recompute's generation counter in memory, standing in
    for the Redis one, so the race tests need Postgres only."""

    def __init__(self) -> None:
        self._generation = 0
        self._processed = 0
        self._stale_since: datetime | None = None

    async def increment_generation(self) -> int:
        self._generation += 1
        return self._generation

    async def current_generation(self) -> int:
        return self._generation

    async def processed_generation(self) -> int:
        return self._processed

    async def mark_processed(self, generation: int) -> None:
        self._processed = max(self._processed, generation)

    async def mark_stale(self, at: datetime) -> None:
        if self._stale_since is None:
            self._stale_since = at

    async def take_stale_since(self) -> datetime | None:
        taken, self._stale_since = self._stale_since, None
        return taken

    async def stale_since(self) -> datetime | None:
        return self._stale_since


def sessions(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Sessions configured as the application's SessionLocal is."""
    return async_sessionmaker(engine, autoflush=False, expire_on_commit=False)


async def request[U, R](
    side: str,
    engine: AsyncEngine,
    factory: Callable[..., U],
    call: Callable[[U], Awaitable[R]],
) -> R:
    """Runs `call` on the use case `factory` builds, as one request of
    `side` on its own session. The use case commits what it does; a failed
    request leaves nothing behind."""
    SIDE.set(side)
    async with sessions(engine)() as db:
        use_case = await build(
            factory,
            db,
            {get_schedule_recompute_generation_counter: LocalGenerationCounter()},
        )
        try:
            return await call(use_case)
        except BaseException:
            await db.rollback()
            raise


def start[R](coroutine: Awaitable[R]) -> "asyncio.Task[R]":
    return asyncio.ensure_future(coroutine)


class Gate:
    """Stops the first call of `side` to a wrapped method, before or after
    the call itself, until release() is called."""

    def __init__(self, side: str) -> None:
        self.side = side
        self.reached = asyncio.Event()
        self._released = asyncio.Event()

    def wrap(self, method: Callable[..., Awaitable[Any]], *, after: bool = False) -> Any:
        @functools.wraps(method)
        async def gated(*args: Any, **kwargs: Any) -> Any:
            stop = SIDE.get() == self.side and not self.reached.is_set()
            if stop and not after:
                await self._stop()
            result = await method(*args, **kwargs)
            if stop and after:
                await self._stop()
            return result

        return gated

    async def _stop(self) -> None:
        self.reached.set()
        await self._released.wait()

    async def wait_reached(self) -> None:
        await asyncio.wait_for(self.reached.wait(), WAIT_SECONDS)

    def release(self) -> None:
        self._released.set()


async def wait_for_lock(watcher: AsyncEngine, application_name: str) -> None:
    """Returns once a connection of `application_name` waits for a lock,
    a row lock or an advisory lock; fails the test when none does."""
    deadline = asyncio.get_running_loop().time() + WAIT_SECONDS
    while True:
        async with watcher.connect() as connection:
            waiting = await connection.scalar(
                text(
                    "SELECT count(*) FROM pg_stat_activity "
                    "WHERE application_name = :name AND wait_event_type = 'Lock'"
                ),
                {"name": application_name},
            )
        if waiting:
            return
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError(f"{application_name} never waited for a lock.")
        await asyncio.sleep(0.05)


async def outcomes(*tasks: "asyncio.Task[Any]") -> list[Any]:
    """The result or the exception of every task, once all have ended."""
    return list(
        await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), WAIT_SECONDS * 2)
    )
