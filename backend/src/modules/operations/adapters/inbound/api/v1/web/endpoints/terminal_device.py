"""
Endpoints the displays call. Prefix `/terminal-device`.

`/challenge` and `/session` need no session: the device proves it holds its
private key by signing the challenge, and an unknown device also sends a
terminal key in `X-Api-Key`. Both are rate-limited per client address.
The thumbnails and drawings a feed links to need no header either: each
link carries a signed token naming one item picture or one drawing file. Everything else authenticates with
the terminal access token from
`/session` (`Authorization: Bearer`), through get_current_terminal, which
reloads the terminal on every request.

The live stream sends the same frames as the web live stream, filtered to
the terminal's own row, its screen's row and the resources its widgets read.
"""

import json
from collections.abc import AsyncIterator
from dataclasses import asdict

from fastapi import Depends
from fastapi import Header
from fastapi import Request
from fastapi import Response
from fastapi.routing import APIRouter
from sse_starlette.sse import EventSourceResponse

from src.modules.operations.adapters.inbound.api.deps.terminals import TerminalLiveScopeLoader
from src.modules.operations.adapters.inbound.api.deps.terminals import (
    get_issue_terminal_challenge_use_case,
)
from src.modules.operations.adapters.inbound.api.deps.terminals import (
    get_serve_infoscreen_drawing_use_case,
)
from src.modules.operations.adapters.inbound.api.deps.terminals import (
    get_serve_infoscreen_thumbnail_use_case,
)
from src.modules.operations.adapters.inbound.api.deps.terminals import (
    get_start_terminal_session_use_case,
)
from src.modules.operations.adapters.inbound.api.deps.terminals import (
    get_terminal_device_state_use_case,
)
from src.modules.operations.adapters.inbound.api.deps.terminals import get_terminal_feed_use_case
from src.modules.operations.adapters.inbound.api.deps.terminals import (
    get_terminal_live_scope_loader,
)
from src.modules.operations.adapters.inbound.api.schemas.infoscreen_schema import (
    InfoscreenFeedResponse,
)
from src.modules.operations.adapters.inbound.api.schemas.terminal_schema import (
    TerminalChallengeRequest,
)
from src.modules.operations.adapters.inbound.api.schemas.terminal_schema import (
    TerminalChallengeResponse,
)
from src.modules.operations.adapters.inbound.api.schemas.terminal_schema import (
    TerminalDeviceStateResponse,
)
from src.modules.operations.adapters.inbound.api.schemas.terminal_schema import (
    TerminalSessionRequest,
)
from src.modules.operations.adapters.inbound.api.schemas.terminal_schema import (
    TerminalSessionResponse,
)
from src.modules.operations.adapters.inbound.api.terminal_auth_deps import client_ip
from src.modules.operations.adapters.inbound.api.terminal_auth_deps import get_current_terminal
from src.modules.operations.application.dto.infoscreen_feed_dto import InfoscreenFeedResult
from src.modules.operations.application.dto.terminal_dto import StartTerminalSessionCommand
from src.modules.operations.application.dto.terminal_dto import TerminalChallengeResult
from src.modules.operations.application.dto.terminal_dto import TerminalDeviceStateResult
from src.modules.operations.application.dto.terminal_dto import TerminalSessionResult
from src.modules.operations.application.use_cases.infoscreen.get_infoscreen_feed import (
    GetTerminalFeed,
)
from src.modules.operations.application.use_cases.infoscreen.serve_drawing import (
    ServeInfoscreenDrawing,
)
from src.modules.operations.application.use_cases.infoscreen.serve_thumbnail import (
    ServeInfoscreenThumbnail,
)
from src.modules.operations.application.use_cases.terminal_device.get_device_state import (
    GetTerminalDeviceState,
)
from src.modules.operations.application.use_cases.terminal_device.issue_challenge import (
    IssueTerminalChallenge,
)
from src.modules.operations.application.use_cases.terminal_device.start_session import (
    StartTerminalSession,
)
from src.modules.operations.domain.entities.terminal import Terminal
from src.modules.operations.domain.value_objects.terminal import TerminalStatus
from src.modules.platform.adapters.inbound.api.live.hub import LiveHub
from src.modules.platform.adapters.inbound.api.live.hub import TerminalLiveConnection
from src.modules.platform.adapters.inbound.api.live.hub import get_live_hub
from src.modules.platform.ports.outbound.live_signal import LiveResource
from src.modules.platform.ports.outbound.live_signal import LiveSignal

router = APIRouter()

_PING_SECONDS = 15
_SEND_TIMEOUT_SECONDS = 10.0


@router.post("/challenge", response_model=TerminalChallengeResponse)
async def create_challenge(
    body: TerminalChallengeRequest,
    request: Request,
    use_case: IssueTerminalChallenge = Depends(get_issue_terminal_challenge_use_case),
) -> TerminalChallengeResult:
    """A single-use nonce, valid 60 seconds, for the bridge to sign."""
    return await use_case.execute(body.public_key, client_ip(request))


