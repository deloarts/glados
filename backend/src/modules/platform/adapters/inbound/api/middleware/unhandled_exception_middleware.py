"""
Catch-all for exceptions that are not a `DomainError`/`HTTPException`/
`RequestValidationError` (those are already converted by Starlette's own
`ExceptionMiddleware`, which sits just inside this one). Without this,
such an exception reaches Starlette's `ServerErrorMiddleware` instead,
which sits *outside* every user middleware: the response it sends is
plain text with no `X-Request-ID` and no CORS header (a browser sees a
CORS failure, not a 500), `RequestContextMiddleware` logs the request as
"→ -" because `http.response.start` never reaches its wrapped `send`,
and it re-raises after responding, so uvicorn/TestClient still surface
the traceback.

Deliberately pure ASGI, not `BaseHTTPMiddleware`: the latter wraps the
downstream app in its own task group, which is a known source of
regressions for streaming responses (the SSE route at `/api/v1/web/live/`
in particular).

Registered as the *first* `add_middleware` call in `main.py`, i.e. the
innermost user middleware, just outside `ExceptionMiddleware`. That
placement is what makes this work: CORS, `DatabaseLoggingMiddleware`,
`RequestContextMiddleware` and `SecurityHeadersMiddleware` all sit
outside it, so once this middleware turns the crash into an ordinary
`JSONResponse`, every one of those layers still runs against it exactly
as it would for any other response, adding `X-Request-ID`, the CORS
headers, the security headers, and the DB/HTTP log rows.
"""

from collections.abc import MutableMapping
from typing import Any

from fastapi.responses import JSONResponse
from starlette.types import ASGIApp
from starlette.types import Message
from starlette.types import Receive
from starlette.types import Scope
from starlette.types import Send

from src.modules.platform.infrastructure.logging.logger import log

_ENVELOPE: MutableMapping[str, Any] = {"detail": "Internal server error", "code": "InternalError"}


class UnhandledExceptionMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        response_started = False

        async def send_tracking_start(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self._app(scope, receive, send_tracking_start)
        except Exception:
            # Unconditional: this is the last-resort record of a bug that
            # would otherwise surface only as a client-visible 500 with no
            # server-side trace. request_id/user context is still live here
            # (RequestContextMiddleware/DatabaseLoggingMiddleware sit
            # outside this one and haven't unwound yet).
            log.exception("Unhandled exception during %s %s.", scope["method"], scope["path"])
            if response_started:
                # A partial response already went out, nothing left to do
                # but let it surface the way it would have before this
                # middleware existed.
                raise
            response = JSONResponse(status_code=500, content=dict(_ENVELOPE))
            await response(scope, receive, send)
