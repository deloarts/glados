"""
Machinery shared by the read scenarios: the naming rule that decides which
repository methods are reads, the `Reader` proxy that every read goes
through, and the `Scenarios` registry each test module keeps.
"""

import inspect
from collections.abc import Awaitable
from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.outbound.persistence.session import SessionLocal
from tests.integration.repository_reads._graph import Graph

# A public async method whose name starts with one of these is a read path
# and must be exercised by its repository's scenario.
READ_PREFIXES = (
    # "get" alone too, the lookup by a composite key.
    "get",
    "list_",
    "find_",
    "all_",
    "exists",
    "existing_",
    "count_",
    "counts_",
    "latest",
    "last_",
    "is_",
    "owner_of",
    "search",
    "recent_",
    "minutes_by_",
    "sum_minutes_",
    "next_",
    "max_",
)

# Everything else must match one of these. Writes are out of scope, but
# naming them explicitly means an oddly named read cannot hide among them.
WRITE_PREFIXES = (
    "save",
    "delete",
    "add",
    "append",
    "upsert",
    "create",
    "merge_",
    "mark_",
    "revoke_",
    "reset",
    "record_event",
    "set_",
    "reorder_",
    "reassign",
    "close_",
    "shift_",
    "touch_",
    "finish",
    "start",
    "prune",
    "claim",
    "try_claim",
    "release_",
    "acknowledge",
    "lock_",
    "assert_",
    "remove",
    "clear_",
    "anonymise",
    "purge",
)


def public_async_methods(repo_cls: type) -> set[str]:
    return {
        name
        for name in dir(repo_cls)
        if not name.startswith("_") and inspect.iscoroutinefunction(getattr(repo_cls, name))
    }


def read_methods(repo_cls: type) -> set[str]:
    return {m for m in public_async_methods(repo_cls) if m.startswith(READ_PREFIXES)}


def _is_empty(result: object) -> bool:
    if result is None:
        return True
    if isinstance(result, list | dict):
        return not result
    if isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], list):
        return not result[1]
    return False


class Reader:
    """Proxy over a repository on the reading session. Every call first
    ends the seeding session's transaction, whose SQLite read lock would
    otherwise block a read that writes, such as drawing a number, and
    detaches all instances, so a read cannot borrow a relationship that an
    earlier call happened to load and must load what its mapper needs by
    itself. Each call is recorded for the coverage check. An empty result
    fails the test, since it never reaches the mapper; `maybe_empty` skips
    that check for reads whose answer is legitimately empty for the seeded
    graph."""

    def __init__(
        self,
        repo: object,
        session: AsyncSession,
        seed_session: AsyncSession,
        *,
        check_empty: bool = True,
    ) -> None:
        self._repo = repo
        self._session = session
        self._seed_session = seed_session
        self._check_empty = check_empty
        self.called: set[str] = set()

    @property
    def maybe_empty(self) -> "Reader":
        lenient = Reader(self._repo, self._session, self._seed_session, check_empty=False)
        lenient.called = self.called
        return lenient

    def __getattr__(self, name: str) -> Callable[..., Awaitable[Any]]:
        method = getattr(self._repo, name)

        async def call(*args: Any, **kwargs: Any) -> Any:
            await self._seed_session.commit()
            self._session.expunge_all()
            self.called.add(name)
            result = await method(*args, **kwargs)
            if self._check_empty:
                assert not _is_empty(result), f"{name} returned nothing, so no mapper ran"
            return result

        return call


Scenario = Callable[[Graph, Any], Awaitable[None]]


class Scenarios:
    """One registry per test module, mapping a repository class to the
    scenario that reads through it and to the read methods it deliberately
    skips (method name to reason)."""

    def __init__(self) -> None:
        self.scenarios: dict[type, Scenario] = {}
        self.exempt: dict[type, dict[str, str]] = {}

    def register(
        self, repo_cls: type, *, exempt: dict[str, str] | None = None
    ) -> Callable[[Scenario], Scenario]:
        def add(fn: Scenario) -> Scenario:
            assert repo_cls not in self.scenarios, f"{repo_cls.__name__} registered twice"
            self.scenarios[repo_cls] = fn
            self.exempt[repo_cls] = exempt or {}
            return fn

        return add

    def parametrize[F](self, test: F) -> F:
        """Runs the decorated test once per registered repository."""
        return pytest.mark.parametrize(  # type: ignore[no-any-return]
            "repo_cls", list(self.scenarios), ids=lambda cls: cls.__name__
        )(test)

    async def run(self, repo_cls: type, db: AsyncSession) -> None:
        """Seeds on `db` and reads on a separate session, then checks that
        every read method was called or is exempt with a reason."""
        graph = await Graph.seed(db)
        async with SessionLocal() as read_session:
            reader = Reader(repo_cls(read_session), read_session, db)
            await self.scenarios[repo_cls](graph, reader)

        exempt = self.exempt[repo_cls]
        stale = set(exempt) - read_methods(repo_cls)
        assert not stale, f"exemptions for methods that are not reads: {sorted(stale)}"
        missing = read_methods(repo_cls) - reader.called - set(exempt)
        assert not missing, (
            f"{repo_cls.__name__} read methods not exercised: {sorted(missing)}. "
            "Call them in the scenario or exempt them with a reason."
        )
