"""
Pure-ASGI middleware that wraps the audit log and every layer below it:
  - Mints a short request ID, or propagates X-Request-ID from the caller
    when it is a plain token of at most 64 characters. Anything else is
    replaced: the ID is stored with every log and audit row, so an
    oversized or malformed value would make those inserts fail.
  - Stores it in request_id_var so every log line in the same request
    carries the same ID automatically via ContextFilter.
  - Echoes the ID back in the X-Request-ID response header.
  - Stores the client address and user agent in their context vars, for
    the security log entries the request writes.
  - Logs every HTTP request with method, path, status, and elapsed time.
"""

import re
import time
import uuid

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp
from starlette.types import Message
from starlette.types import Receive
from starlette.types import Scope
from starlette.types import Send

from src.modules.platform.const import API_WEB
from src.modules.platform.infrastructure.logging.context import client_ip_var
from src.modules.platform.infrastructure.logging.context import request_id_var
from src.modules.platform.infrastructure.logging.context import user_agent_var
from src.modules.platform.infrastructure.logging.logger import log

# The live SSE connection stays open for the life of the tab, so logging it
# here would log one "HTTP GET" line per connection at disconnect with an
# elapsed_ms equal to the whole connection's lifetime, noise that poisons
# latency dashboards rather than useful request telemetry.
_SKIP_LOG_PATHS = {"/health", "/ready", "/metrics", f"{API_WEB}/live/"}


_REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9._-]{1,64}")


def accepted_request_id(raw: bytes) -> str | None:
    """The caller-supplied request ID if it is safe to store, else None."""
    value = raw.decode("latin-1")
    return value if _REQUEST_ID_PATTERN.fullmatch(value) else None


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self._app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        rid = accepted_request_id(headers.get(b"x-request-id", b"")) or str(uuid.uuid4())[:8]

        token = request_id_var.set(rid)
        client = scope.get("client")
        ip_token = client_ip_var.set(client[0] if client else None)
        user_agent = headers.get(b"user-agent")
        agent_token = user_agent_var.set(user_agent.decode("latin-1") if user_agent else None)
        t0 = time.perf_counter()

        method = scope.get("method", "")
        path = scope.get("path", "")
        status_code: int = 0

        async def send_with_header(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                mutable = MutableHeaders(scope=message)
                mutable.append("X-Request-ID", rid)
            await send(message)

        try:
            await self._app(scope, receive, send_with_header)
        finally:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            if scope["type"] == "http" and path not in _SKIP_LOG_PATHS:
                log.info(
                    "HTTP %s %s → %s [%.1fms]",
                    method,
                    path,
                    status_code or "-",
                    elapsed_ms,
                    extra={
                        "_skip_db": True,
                        # Structured mirror of the message above, for
                        # LOG_FORMAT=json consumers (Loki/Elastic) to filter
                        # on. Ignored by the text formatter and by
                        # DatabaseLogHandler, so the text line is unchanged.
                        "http": {
                            "method": method,
                            "path": path,
                            "status": status_code,
                            "elapsed_ms": round(elapsed_ms, 1),
                        },
                    },
                )
            request_id_var.reset(token)
            client_ip_var.reset(ip_token)
            user_agent_var.reset(agent_token)
