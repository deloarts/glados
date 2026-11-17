"""
StreamedRun, the SSE background run behind the Auto-Plan and storage
migration streams: the frames it posts, the order of its shutdown steps, and
that a failing step never skips the next one or the closing sentinel.
"""

import asyncio
import json
from dataclasses import dataclass
from typing import Any

import pytest
from pydantic import BaseModel

from src.modules.fulfillment.domain.errors import AutoPlanRunInProgressError
from src.modules.platform.adapters.inbound.api import streamed_run as streamed_run_module
from src.modules.platform.adapters.inbound.api.streamed_run import StreamedRun
from src.modules.platform.infrastructure.run_registry import RunHandle


@dataclass
class _Progress:
    current: int
    total: int


class _Response(BaseModel):
    value: int


@dataclass
class _Result:
    value: int


class _FakeSession:
    def __init__(self, log: list[str]) -> None:
        self._log = log

    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, *_: object) -> None:
        self._log.append("session closed")

    async def rollback(self) -> None:
        self._log.append("rollback")


@pytest.fixture
def log(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    entries: list[str] = []
    monkeypatch.setattr(streamed_run_module, "SessionLocal", lambda: _FakeSession(entries))
    return entries


def _handle() -> RunHandle:
    return RunHandle(run_id="r", user_id=1, user_name="u", started_at="now")


def _run(log: list[str], execute: Any, *, fail_release: bool = False) -> StreamedRun[_Progress]:
    async def heartbeat_once(_: RunHandle) -> None:
        log.append("heartbeat")

    async def release(_: RunHandle) -> None:
        log.append("release")
        if fail_release:
            raise RuntimeError("redis down")

    async def on_end() -> None:
        log.append("end signal")

    return StreamedRun(
        label="Test run",
        execute=execute,
        response_model=_Response,
        snapshot=lambda handle, event: log.append(f"snapshot {event.current}/{event.total}"),
        heartbeat_once=heartbeat_once,
        release=release,
        on_end=on_end,
    )


async def _frames(run: StreamedRun[_Progress], handle: RunHandle) -> list[dict[str, str]]:
    tasks: set[asyncio.Task[None]] = set()
    response = await run.start(handle, tasks)
    frames = [frame async for frame in response.body_iterator]
    await asyncio.gather(*tasks)
    return frames  # type: ignore[return-value]


async def test_streamed_run_posts_progress_then_result_and_shuts_down_in_order(
    log: list[str],
) -> None:
    async def execute(db: Any, progress: Any) -> _Result:
        progress(_Progress(current=1, total=2))
        return _Result(value=7)

    frames = await _frames(_run(log, execute), _handle())

    assert frames == [
        {"event": "progress", "data": json.dumps({"current": 1, "total": 2})},
        {"event": "result", "data": '{"value":7}'},
    ]
    assert log == ["snapshot 1/2", "session closed", "release", "end signal"]


async def test_streamed_run_hides_an_unmapped_error_behind_the_generic_detail(
    log: list[str],
) -> None:
    async def execute(db: Any, progress: Any) -> _Result:
        raise RuntimeError("secret internals")

    frames = await _frames(_run(log, execute), _handle())

    assert frames == [{"event": "error", "data": json.dumps({"detail": "Test run failed."})}]
    assert log == ["rollback", "session closed", "release", "end signal"]


async def test_streamed_run_echoes_a_mapped_domain_error(log: list[str]) -> None:
    async def execute(db: Any, progress: Any) -> _Result:
        raise AutoPlanRunInProgressError("Busy.")

    frames = await _frames(_run(log, execute), _handle())

    assert frames == [{"event": "error", "data": json.dumps({"detail": "Busy."})}]


async def test_streamed_run_still_ends_the_stream_when_the_release_fails(log: list[str]) -> None:
    async def execute(db: Any, progress: Any) -> _Result:
        return _Result(value=1)

    frames = await _frames(_run(log, execute, fail_release=True), _handle())

    assert [frame["event"] for frame in frames] == ["result"]
    assert log[-2:] == ["release", "end signal"]
