"""
Builds a use case through the same dependency factory its web route uses,
outside a FastAPI request. A tool therefore runs exactly the use case, with
exactly the wiring, that the matching button in the web app runs, and never
assembles repositories by hand.

A factory declares what it needs as `Depends(...)` defaults, as FastAPI
reads them. The resolver walks those defaults depth first, hands every
dependency on `get_db` the tool call's session, and builds each dependency
once per call, as FastAPI caches it once per request. Overrides registered
on the app (`app.dependency_overrides`, which only tests use) apply here
too, so a test that swaps a dependency swaps it for the tools as well.

Only the shapes the use-case factories use are supported: plain functions
and coroutine functions whose parameters all have a `Depends` default or a
plain default. A factory that needs anything else, such as a request header
or a generator dependency besides the session, is refused with an error
naming it, so a new factory that cannot be resolved fails in the first test
that calls its tool.
"""

import inspect
from collections.abc import Callable
from collections.abc import Mapping
from typing import Any
from typing import cast

from fastapi import params
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.inbound.api.deps.database import get_db


class UnresolvableDependencyError(RuntimeError):
    """A factory asks for something a tool call cannot provide."""


class DependencyResolver:
    def __init__(
        self,
        db: AsyncSession,
        overrides: Mapping[Callable[..., Any], Callable[..., Any]] | None = None,
    ) -> None:
        self._db = db
        self._overrides = overrides or {}
        self._cache: dict[Callable[..., Any], Any] = {}

    async def build[T](self, factory: Callable[..., T]) -> T:
        """The value `factory` returns with its dependencies resolved."""
        return cast(T, await self._resolve(factory, ()))

    async def _resolve(self, factory: Callable[..., Any], chain: tuple[str, ...]) -> Any:
        target = self._overrides.get(factory, factory)
        if target is get_db:
            return self._db
        if target in self._cache:
            return self._cache[target]

        name = getattr(target, "__qualname__", repr(target))
        if inspect.isgeneratorfunction(target) or inspect.isasyncgenfunction(target):
            raise UnresolvableDependencyError(
                f"{' -> '.join((*chain, name))} is a generator dependency; only the "
                "session may be one."
            )

        kwargs: dict[str, Any] = {}
        for param in inspect.signature(target).parameters.values():
            default = param.default
            if isinstance(default, params.Depends):
                if default.dependency is None:
                    raise UnresolvableDependencyError(
                        f"{' -> '.join((*chain, name))}: parameter {param.name!r} has a "
                        "Depends() without a dependency."
                    )
                kwargs[param.name] = await self._resolve(default.dependency, (*chain, name))
            elif default is inspect.Parameter.empty:
                raise UnresolvableDependencyError(
                    f"{' -> '.join((*chain, name))}: parameter {param.name!r} is neither "
                    "a dependency nor optional."
                )
            elif isinstance(default, params.Param | params.Body):
                raise UnresolvableDependencyError(
                    f"{' -> '.join((*chain, name))}: parameter {param.name!r} reads the "
                    "request, which a tool call does not have."
                )

        value = target(**kwargs)
        if inspect.isawaitable(value):
            value = await value
        self._cache[target] = value
        return value
