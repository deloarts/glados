"""Transaction boundary protocol for database operations.

Coordinates commit and rollback across repositories in a use case. A write
that violates a database constraint, at commit or at an earlier flush inside
a repository call, raises ConstraintViolationError, so the application layer
can tell a constraint conflict apart from other failures without knowing the
persistence library.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from typing import Protocol
from typing import runtime_checkable


class ConstraintViolationError(Exception):
    """A write broke a unique, primary key, foreign key, check or not-null
    constraint. `constraint` holds the violated constraint's name when the
    database driver reports one, otherwise the driver's message, which on
    SQLite names the table and columns instead."""

    def __init__(self, constraint: str) -> None:
        super().__init__(constraint)
        self.constraint = constraint


@runtime_checkable
class IUnitOfWork(Protocol):
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...


@runtime_checkable
class IDeferringUnitOfWork(IUnitOfWork, Protocol):
    """A unit of work whose commits a caller can hold, so that a use
    case's work commits together with what the caller writes after it.
    While its commits are held, an effect that must follow the commit waits
    for the real one."""

    def defer_until_committed(self, effect: Callable[[], Awaitable[None]]) -> bool:
        """Queues `effect` to run once after the commit that ends the
        hold and returns True; returns False, queuing nothing, when no hold
        is in force, so the caller runs the effect itself. A rollback drops
        what was queued."""
        ...
