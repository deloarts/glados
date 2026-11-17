"""Terminal connections of the live hub: a display receives its own row,
its screen's row and its widget resources, and nothing else."""

import pytest

from src.modules.platform.adapters.inbound.api.live.hub import LiveHub
from src.modules.platform.ports.outbound.live_signal import LiveResource
from src.modules.platform.ports.outbound.live_signal import LiveSignal


def _signal(resource: str, id: int, action: str = "updated") -> LiveSignal:
    return LiveSignal(resource=resource, id=id, action=action, actor_id=None)  # type: ignore[arg-type]


def _drain(connection) -> list[LiveSignal]:  # type: ignore[no-untyped-def]
    received: list[LiveSignal] = []
    while not connection.queue.empty():
        received.extend(connection.queue.get_nowait())
    return received


def test_terminal_connection_receives_its_own_row_and_widget_resources_only() -> None:
    hub = LiveHub()
    connection = hub.connect_terminal(7, approved=True, infoscreen_id=3)
    signals = [
        _signal(LiveResource.TERMINALS, 7),
        _signal(LiveResource.TERMINALS, 8),
        _signal(LiveResource.INFOSCREENS, 3),
        _signal(LiveResource.INFOSCREENS, 4),
        _signal(LiveResource.PRODUCTION_ORDERS, 1),
        _signal(LiveResource.PRODUCTION_LOTS, 1),
        _signal(LiveResource.PRODUCTION_MACHINES, 1),
        _signal(LiveResource.MACHINE_POOLS, 1),
        _signal(LiveResource.ORDERS, 1),
        _signal(LiveResource.USERS, 1),
        _signal(LiveResource.ANNOUNCEMENTS, 1),
        _signal(LiveResource.CALCULATIONS, 1),
        _signal(LiveResource.BOUGHT_ITEM_DEMANDS, 1),
    ]
    hub.broadcast(signals)
    assert _drain(connection) == [
        signals[0],
        signals[2],
        signals[4],
        signals[5],
        signals[6],
        signals[7],
        signals[8],
    ]


def test_terminal_pending_connection_receives_only_its_own_row() -> None:
    hub = LiveHub()
    connection = hub.connect_terminal(7, approved=False, infoscreen_id=3)
    own = _signal(LiveResource.TERMINALS, 7)
    hub.broadcast([own, _signal(LiveResource.INFOSCREENS, 3), _signal(LiveResource.ORDERS, 1)])
    assert _drain(connection) == [own]


def test_terminal_connection_follows_a_changed_scope() -> None:
    hub = LiveHub()
    connection = hub.connect_terminal(7, approved=True, infoscreen_id=3)
    connection.infoscreen_id = 4
    new_screen = _signal(LiveResource.INFOSCREENS, 4)
    hub.broadcast([_signal(LiveResource.INFOSCREENS, 3), new_screen])
    assert _drain(connection) == [new_screen]


def test_terminal_connections_are_capped_per_terminal_and_count_in_the_total() -> None:
    hub = LiveHub()
    hub.connect(1)
    first = hub.connect_terminal(7, approved=True, infoscreen_id=None)
    hub.connect_terminal(7, approved=True, infoscreen_id=None)
    hub.connect_terminal(7, approved=True, infoscreen_id=None)
    assert hub.connection_count == 3
    assert first.queue.get_nowait() is None
    hub.disconnect_terminal(first)
    assert hub.connection_count == 3
    hub.close_all()
    assert hub.connection_count == 0


def test_terminal_web_users_receive_terminal_and_infoscreen_rows() -> None:
    hub = LiveHub()
    user = hub.connect(1)
    signals = [_signal(LiveResource.TERMINALS, 7), _signal(LiveResource.INFOSCREENS, 3)]
    hub.broadcast(signals)
    assert user.queue.get_nowait() == signals


async def test_terminal_stream_rereads_its_scope_when_its_own_row_changes() -> None:
    from src.modules.operations.adapters.inbound.api.v1.web.endpoints.terminal_device import _frames
    from src.modules.operations.application.use_cases.terminal_device.get_live_scope import (
        TerminalLiveScope,
    )

    hub = LiveHub()
    connection = hub.connect_terminal(7, approved=False, infoscreen_id=None)
    scopes = [TerminalLiveScope(approved=True, infoscreen_id=4), None]
    loads: list[int] = []

    async def load_scope(terminal_id: int) -> TerminalLiveScope | None:
        loads.append(terminal_id)
        return scopes.pop(0)

    frames = _frames(hub, connection, load_scope)
    hub.broadcast([_signal(LiveResource.ORDERS, 1), _signal(LiveResource.TERMINALS, 7)])
    first = await anext(frames)
    assert first["event"] == "signal"
    assert connection.approved is True and connection.infoscreen_id == 4

    hub.broadcast([_signal(LiveResource.INFOSCREENS, 4)])
    assert '"infoscreens"' in (await anext(frames))["data"]

    hub.broadcast([_signal(LiveResource.TERMINALS, 7, "deleted")])
    assert (await anext(frames))["event"] == "signal"
    with pytest.raises(StopAsyncIteration):
        await anext(frames)
    assert loads == [7, 7]
    assert hub.connection_count == 0


def test_the_default_schedule_reaches_approved_displays_showing_a_screen() -> None:
    hub = LiveHub()
    showing = hub.connect_terminal(7, approved=True, infoscreen_id=3)
    without_screen = hub.connect_terminal(8, approved=True, infoscreen_id=None)
    pending = hub.connect_terminal(9, approved=False, infoscreen_id=3)
    default = _signal(LiveResource.INFOSCREEN_DEFAULTS, 1)
    hub.broadcast([default])
    assert _drain(showing) == [default]
    assert _drain(without_screen) == []
    assert _drain(pending) == []
