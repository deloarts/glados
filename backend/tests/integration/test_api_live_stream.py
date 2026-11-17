"""
Integration coverage for the live row-sync SSE endpoint
(src/modules/platform/adapters/inbound/api/v1/web/endpoints/live.py): just auth and response
shape.

The 200 case is driven through a raw ASGI scope/receive/send harness rather
than TestClient/httpx, verified empirically that httpx's ASGITransport
(both TestClient and a bare httpx.AsyncClient) does not return control from
`.stream()` until the response body iterator finishes or yields past its
first chunk into a quiet period, which for an intentionally infinite SSE
stream never happens; `.stream()` simply hangs forever, timeout= or not.
Driving the ASGI callable directly sidesteps that transport limitation:
this only waits for the `http.response.start` message and then cancels.

Message delivery is separately not asserted here even with this harness:
TestClient-style helpers aside, broadcasting from the test would still need
to reach LiveHub's asyncio.Queue on the same running loop as the endpoint's
generator, which this harness deliberately doesn't wire up. Delivery is
covered by tests/unit/test_live_hub.py and tests/unit/test_live_subscriber.py.
"""

import asyncio
import contextlib
from collections.abc import Callable
from collections.abc import Generator

from sqlalchemy.orm import Session

from src.bootstrap.main import app
from src.modules.platform.adapters.inbound.api.deps.database import get_db
from src.modules.platform.adapters.outbound.persistence.session import SessionLocal
from src.modules.platform.const import API_WEB

from .conftest import auth_headers

_LIVE_PATH = f"{API_WEB}/live/"


async def _get_response_start(
    headers: dict[str, str], on_start: Callable[[], None] | None = None
) -> dict:
    """Drives `app` through a raw ASGI request for `_LIVE_PATH`, returning
    the `http.response.start` message and then cancelling the connection,
    never reads the (intentionally infinite) body. `on_start` runs while the
    stream is still open, after the response has started."""
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": _LIVE_PATH,
        "raw_path": _LIVE_PATH.encode(),
        "query_string": b"",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": ("testclient", 123),
        "server": ("testclient", 80),
    }

    got_start = asyncio.Event()
    start_message: dict = {}

    async def receive() -> dict:
        # Simulates a connection that stays open (no immediate disconnect),
        # resolves only when the harness cancels the app task below.
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    async def send(message: dict) -> None:
        if message["type"] == "http.response.start" and not got_start.is_set():
            start_message.update(message)
            got_start.set()

    task = asyncio.ensure_future(app(scope, receive, send))
    try:
        await asyncio.wait_for(got_start.wait(), timeout=5)
        if on_start is not None:
            on_start()
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    return start_message


def _header(message: dict, name: bytes) -> str | None:
    for key, value in message.get("headers", []):
        if key == name:
            return value.decode()
    return None


async def test_unauthenticated_stream_is_rejected(client):
    response = await client.get(_LIVE_PATH)
    assert response.status_code == 401


async def test_authenticated_stream_opens(create_user):
    user = await create_user()
    message = await _get_response_start(await auth_headers(user))

    assert message["status"] == 200
    assert _header(message, b"content-type").startswith("text/event-stream")
    assert _header(message, b"x-accel-buffering") == "no"


async def test_stream_does_not_hold_the_request_db_session(create_user):
    user = await create_user()
    closed: list[bool] = []

    def tracking_get_db() -> Generator[Session]:
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
            closed.append(True)

    def assert_session_closed() -> None:
        assert closed == [True]

    app.dependency_overrides[get_db] = tracking_get_db
    try:
        message = await _get_response_start(
            await auth_headers(user), on_start=assert_session_closed
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert message["status"] == 200
