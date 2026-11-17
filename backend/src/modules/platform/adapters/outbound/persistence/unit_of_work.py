"""
Thin wrapper around SQLAlchemy AsyncSession for commit/rollback control.

A caller that must commit a use case's work together with something it
writes after the use case returned holds the session's commits
(hold_commits): while the hold lasts, a commit of any unit of work on that
session only flushes, so its constraint checks still run where the use case
expects them, and the caller commits once when the hold ends. The
Idempotency-Key routes use it, so the key's record of what a request wrote
commits with the work itself. An effect that must follow the commit, such
as the schedule recompute's request, waits for that commit
(defer_until_committed) and is dropped when the work rolls back. A
rollback while the hold lasts discards the holder's writes too, so the hold
then refuses to end normally (RollbackWhileHeldError).
"""

from collections.abc import AsyncIterator
from collections.abc import Awaitable
from collections.abc import Callable
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.infrastructure.logging.logger import log

_HELD = "glados_commits_held"
_DEFERRED = "glados_effects_after_commit"
_ROLLED_BACK = "glados_rolled_back_while_held"


class RollbackWhileHeldError(RuntimeError):
    """A unit of work rolled back while its commits were held and the work
    then carried on. The rollback also discarded what the holder wrote
    before the work, such as an Idempotency-Key's claim, so the work must
    not commit."""


@asynccontextmanager
async def hold_commits(session: AsyncSession) -> AsyncIterator[None]:
    """Turns the commits on `session` into flushes until the block ends;
    the caller commits afterwards. Holds nest. A block that rolled the
    session back and still ends normally raises RollbackWhileHeldError, so
    the caller never commits a partial transaction; one that raises keeps
    its own error."""
    session.info[_HELD] = session.info.get(_HELD, 0) + 1
    try:
        yield
    except BaseException:
        session.info.pop(_DEFERRED, None)
        session.info.pop(_ROLLED_BACK, None)
        raise
    finally:
        session.info[_HELD] -= 1
    if session.info.pop(_ROLLED_BACK, False):
        session.info.pop(_DEFERRED, None)
        raise RollbackWhileHeldError(
            "The work rolled back while its commits were held and then carried on."
        )


class SqlAlchemyUnitOfWork:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def defer_until_committed(self, effect: Callable[[], Awaitable[None]]) -> bool:
        if not self._session.info.get(_HELD, 0):
            return False
        self._session.info.setdefault(_DEFERRED, []).append(effect)
        return True

    async def commit(self) -> None:
        if self._session.info.get(_HELD, 0):
            await self._session.flush()
            return
        await self._session.commit()
        await self._run_deferred()

    async def rollback(self) -> None:
        self._session.info.pop(_DEFERRED, None)
        if self._session.info.get(_HELD, 0):
            self._session.info[_ROLLED_BACK] = True
        await self._session.rollback()

    async def _run_deferred(self) -> None:
        """Runs what waited for this commit, each once and in order. The
        work is committed by then, so a failing effect is logged and the
        others still run."""
        effects: list[Callable[[], Awaitable[None]]] = self._session.info.pop(_DEFERRED, [])
        for effect in effects:
            try:
                await effect()
            except Exception:
                log.exception("An effect deferred until the commit failed after it")
