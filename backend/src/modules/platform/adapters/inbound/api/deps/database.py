"""The request's session, unit of work, transactional event bus and public id
resolver, which every module's factories build on."""

from collections.abc import AsyncGenerator
from collections.abc import Callable
from typing import TypeVar

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.outbound.persistence.event_outbox import OutboxEventBus
from src.modules.platform.adapters.outbound.persistence.public_id_lookup import (
    SqlAlchemyPublicIdResolver,
)
from src.modules.platform.adapters.outbound.persistence.session import SessionLocal
from src.modules.platform.adapters.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.repositories.public_id_resolver import IPublicIdResolver
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork

# ── DB session ────────────────────────────────────────────────────────


async def get_db() -> AsyncGenerator[AsyncSession]:
    """Per-request DB session. Every `Depends(get_db, ...)` passes
    `scope="function"` so the session closes as soon as the endpoint returns,
    before the response is sent. With the default request scope FastAPI keeps
    it open until the response has finished streaming, which pins a pooled
    connection for the lifetime of every SSE stream. All sites must use the
    same scope or FastAPI's dependency cache hands out two sessions."""
    async with SessionLocal() as db:
        try:
            yield db
        except Exception:
            await db.rollback()
            raise


_T = TypeVar("_T")


def repo_factory(repo_cls: Callable[[AsyncSession], _T]) -> Callable[[AsyncSession], _T]:
    """A dependency that builds `repo_cls` from the request's session."""

    def factory(db: AsyncSession = Depends(get_db, scope="function")) -> _T:
        return repo_cls(db)

    return factory


# ── Event bus ─────────────────────────────────────────────────────────


def get_transactional_event_bus(db: AsyncSession = Depends(get_db, scope="function")) -> IEventBus:
    """Stages events in the caller's transaction, so a use case publishes
    before it commits its unit of work. Publishing after the commit would
    lose the event, since get_db() never commits."""
    return OutboxEventBus(db)


get_unit_of_work: Callable[[AsyncSession], IUnitOfWork] = repo_factory(SqlAlchemyUnitOfWork)
get_public_id_resolver: Callable[[AsyncSession], IPublicIdResolver] = repo_factory(
    SqlAlchemyPublicIdResolver
)
