"""
Live row-sync SSE endpoint. Streams row-change signals
(src/modules/platform/ports/outbound/live_signal.py) to authenticated clients so tables can
refetch only the rows that changed instead of polling or reloading. Prefix
`/live`, see src/modules/platform/adapters/inbound/api/live/hub.py for the per-process
connection registry this endpoint reads from.
"""

import asyncio
import json
import time
from collections.abc import AsyncIterator
from dataclasses import asdict

from fastapi import Depends
from fastapi.routing import APIRouter
from sse_starlette.sse import EventSourceResponse

from src.modules.platform.adapters.inbound.api.auth_deps import LiveSessionCheck
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.auth_deps import get_live_session_check
from src.modules.platform.adapters.inbound.api.live.hub import LiveConnection
from src.modules.platform.adapters.inbound.api.live.hub import LiveHub
from src.modules.platform.adapters.inbound.api.live.hub import get_live_hub
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log

router = APIRouter()

_PING_SECONDS = 15
_SEND_TIMEOUT_SECONDS = 10.0
# How often an open stream checks its session again. A logout, a revoked
# session, a deactivation or a permission change reaches the stream within
# this time instead of when the connection happens to drop.
_SESSION_CHECK_SECONDS = 60.0


@router.get("/")
async def live_stream(
    user: User = Depends(get_current_active_user),
    hub: LiveHub = Depends(get_live_hub),
    check_session: LiveSessionCheck = Depends(get_live_session_check),
) -> EventSourceResponse:
    # The DB session opened to resolve `user` above is closed by the time
    # the stream starts because get_db is declared with scope="function"
    # (see get_db in deps/database.py). Without that, every open tab would hold one of
    # this worker's pooled connections for the whole stream.
    connection = hub.connect(
        user_id=user.id,
        permissions=frozenset(user.effective_permissions),
        is_systemuser=user.is_systemuser,
    )
    return EventSourceResponse(
        _frames(hub, connection, check_session),
        ping=_PING_SECONDS,
        send_timeout=_SEND_TIMEOUT_SECONDS,
        sep="\n",  # pin LF, sse-starlette defaults to CRLF
    )


async def _frames(
    hub: LiveHub,
    connection: LiveConnection,
    check_session: LiveSessionCheck,
    check_every: float = _SESSION_CHECK_SECONDS,
) -> AsyncIterator[dict[str, str]]:
    """Streams the connection's signals and ends the stream once its session
    is no longer valid. Each check also takes over the user's current
    permissions, so a right that was taken away stops its signals."""
    next_check = time.monotonic() + check_every
    try:
        while True:
            try:
                signals = await asyncio.wait_for(
                    connection.queue.get(), timeout=max(0.0, next_check - time.monotonic())
                )
            except TimeoutError:
                signals = []
            if time.monotonic() >= next_check:
                permissions = await check_session()
                if permissions is None:
                    log.info(
                        "Live stream of user #%s ended: its session is no longer valid.",
                        connection.user_id,
                    )
                    return
                connection.permissions = permissions
                next_check = time.monotonic() + check_every
            if signals is None:  # evicted by the hub, or the process is shutting down
                return
            if not signals:
                continue
            if connection.overflowed:
                connection.overflowed = False
                _drain(connection)
                yield {"event": "resync", "data": "{}"}
                continue
            yield {"event": "signal", "data": json.dumps([asdict(s) for s in signals])}
    finally:
        hub.disconnect(connection)


def _drain(connection: LiveConnection) -> None:
    while not connection.queue.empty():
        connection.queue.get_nowait()
