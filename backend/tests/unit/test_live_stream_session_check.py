"""
An open live stream checks its session again while it runs: it ends once
the session is no longer valid and takes over the user's current
permissions while it is.
"""

import asyncio

from src.modules.platform.adapters.inbound.api.live.hub import LiveHub
from src.modules.platform.adapters.inbound.api.v1.web.endpoints.live import _frames
from src.modules.platform.ports.outbound.live_signal import LiveSignal

_SIGNAL = LiveSignal(resource="orders", id=7, action="updated", actor_id=None)


class _Checks:
    """Answers the queued results in turn and counts the calls."""

    def __init__(self, *answers: frozenset[str] | None) -> None:
        self._answers = list(answers)
        self.calls = 0
        self.checked = asyncio.Event()

    async def __call__(self) -> frozenset[str] | None:
        self.calls += 1
        self.checked.set()
        return self._answers.pop(0) if self._answers else frozenset()


async def test_the_stream_ends_once_the_session_is_no_longer_valid() -> None:
    hub = LiveHub()
    connection = hub.connect(1, permissions=frozenset({"read:orders"}))
    checks = _Checks(None)

    frames = [frame async for frame in _frames(hub, connection, checks, check_every=0.01)]

    assert frames == []
    assert checks.calls == 1
    assert hub.connection_count == 0


async def test_signals_flow_until_the_check_fails() -> None:
    hub = LiveHub()
    connection = hub.connect(1)
    connection.queue.put_nowait([_SIGNAL])
    checks = _Checks(frozenset(), None)

    frames = [frame async for frame in _frames(hub, connection, checks, check_every=0.05)]

    assert [frame["event"] for frame in frames] == ["signal"]
    assert checks.calls == 2


async def test_a_check_takes_over_the_current_permissions() -> None:
    hub = LiveHub()
    connection = hub.connect(1, permissions=frozenset({"read:orders", "write:orders"}))
    checks = _Checks(frozenset({"read:orders"}), None)
    stream = _frames(hub, connection, checks, check_every=0.01)

    task = asyncio.ensure_future(anext(stream, None))
    await checks.checked.wait()
    # The check has answered; one more turn of the event loop lets the
    # stream apply the answer.
    await asyncio.sleep(0)

    assert connection.permissions == frozenset({"read:orders"})
    await task
