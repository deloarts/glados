"""
Tells whether any database session committed while a block ran, for the
server-side retry of a request that lost a race (LostRaceRetryMiddleware):
only a request that committed nothing had no effect and may be run again.
A listener on every ORM session marks the tracker of the current context,
so the sessions a request opens report to the tracker its middleware set.
"""

from collections.abc import Callable
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import Session


class _Commits:
    def __init__(self) -> None:
        self.happened = False


_current: ContextVar[_Commits | None] = ContextVar("request_commits", default=None)


@event.listens_for(Session, "after_commit")
def _mark_commit(_session: Any) -> None:
    commits = _current.get()
    if commits is not None:
        commits.happened = True


@contextmanager
def track_commits() -> Iterator[Callable[[], bool]]:
    """Yields a function that answers whether a session committed since the
    block began."""
    commits = _Commits()
    token = _current.set(commits)
    try:
        yield lambda: commits.happened
    finally:
        _current.reset(token)
