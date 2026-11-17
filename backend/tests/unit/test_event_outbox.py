"""
Unit tests for the producer side of the transactional outbox: OutboxEventBus
and the atomicity claim it rests on.

The last test uses a real in-memory SQLite session rather than a fake, because
"staged before commit is visible after commit and gone after rollback" is a
claim about SQLAlchemy's transaction semantics, and asserting it against a fake
session would only test the fake.
"""

import logging

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from src.modules.platform.adapters.outbound.persistence.event_outbox import OutboxEventBus
from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.adapters.outbound.persistence.models.event_outbox_model import (
    EventOutboxOrmModel,
)
from src.modules.workspace.domain.events.project_events import ProjectCreated

EVENT = ProjectCreated(project_id=1, project_number="P-1", actor_id=7, designated_user_id=4)


class FakeSession:
    """Minimal Session stand-in: records adds, commits and rollbacks."""

    def __init__(self, add_error: Exception | None = None) -> None:
        self.new: list[object] = []
        self.commits = 0
        self.rollbacks = 0
        self._add_error = add_error

    def add(self, instance: object) -> None:
        if self._add_error is not None:
            raise self._add_error
        self.new.append(instance)

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


async def test_publish_stages_a_row_without_committing():
    session = FakeSession()

    await OutboxEventBus(session).publish(EVENT)  # type: ignore[arg-type]

    (row,) = session.new
    assert isinstance(row, EventOutboxOrmModel)
    assert session.commits == 0  # the caller's uow.commit() carries it


async def test_staged_row_carries_the_serialized_event_and_a_unique_event_id():
    session = FakeSession()
    bus = OutboxEventBus(session)  # type: ignore[arg-type]

    await bus.publish(EVENT)
    await bus.publish(EVENT)

    first, second = session.new
    assert first.event_type == second.event_type == "ProjectCreated"
    assert first.payload == second.payload
    assert '"project_id": 1' in first.payload
    assert first.event_id != second.event_id  # producer-assigned identity, per publish


async def test_publish_never_raises_when_staging_fails(glados_caplog):
    """IEventBus's contract: implementations must not raise. A broken outbox
    must not fail the request that is trying to use it."""
    session = FakeSession(add_error=RuntimeError("session is wedged"))

    await OutboxEventBus(session).publish(EVENT)  # type: ignore[arg-type]

    assert session.rollbacks == 0  # the caller owns the transaction, never the bus
    assert [r for r in glados_caplog.records if r.levelno == logging.ERROR]


async def test_publish_of_an_unregistered_event_is_logged_and_dropped(glados_caplog):
    """EventCodecError is raised at STAGE time (serialize runs inside
    publish), so an unserializable event can never reach the table and can
    never become a row the relay retries forever."""
    session = FakeSession()

    await OutboxEventBus(session).publish(object())  # type: ignore[arg-type]

    assert session.new == []
    assert [r for r in glados_caplog.records if r.levelno == logging.ERROR]


@pytest.fixture
async def sqlite_session_factory():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[EventOutboxOrmModel.__table__])
    try:
        yield async_sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    finally:
        await engine.dispose()


async def test_events_staged_before_commit_are_visible_after_commit_and_gone_after_rollback(
    sqlite_session_factory,
):
    async with sqlite_session_factory() as db:
        await OutboxEventBus(db).publish(EVENT)
        await db.commit()

    async with sqlite_session_factory() as db:
        await OutboxEventBus(db).publish(EVENT)
        await db.rollback()

    async with sqlite_session_factory() as db:
        rows = (await db.execute(select(EventOutboxOrmModel))).scalars().all()

    assert len(rows) == 1  # committed one, rolled the other back with its write
    assert rows[0].event_type == "ProjectCreated"
    assert rows[0].published_at is None  # not relayed yet
    assert rows[0].attempts == 0
