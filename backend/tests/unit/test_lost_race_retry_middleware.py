"""
LostRaceRetryMiddleware over a small ASGI app: a write that lost a race
and committed nothing runs once more and the client gets the second
answer, with the body read again; a write that committed first, a 503 of
another cause and a read are answered as they came.
"""

import json
from typing import Any

import httpx
from sqlalchemy.orm import Session
from starlette.types import Receive
from starlette.types import Scope
from starlette.types import Send

from src.modules.platform.adapters.inbound.api.middleware.lost_race_retry_middleware import (
    LostRaceRetryMiddleware,
)
from src.modules.platform.adapters.outbound.persistence.commit_tracking import _mark_commit

_LOST = {"detail": "collided", "code": "DatabaseConflictError"}


class _App:
    """Answers the n-th call with answers[n] and records each body read."""

    def __init__(self, *answers: tuple[int, dict[str, Any]], commits: bool = False) -> None:
        self.answers = list(answers)
        self.bodies: list[bytes] = []
        self.commits = commits

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        body = b""
        while True:
            message = await receive()
            body += message.get("body", b"")
            if not message.get("more_body"):
                break
        self.bodies.append(body)
        if self.commits:
            _mark_commit(Session())
        status, payload = self.answers[len(self.bodies) - 1]
        data = json.dumps(payload).encode()
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": data})


async def _call(app: _App, method: str = "POST") -> httpx.Response:
    wrapped = LostRaceRetryMiddleware(app, delay_seconds=(0.0, 0.0))
    transport = httpx.ASGITransport(app=wrapped)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, "/x", content=b'{"quantity": 4}')


async def test_a_lost_race_that_committed_nothing_runs_once_more() -> None:
    app = _App((503, _LOST), (200, {"ok": True}))

    response = await _call(app)

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert app.bodies == [b'{"quantity": 4}', b'{"quantity": 4}']


async def test_a_lock_timeout_that_committed_nothing_runs_once_more() -> None:
    app = _App((503, {"code": "DatabaseLockTimeoutError"}), (200, {"ok": True}))

    response = await _call(app)

    assert response.status_code == 200
    assert len(app.bodies) == 2


async def test_a_second_lost_race_is_answered_with_its_503() -> None:
    app = _App((503, _LOST), (503, _LOST))

    response = await _call(app)

    assert response.status_code == 503
    assert len(app.bodies) == 2


async def test_a_request_that_committed_is_not_run_again() -> None:
    app = _App((503, _LOST), (200, {"ok": True}), commits=True)

    response = await _call(app)

    assert response.status_code == 503
    assert len(app.bodies) == 1


async def test_another_503_is_not_run_again() -> None:
    app = _App((503, {"code": "DatabaseTimeoutError"}), (200, {"ok": True}))

    response = await _call(app)

    assert response.json()["code"] == "DatabaseTimeoutError"
    assert len(app.bodies) == 1


async def test_a_read_is_not_run_again() -> None:
    app = _App((503, _LOST), (200, {"ok": True}))

    response = await _call(app, method="GET")

    assert response.status_code == 503
    assert len(app.bodies) == 1
