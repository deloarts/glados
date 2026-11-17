"""
A write that lost its optimistic version check (StaleDataError) and the
domain's ConcurrentModificationError both answer 409 with the code
ConcurrentModificationError, through the handlers the app registers.
"""

import json

import httpx
from fastapi import FastAPI
from sqlalchemy.orm.exc import StaleDataError

from src.modules.platform.adapters.inbound.api.exception_handlers import register_exception_handlers
from src.modules.platform.adapters.inbound.api.exception_handlers import stale_data_error_handler
from src.modules.platform.domain.exceptions import ConcurrentModificationError


def _app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/stale")
    async def stale() -> None:
        raise StaleDataError(
            "UPDATE statement on table 'order_table' expected to update 1 row(s); 0 were matched."
        )

    @app.get("/moved")
    async def moved() -> None:
        raise ConcurrentModificationError("Order #4 gained a line while it was being canceled.")

    return app


async def _get(path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


async def test_a_stale_write_is_a_409_with_the_concurrent_modification_code(glados_caplog) -> None:
    response = await _get("/stale")

    assert response.status_code == 409
    assert response.json()["code"] == "ConcurrentModificationError"


async def test_a_stale_write_never_echoes_the_statement(glados_caplog) -> None:
    response = await _get("/stale")

    assert "order_table" not in response.json()["detail"]
    assert "UPDATE" not in response.json()["detail"]


async def test_a_stale_write_is_logged_as_a_warning(glados_caplog) -> None:
    response = await stale_data_error_handler(None, StaleDataError("0 were matched"))  # type: ignore[arg-type]

    assert json.loads(bytes(response.body))["code"] == "ConcurrentModificationError"
    assert any(
        r.levelname == "WARNING" and "Concurrent modification" in r.getMessage()
        for r in glados_caplog.records
    )


async def test_the_domain_error_is_a_409_that_keeps_its_message(glados_caplog) -> None:
    response = await _get("/moved")

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Order #4 gained a line while it was being canceled.",
        "code": "ConcurrentModificationError",
    }
