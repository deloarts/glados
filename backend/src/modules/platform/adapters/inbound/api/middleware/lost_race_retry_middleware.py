"""
Runs a write request once more when it lost a race in the database. A
deadlock or a serialization failure (SQLSTATE 40P01 or 40001) rolls the
transaction back and answers 503 DatabaseConflictError, and a row lock wait
that hit lock_timeout (55P03) answers 503 DatabaseLockTimeoutError
(exception_handlers.py). When the request committed nothing, it had no
effect, and the outbox holds its events back until a commit, so it is run
again after a short random delay with a fresh session, lock plan and
reconciler, which the dependencies build anew; this answer, success or
failure, is the one the client gets. A request that committed before it
failed is answered with the 503 and repeated by the client.

Pure ASGI, like UnhandledExceptionMiddleware, which it wraps: the request
body is recorded as the app reads it so the second run reads it again, and
a 503 answer is held back until it is clear whether to send it or retry.
Every other answer streams through unchanged.
"""

import asyncio
import json
import random

from starlette.types import ASGIApp
from starlette.types import Message
from starlette.types import Receive
from starlette.types import Scope
from starlette.types import Send

from src.modules.platform.adapters.outbound.persistence.commit_tracking import track_commits
from src.modules.platform.infrastructure.logging.logger import log

_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_LOST_RACE_CODES = frozenset({"DatabaseConflictError", "DatabaseLockTimeoutError"})
_RETRY_DELAY_SECONDS = (0.05, 0.25)


def _lost_race(held: list[Message]) -> bool:
    body = b"".join(m.get("body", b"") for m in held if m["type"] == "http.response.body")
    try:
        payload = json.loads(body)
    except ValueError:
        return False
    return isinstance(payload, dict) and payload.get("code") in _LOST_RACE_CODES


class LostRaceRetryMiddleware:
    def __init__(
        self, app: ASGIApp, *, delay_seconds: tuple[float, float] = _RETRY_DELAY_SECONDS
    ) -> None:
        self._app = app
        self._delay = delay_seconds

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] not in _WRITE_METHODS:
            await self._app(scope, receive, send)
            return

        received: list[Message] = []

        async def recording_receive() -> Message:
            message = await receive()
            received.append(message)
            return message

        held: list[Message] = []
        status: int | None = None

        async def holding_send(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            if status == 503:
                held.append(message)
            else:
                await send(message)

        with track_commits() as committed:
            await self._app(scope, recording_receive, holding_send)

        if status == 503 and not committed() and _lost_race(held):
            log.warning(
                "%s %s lost a race in the database and runs once more.",
                scope["method"],
                scope["path"],
            )
            await asyncio.sleep(random.uniform(*self._delay))
            replay = iter(received)

            async def replaying_receive() -> Message:
                return next(replay, None) or await receive()

            await self._app(scope, replaying_receive, send)
            return

        for message in held:
            await send(message)
