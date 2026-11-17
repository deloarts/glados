"""
Ack-aware trimming of the events stream: entries are trimmed only below the
oldest one any consumer group still needs, and the hard cap applies on top.
"""

import pytest

from src.modules.platform.infrastructure.events import stream_trimmer
from src.modules.platform.infrastructure.events.stream_trimmer import trim_events_stream

STREAM = "glados:events"


class FakeStreamRedis:
    """A stream with entries 1-0 .. n-0 and consumer groups described by
    their last delivered id and pending ids."""

    def __init__(self, entries: int, groups: dict[str, tuple[str, list[str]]]) -> None:
        self.ids = [f"{n}-0" for n in range(1, entries + 1)]
        self.groups = groups

    @staticmethod
    def _key(stream_id: str) -> tuple[int, int]:
        ms, _, seq = stream_id.partition("-")
        return int(ms), int(seq)

    async def exists(self, key):
        return 1 if self.ids or self.groups else 0

    async def xinfo_groups(self, stream):
        return [
            {"name": name, "last-delivered-id": last, "pending": len(pending)}
            for name, (last, pending) in self.groups.items()
        ]

    async def xpending(self, stream, group):
        pending = sorted(self.groups[group][1], key=self._key)
        return {
            "pending": len(pending),
            "min": pending[0] if pending else None,
            "max": pending[-1] if pending else None,
            "consumers": [],
        }

    async def xtrim(self, stream, maxlen=None, approximate=True, minid=None):
        before = len(self.ids)
        if minid is not None:
            self.ids = [i for i in self.ids if self._key(i) >= self._key(minid)]
        if maxlen is not None:
            self.ids = self.ids[-maxlen:]
        return before - len(self.ids)

    async def xlen(self, stream):
        return len(self.ids)


async def test_trims_below_the_oldest_pending_message_of_any_group() -> None:
    client = FakeStreamRedis(
        10,
        {
            "notifications": ("10-0", []),
            "webhooks": ("10-0", ["4-0", "7-0"]),
        },
    )

    assert await trim_events_stream(client) == 3  # type: ignore[arg-type]
    assert client.ids[0] == "4-0"


async def test_without_pending_messages_trims_up_to_the_slowest_groups_last_delivery() -> None:
    client = FakeStreamRedis(10, {"notifications": ("9-0", []), "auto_print": ("6-0", [])})

    await trim_events_stream(client)  # type: ignore[arg-type]

    assert client.ids[0] == "6-0"


async def test_a_group_that_never_read_keeps_everything() -> None:
    client = FakeStreamRedis(10, {"notifications": ("10-0", []), "pdm_sync": ("0-0", [])})

    assert await trim_events_stream(client) == 0  # type: ignore[arg-type]
    assert len(client.ids) == 10


async def test_without_consumer_groups_nothing_is_trimmed() -> None:
    client = FakeStreamRedis(10, {})

    assert await trim_events_stream(client) == 0  # type: ignore[arg-type]


async def test_hard_cap_drops_unprocessed_entries_and_logs_an_error(
    monkeypatch: pytest.MonkeyPatch, glados_caplog
) -> None:
    monkeypatch.setattr(stream_trimmer, "HARD_CAP", 5)
    client = FakeStreamRedis(10, {"stale": ("0-0", [])})

    assert await trim_events_stream(client) == 5  # type: ignore[arg-type]
    assert client.ids == ["6-0", "7-0", "8-0", "9-0", "10-0"]
    assert any(
        r.levelname == "ERROR" and "hard cap" in r.getMessage() for r in glados_caplog.records
    )
