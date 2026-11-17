"""
`admin republish-outbox` puts relayed outbox rows on the events stream once
more, with their original event ids, in id order, bounded by the time the
relay published them and optionally by event type. A dry run only counts.
The rows live in a real in-memory SQLite database; Redis is a fake.
"""

import argparse
import importlib
from collections import Counter
from datetime import UTC
from datetime import datetime
from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from src.bootstrap.cli import admin
from src.bootstrap.cli.republish_outbox import republish
from src.modules.platform.adapters.outbound.persistence import session as session_module
from src.modules.platform.adapters.outbound.persistence.alembic_imports import model_module_names
from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.adapters.outbound.persistence.models.event_outbox_model import (
    EventOutboxOrmModel,
)
from src.modules.platform.infrastructure import redis_client

_START = datetime(2026, 11, 4, 6, 0, tzinfo=UTC)

# The mappers resolve every relationship on first use, so every model must be
# imported, not only the outbox table this file creates.
for _module_name in model_module_names():
    importlib.import_module(_module_name)


class _FakeStream:
    def __init__(self) -> None:
        self.added: list[dict[str, str]] = []
        self.closed = False

    async def xadd(self, stream, fields):
        assert stream == "glados:events"
        self.added.append(dict(fields))
        return f"{len(self.added)}-0"

    async def aclose(self):
        self.closed = True


@pytest.fixture
async def outbox(monkeypatch: pytest.MonkeyPatch):
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[EventOutboxOrmModel.__table__])
    factory = async_sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    rows = [
        ("evt-before", "ProjectCreated", _START - timedelta(minutes=1)),
        ("evt-1", "ProjectCreated", _START),
        ("evt-2", "OrderCanceled", _START + timedelta(minutes=5)),
        ("evt-3", "ProjectCreated", _START + timedelta(minutes=10)),
        ("evt-unpublished", "ProjectCreated", None),
    ]
    async with factory() as db:
        for event_id, event_type, published_at in rows:
            db.add(
                EventOutboxOrmModel(
                    event_id=event_id,
                    event_type=event_type,
                    payload="{}",
                    created=_START - timedelta(hours=1),
                    published_at=published_at,
                )
            )
        await db.commit()
    monkeypatch.setattr(session_module, "SessionLocal", factory)
    try:
        yield
    finally:
        await engine.dispose()


@pytest.fixture
def stream(monkeypatch: pytest.MonkeyPatch) -> _FakeStream:
    fake = _FakeStream()
    monkeypatch.setattr(redis_client, "get_async_redis_client", lambda: fake)
    return fake


def _args(**overrides) -> argparse.Namespace:
    values = {"since": _START, "until": None, "event_types": None, "dry_run": False}
    values.update(overrides)
    return argparse.Namespace(**values)


async def test_republishes_the_rows_published_since_with_their_event_ids(outbox, stream) -> None:
    assert await admin.republish_outbox(_args()) == 0

    assert [m["event_id"] for m in stream.added] == ["evt-1", "evt-2", "evt-3"]
    assert stream.added[1]["type"] == "OrderCanceled"
    assert stream.added[1]["payload"] == "{}"
    assert stream.closed


async def test_until_and_type_narrow_the_rows(outbox, stream) -> None:
    await admin.republish_outbox(
        _args(until=_START + timedelta(minutes=10), event_types=["ProjectCreated"])
    )

    assert [m["event_id"] for m in stream.added] == ["evt-1"]


async def test_a_dry_run_counts_per_type_and_publishes_nothing(outbox, stream, capsys) -> None:
    assert await admin.republish_outbox(_args(dry_run=True)) == 0

    assert stream.added == []
    output = capsys.readouterr().out
    assert "OrderCanceled: 1" in output
    assert "ProjectCreated: 2" in output
    assert "Would republish 3 event(s)." in output


async def test_rows_are_read_in_batches_without_skipping_any(outbox) -> None:
    published: list[str] = []
    counts: Counter[str] = Counter()

    async def publish(message) -> None:
        published.append(message.event_id)

    await republish(
        session_factory=session_module.SessionLocal,
        publish=publish,
        since=_START,
        until=None,
        event_types=[],
        counts=counts,
        batch_size=1,
    )

    assert published == ["evt-1", "evt-2", "evt-3"]
    assert counts == Counter({"ProjectCreated": 2, "OrderCanceled": 1})


async def test_an_unknown_event_type_is_refused(outbox, stream) -> None:
    assert await admin.republish_outbox(_args(event_types=["NoSuchEvent"])) == 2
    assert stream.added == []


async def test_an_empty_time_range_is_refused(outbox, stream) -> None:
    assert await admin.republish_outbox(_args(until=_START)) == 2


def test_a_time_without_a_utc_offset_is_refused() -> None:
    assert admin._aware_datetime("2026-11-04T06:00Z") == _START
    with pytest.raises(argparse.ArgumentTypeError, match="no UTC offset"):
        admin._aware_datetime("2026-11-04T06:00")
