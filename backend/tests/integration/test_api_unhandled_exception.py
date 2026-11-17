"""
UnhandledExceptionMiddleware is the innermost user middleware (registered
first in main.py, see its own docstring). It converts any exception
ExceptionMiddleware doesn't already know how to map
(DomainError/HTTPException/RequestValidationError) into the standard
error envelope at 500, instead of the plain-text, context-less 500
Starlette's ServerErrorMiddleware produces on its own.

A temporary route is added directly to the real `app` for the crash,
because nothing in this app deliberately raises an unmapped exception,
removed again in the fixture's teardown so it can't leak into other
tests sharing the same module-level `app` singleton.
"""

import logging

import pytest
from starlette.routing import Route

from src.bootstrap.main import app
from src.modules.platform.const import API_WEB
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.infrastructure.config.settings import cfg

_CRASH_PATH = "/__test_unhandled_exception__"


async def _boom(request):  # Starlette endpoint signature
    raise RuntimeError("kaboom-internal-secret")


@pytest.fixture
def crash_route():
    route = Route(_CRASH_PATH, _boom, methods=["GET"])
    app.router.routes.append(route)
    try:
        yield _CRASH_PATH
    finally:
        app.router.routes.remove(route)


class TestEnvelope:
    async def test_returns_500_with_the_standard_envelope(self, client, crash_route):
        response = await client.get(crash_route)

        assert response.status_code == 500
        assert response.json() == {"detail": "Internal server error", "code": "InternalError"}

    async def test_leaks_no_internal_detail(self, client, crash_route):
        response = await client.get(crash_route)

        assert "kaboom" not in response.text
        assert "Traceback" not in response.text

    async def test_carries_a_request_id_header(self, client, crash_route):
        response = await client.get(crash_route)

        assert response.headers.get("X-Request-ID")

    async def test_keeps_the_cors_header(self, client, crash_route):
        response = await client.get(crash_route, headers={"Origin": cfg.domain})

        assert response.headers.get("access-control-allow-origin") == cfg.domain


class TestLoggingSideEffect:
    async def test_logs_exactly_one_error_record_carrying_the_request_id(
        self, client, crash_route, glados_caplog
    ):
        response = await client.get(crash_route)

        error_records = [r for r in glados_caplog.records if r.levelno == logging.ERROR]
        assert len(error_records) == 1
        record = error_records[0]
        assert record.exc_info is not None
        assert record.request_id == response.headers["X-Request-ID"]


class TestDomainErrorsAreUnaffected:
    async def test_a_mapped_404_still_returns_its_status_and_code(self, auth_client):
        client = await auth_client(permissions=[Permission.READ_SETTINGS])
        response = await client.get(f"{API_WEB}/users/999999")

        assert response.status_code == 404
        assert response.json()["code"] == "UserNotFoundError"


class TestSseIsUnaffected:
    async def test_live_stream_response_still_starts(self):
        """Regression guard for the "pure ASGI, not BaseHTTPMiddleware"
        design constraint (see the middleware's own docstring): a
        BaseHTTPMiddleware layer wraps the downstream app in its own task
        group, a known source of breakage for a StreamingResponse. This
        only confirms the response still starts; full SSE coverage lives
        in test_api_live_stream.py."""
        import asyncio
        import contextlib

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": f"{API_WEB}/live/",
            "raw_path": f"{API_WEB}/live/".encode(),
            "query_string": b"",
            "headers": [],
            "client": ("testclient", 123),
            "server": ("testclient", 80),
        }
        got_message = asyncio.Event()
        first_message: dict = {}

        async def receive() -> dict:
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

        async def send(message: dict) -> None:
            if not got_message.is_set():
                first_message.update(message)
                got_message.set()

        task = asyncio.ensure_future(app(scope, receive, send))
        try:
            await asyncio.wait_for(got_message.wait(), timeout=5)
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

        # Unauthenticated: 401 from ExceptionMiddleware's own conversion,
        # not a 500 from this middleware. This proves the request still
        # flows through unimpeded rather than hanging or crashing at this
        # layer.
        assert first_message.get("status") == 401
