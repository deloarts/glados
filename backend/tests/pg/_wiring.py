"""
Builds a use case the way a request does, from its FastAPI factory in a
module's adapters/inbound/api/deps package, on a session the race test
chooses. The factories are plain functions whose parameters default to
Depends(...), so resolving them is calling them with their dependencies
resolved first. One
resolution is one request: every dependency is built once and shared, as
FastAPI caches it per request, so the use case and its lifecycle reconciler
take their row locks through one lock plan. `overrides` replaces a
dependency by a value, as app.dependency_overrides does: the schedule
recompute's Redis counter becomes an in-memory one, so the race tests need
Postgres only.
"""

import inspect
from collections.abc import Callable
from collections.abc import Mapping
from typing import Any

from fastapi import params
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.inbound.api.deps.database import get_db


async def build[T](
    factory: Callable[..., T],
    db: AsyncSession,
    overrides: Mapping[Callable[..., Any], Any] | None = None,
) -> T:
    """The object `factory` returns for one request on `db`."""
    cache: dict[Callable[..., Any], Any] = {get_db: db, **(overrides or {})}

    async def solve(dependency: Callable[..., Any]) -> Any:
        if dependency in cache:
            return cache[dependency]
        arguments: dict[str, Any] = {}
        for name, parameter in inspect.signature(dependency).parameters.items():
            if isinstance(parameter.default, params.Depends):
                arguments[name] = await solve(parameter.default.dependency)
            elif parameter.default is inspect.Parameter.empty:
                raise TypeError(
                    f"{dependency.__name__} needs {name!r}, which no dependency provides."
                )
        value = dependency(**arguments)
        if inspect.isawaitable(value):
            value = await value
        cache[dependency] = value
        return value

    return await solve(factory)
