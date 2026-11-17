"""Per-process registry of connected live-sync SSE clients; Redis Pub/Sub
does the cross-process fan-out.

The live connections gauge moves at exactly the points a connection enters
or leaves `_by_user`, eviction included, so it stays in step with
connection_count.

Each connection carries its user's permissions, taken at connect time and
replaced each time the live endpoint checks the session again, and
broadcast drops resources it may not read. The contact topics are the
gated ones, since contacts are personal data. An unknown resource fails
open, since it is more likely a mapping gap than a secret.

Terminals have connections of their own, keyed by terminal id with their
own cap. A terminal connection fails closed: it receives its own terminal
row, the row of the screen it shows, the messages to terminals and the
production resources the widgets read, and nothing else. A pending or revoked terminal receives only
its own row. Its scope is updated when its own row changes (see the device
live endpoint), because an admin can assign another screen at any time.
"""

import asyncio
from collections import defaultdict
from dataclasses import dataclass
from dataclasses import field
from functools import lru_cache

from src.modules.platform.adapters.inbound.api.http_metrics import LIVE_CONNECTIONS
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.live_signal import LiveResource
from src.modules.platform.ports.outbound.live_signal import LiveSignal

_QUEUE_MAXSIZE = 100
_MAX_CONNECTIONS_PER_USER = 5  # per process; effective ceiling is this × worker count
# A display has one page open; the second slot covers a reload whose old
# stream has not closed yet.
_MAX_CONNECTIONS_PER_TERMINAL = 2

# Read permission per live resource, None meaning any authenticated user.
_RESOURCE_READ_PERMISSION: dict[str, str | None] = {
    LiveResource.ORDERS: None,
    LiveResource.BOUGHT_ITEM_DEMANDS: None,
    LiveResource.BOUGHT_ITEMS: None,
    LiveResource.MADE_ITEMS: None,
    LiveResource.SOURCE_ITEMS: None,
    LiveResource.QUOTE_REQUESTS: None,
    # Every signed-in user reads every meeting.
    LiveResource.MEETINGS: None,
    LiveResource.MEETING_CARD_PRESENCE: None,
    LiveResource.MADE_ITEM_DEMANDS: None,
    LiveResource.SOURCE_ITEM_DEMANDS: None,
    LiveResource.PRODUCTION_LOTS: None,
    LiveResource.PRODUCTION_ORDERS: None,
    LiveResource.PRODUCTION_MACHINES: None,
    LiveResource.MACHINE_POOLS: None,
    LiveResource.PRINTERS: None,
    LiveResource.ANNOUNCEMENTS: None,
    LiveResource.AUTO_PLAN_RUN: None,
    # A signal carries only the id; the page refetches through the REST
    # endpoint, which hides other users' personal documents.
    LiveResource.CALCULATIONS: None,
    LiveResource.CHECKLISTS: None,
    LiveResource.SEQUENCES: None,
    # Devices are readable by every user, like their product.
    LiveResource.PRODUCT_DEVICES: None,
    # Both tabs are readable by every user.
    LiveResource.TERMINALS: None,
    LiveResource.INFOSCREENS: None,
    LiveResource.INFOSCREEN_DEFAULTS: None,
    LiveResource.TERMINAL_BROADCASTS: None,
    # Contacts are personal data, and even which contact changed is theirs.
    LiveResource.CONTACTS: Permission.READ_CONTACTS,
    LiveResource.PRODUCT_CONTACTS: Permission.READ_CONTACTS,
    LiveResource.PROJECT_CONTACTS: Permission.READ_CONTACTS,
}

# What an approved terminal follows besides its own row and its screen's
# row: the resources its widgets read and the messages to terminals.
_TERMINAL_WIDGET_RESOURCES: frozenset[str] = frozenset(
    {
        LiveResource.PRODUCTION_ORDERS,
        LiveResource.PRODUCTION_LOTS,
        LiveResource.PRODUCTION_MACHINES,
        LiveResource.MACHINE_POOLS,
        LiveResource.ORDERS,
        # Whether a message reaches the display is decided when it reads its
        # state, so every approved display gets the signal.
        LiveResource.TERMINAL_BROADCASTS,
    }
)


@dataclass
class LiveConnection:
    user_id: int
    permissions: frozenset[str] = frozenset()
    is_systemuser: bool = False
    queue: "asyncio.Queue[list[LiveSignal] | None]" = field(
        default_factory=lambda: asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
    )
    overflowed: bool = False

    def may_receive(self, resource: str) -> bool:
        """System users and write:settings holders receive everything;
        others need the resource's permission, if any."""
        if self.is_systemuser or Permission.WRITE_SETTINGS in self.permissions:
            return True
        required = _RESOURCE_READ_PERMISSION.get(resource)
        return required is None or required in self.permissions