@router.post("/session", response_model=TerminalSessionResponse)
async def create_session(
    body: TerminalSessionRequest,
    request: Request,
    api_key: str | None = Header(default=None, alias="X-Api-Key"),
    use_case: StartTerminalSession = Depends(get_start_terminal_session_use_case),
) -> TerminalSessionResult:
    """A terminal access token (15 minutes) for a signed challenge. An
    unknown device needs a terminal key in `X-Api-Key`."""
    return await use_case.execute(
        StartTerminalSessionCommand(
            **body.model_dump(), api_key=api_key or None, client_ip=client_ip(request)
        )
    )


@router.get("/state", response_model=TerminalDeviceStateResponse)
async def read_state(
    terminal: Terminal = Depends(get_current_terminal),
    use_case: GetTerminalDeviceState = Depends(get_terminal_device_state_use_case),
) -> TerminalDeviceStateResult:
    """The terminal's approval, screen and commands, the power its display
    should have and the message it shows."""
    return await use_case.execute(terminal)


@router.get("/feed", response_model=InfoscreenFeedResponse)
async def read_feed(
    terminal: Terminal = Depends(get_current_terminal),
    use_case: GetTerminalFeed = Depends(get_terminal_feed_use_case),
) -> InfoscreenFeedResult:
    """The feed of the terminal's screen; 409 until it is approved and has
    one."""
    return await use_case.execute(terminal)


@router.get(
    "/thumbnails/{token}",
    response_class=Response,
    responses={200: {"content": {"image/*": {}}}, 404: {"description": "Invalid link"}},
)
async def read_thumbnail(
    token: str,
    use_case: ServeInfoscreenThumbnail = Depends(get_serve_infoscreen_thumbnail_use_case),
) -> Response:
    """An item thumbnail a feed row links to. The signed token is the only
    credential; the browser may cache the image until the link expires."""
    served = await use_case.execute(token)
    return Response(
        content=served.data,
        media_type=served.content_type,
        headers={"Cache-Control": f"private, max-age={served.max_age_seconds}"},
    )


@router.get(
    "/drawings/{token}",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}, 404: {"description": "Invalid link"}},
)
async def read_drawing(
    token: str,
    use_case: ServeInfoscreenDrawing = Depends(get_serve_infoscreen_drawing_use_case),
) -> Response:
    """The drawing a machine detail widget links to, a PDF the display
    embeds. The signed token is the only credential; the browser may cache
    the file until the link expires."""
    served = await use_case.execute(token)
    return Response(
        content=served.data,
        media_type=served.content_type,
        headers={
            "Cache-Control": f"private, max-age={served.max_age_seconds}",
            "Content-Disposition": "inline",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/live")
async def live_stream(
    terminal: Terminal = Depends(get_current_terminal),
    hub: LiveHub = Depends(get_live_hub),
    load_scope: TerminalLiveScopeLoader = Depends(get_terminal_live_scope_loader),
) -> EventSourceResponse:
    # get_db is function-scoped (see get_db in deps/database.py), so the session that
    # resolved `terminal` is closed before the stream starts.
    connection = hub.connect_terminal(
        terminal.id,
        approved=terminal.status == TerminalStatus.APPROVED.value,
        infoscreen_id=terminal.infoscreen_id,
    )
    return EventSourceResponse(
        _frames(hub, connection, load_scope),
        ping=_PING_SECONDS,
        send_timeout=_SEND_TIMEOUT_SECONDS,
        sep="\n",
    )


def _touches_own_row(connection: TerminalLiveConnection, signals: list[LiveSignal]) -> bool:
    return any(
        s.resource == LiveResource.TERMINALS and s.id in (connection.terminal_id, 0)
        for s in signals
    )


async def _frames(
    hub: LiveHub, connection: TerminalLiveConnection, load_scope: TerminalLiveScopeLoader
) -> AsyncIterator[dict[str, str]]:
    try:
        while True:
            signals = await connection.queue.get()
            if signals is None:  # evicted by the hub, or the process is shutting down
                return
            if connection.overflowed:
                connection.overflowed = False
                while not connection.queue.empty():
                    connection.queue.get_nowait()
                yield {"event": "resync", "data": "{}"}
                continue
            if _touches_own_row(connection, signals):
                # The admin may have approved, revoked or reassigned the
                # terminal, so the filter is re-read before the next signal.
                scope = await load_scope(connection.terminal_id)
                if scope is None:
                    yield {"event": "signal", "data": json.dumps([asdict(s) for s in signals])}
                    return
                connection.approved = scope.approved
                connection.infoscreen_id = scope.infoscreen_id
            yield {"event": "signal", "data": json.dumps([asdict(s) for s in signals])}
    finally:
        hub.disconnect_terminal(connection)
