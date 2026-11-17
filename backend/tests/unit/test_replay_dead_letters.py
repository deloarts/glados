"""
`admin replay-dead-letters` puts dead-lettered events back on the events
stream with their original fields only, removes them from the dead-letter
stream, oldest first and at most --limit of them.
"""

import argparse

import pytest

from src.bootstrap.cli import admin
from src.modules.platform.infrastructure import redis_client


class _FakeStreams:
    def __init__(self, dead: list[tuple[str, dict[str, str]]]) -> None:
        self.dead = list(dead)
        self.events: list[dict[str, str]] = []
        self.closed = False

    async def xrange(self, stream, min="-", max="+", count=None):
        assert stream == "glados:events:dead"
        return self.dead[:count]

    async def xadd(self, stream, fields):
        assert stream == "glados:events"
        self.events.append(dict(fields))

    async def xdel(self, stream, entry_id):
        self.dead = [e for e in self.dead if e[0] != entry_id]

    async def aclose(self):
        self.closed = True


def _dead(entry_id: str, event_id: str) -> tuple[str, dict[str, str]]:
    return (
        entry_id,
        {
            "type": "ProjectCreated",
            "payload": "{}",
            "event_id": event_id,
            "dead_group": "webhooks",
            "dead_source_id": "1-0",
            "dead_deliveries": "5",
            "dead_at": "2026-10-02T00:00:00+00:00",
        },
    )


@pytest.fixture
def streams(monkeypatch: pytest.MonkeyPatch) -> _FakeStreams:
    fake = _FakeStreams([_dead("1-0", "evt-1"), _dead("2-0", "evt-2"), _dead("3-0", "evt-3")])
    monkeypatch.setattr(redis_client, "get_async_redis_client", lambda: fake)
    return fake


async def test_replays_original_fields_and_removes_them_from_the_dead_letters(streams) -> None:
    assert await admin.replay_dead_letters(argparse.Namespace(limit=100)) == 0

    assert [e["event_id"] for e in streams.events] == ["evt-1", "evt-2", "evt-3"]
    assert all(not k.startswith("dead_") for e in streams.events for k in e)
    assert streams.dead == []
    assert streams.closed


async def test_limit_replays_only_the_oldest(streams) -> None:
    await admin.replay_dead_letters(argparse.Namespace(limit=2))

    assert [e["event_id"] for e in streams.events] == ["evt-1", "evt-2"]
    assert [entry_id for entry_id, _ in streams.dead] == ["3-0"]