@dataclass
class TerminalLiveConnection:
    terminal_id: int
    approved: bool = False
    infoscreen_id: int | None = None
    queue: "asyncio.Queue[list[LiveSignal] | None]" = field(
        default_factory=lambda: asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
    )
    overflowed: bool = False

    def may_receive(self, signal: LiveSignal) -> bool:
        """Its own row, and once approved its screen's row, the default
        display schedule and the widget resources. A bulk signal of a topic carries no id, so it counts."""
        bulk = signal.action == "bulk"
        if signal.resource == LiveResource.TERMINALS:
            return bulk or signal.id == self.terminal_id
        if not self.approved:
            return False
        if signal.resource == LiveResource.INFOSCREENS:
            return self.infoscreen_id is not None and (bulk or signal.id == self.infoscreen_id)
        if signal.resource == LiveResource.INFOSCREEN_DEFAULTS:
            # Only a display showing a screen can follow the default schedule.
            return self.infoscreen_id is not None
        return signal.resource in _TERMINAL_WIDGET_RESOURCES


def _put_nowait(
    connection: LiveConnection | TerminalLiveConnection, item: list[LiveSignal] | None
) -> None:
    try:
        connection.queue.put_nowait(item)
    except asyncio.QueueFull:
        # The SSE generator sends one "resync" frame instead of dropping
        # silently or disconnecting a slow client.
        connection.overflowed = True
        if isinstance(connection, TerminalLiveConnection):
            log.warning(
                "Live hub: queue full for terminal #%s; flagged for resync.",
                connection.terminal_id,
            )
        else:
            log.warning(
                "Live hub: queue full for user #%s; flagged for resync.", connection.user_id
            )


class LiveHub:
    def __init__(self) -> None:
        self._by_user: dict[int, list[LiveConnection]] = defaultdict(list)
        self._by_terminal: dict[int, list[TerminalLiveConnection]] = defaultdict(list)

    def connect(
        self,
        user_id: int,
        *,
        permissions: frozenset[str] = frozenset(),
        is_systemuser: bool = False,
    ) -> LiveConnection:
        connection = LiveConnection(
            user_id=user_id, permissions=permissions, is_systemuser=is_systemuser
        )
        connections = self._by_user[user_id]
        if len(connections) >= _MAX_CONNECTIONS_PER_USER:
            # Evict the oldest, so a forgotten tab loses updates rather than
            # the new one. A resource guard, not a security control.
            #
            # Asymmetry: this removes `oldest` from
            # `connections` directly instead of going through disconnect()
            # below. `oldest`'s own SSE generator does eventually call
            # disconnect(oldest) once it drains the poison pill queued by
            # _put_nowait(), but by then `oldest` is already gone from
            # the list, so disconnect()'s "connection in connections"
            # check is False and its dec() never runs. Decrementing here,
            # at the actual removal, is what keeps the gauge from leaking
            # +1 per eviction; connection_count itself was never wrong
            # (pop(0) already updated the list synchronously), only a
            # side effect keyed off "went through disconnect()" would
            # have been.
            oldest = connections.pop(0)
            _put_nowait(oldest, None)
            LIVE_CONNECTIONS.dec()
        connections.append(connection)
        LIVE_CONNECTIONS.inc()
        return connection

    def disconnect(self, connection: LiveConnection) -> None:
        connections = self._by_user.get(connection.user_id)
        if not connections:
            return
        if connection in connections:
            connections.remove(connection)
            LIVE_CONNECTIONS.dec()
        if not connections:
            self._by_user.pop(connection.user_id, None)

    def connect_terminal(
        self, terminal_id: int, *, approved: bool, infoscreen_id: int | None
    ) -> TerminalLiveConnection:
        """Registers a terminal's stream, evicting its oldest one past the
        cap like connect() does for a user."""
        connection = TerminalLiveConnection(
            terminal_id=terminal_id, approved=approved, infoscreen_id=infoscreen_id
        )
        connections = self._by_terminal[terminal_id]
        if len(connections) >= _MAX_CONNECTIONS_PER_TERMINAL:
            oldest = connections.pop(0)
            _put_nowait(oldest, None)
            LIVE_CONNECTIONS.dec()
        connections.append(connection)
        LIVE_CONNECTIONS.inc()
        return connection

    def disconnect_terminal(self, connection: TerminalLiveConnection) -> None:
        connections = self._by_terminal.get(connection.terminal_id)
        if not connections:
            return
        if connection in connections:
            connections.remove(connection)
            LIVE_CONNECTIONS.dec()
        if not connections:
            self._by_terminal.pop(connection.terminal_id, None)

    def broadcast(self, signals: list[LiveSignal]) -> None:
        if not signals:
            return
        for connections in self._by_user.values():
            for connection in connections:
                allowed = [s for s in signals if connection.may_receive(s.resource)]
                if allowed:
                    _put_nowait(connection, allowed)
        for terminal_connections in self._by_terminal.values():
            for terminal_connection in terminal_connections:
                delivered = [s for s in signals if terminal_connection.may_receive(s)]
                if delivered:
                    _put_nowait(terminal_connection, delivered)

    def close_all(self) -> None:
        for connections in self._by_user.values():
            for connection in connections:
                _put_nowait(connection, None)
                LIVE_CONNECTIONS.dec()
        self._by_user.clear()
        for terminal_connections in self._by_terminal.values():
            for terminal_connection in terminal_connections:
                _put_nowait(terminal_connection, None)
                LIVE_CONNECTIONS.dec()
        self._by_terminal.clear()

    @property
    def connection_count(self) -> int:
        return sum(len(connections) for connections in self._by_user.values()) + sum(
            len(connections) for connections in self._by_terminal.values()
        )


@lru_cache(maxsize=1)
def get_live_hub() -> LiveHub:
    return LiveHub()
