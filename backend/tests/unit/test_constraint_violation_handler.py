"""
A write that broke a database constraint and reached the API, whether raised
as the port-level ConstraintViolationError or as the persistence adapter's
SqlConstraintViolationError, answers 409 with the code ConflictError, through
the handlers the app registers. The constraint is logged, never returned.
"""

import json

import httpx
from fastapi import FastAPI

from src.modules.platform.adapters.inbound.api.exception_handlers import (
    constraint_violation_handler,
)
from src.modules.platform.adapters.inbound.api.exception_handlers import register_exception_handlers
from src.modules.platform.adapters.outbound.persistence.constraint_violation import (
    SqlConstraintViolationError,
)
from src.modules.platform.ports.outbound.unit_of_work_port import ConstraintViolationError


def _app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/port")
    async def port() -> None:
        raise ConstraintViolationError("ix_order_table_order_number")

    @app.get("/sql")
    async def sql() -> None:
        raise SqlConstraintViolationError(
            "INSERT INTO order_table (order_number) VALUES (?)",
            ("ORD-10",),
            Exception("UNIQUE constraint failed: order_table.order_number"),
        )

    return app


async def _get(path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


async def test_a_port_constraint_violation_is_a_409_with_the_conflict_code(glados_caplog) -> None:
    response = await _get("/port")

    assert response.status_code == 409
    assert response.json()["code"] == "ConflictError"


async def test_a_sql_constraint_violation_is_a_409_with_the_conflict_code(glados_caplog) -> None:
    response = await _get("/sql")

    assert response.status_code == 409
    assert response.json()["code"] == "ConflictError"


async def test_the_answer_never_echoes_the_constraint_or_the_statement(glados_caplog) -> None:
    for path in ("/port", "/sql"):
        detail = (await _get(path)).json()["detail"]

        assert "order_table" not in detail
        assert "order_number" not in detail
        assert "INSERT" not in detail


async def test_the_constraint_is_logged_as_a_warning(glados_caplog) -> None:
    response = await constraint_violation_handler(
        None,  # type: ignore[arg-type]
        ConstraintViolationError("fk_order_item_order_id"),
    )

    assert json.loads(bytes(response.body))["code"] == "ConflictError"
    assert any(
        r.levelname == "WARNING" and "fk_order_item_order_id" in r.getMessage()
        for r in glados_caplog.records
    )
