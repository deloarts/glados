"""
Coverage for the `http` structured extra added to RequestContextMiddleware's
access-log line (src/modules/platform/adapters/inbound/api/middleware/
request_context_middleware.py): the JSON formatter reads it (see
test_json_formatter.py), but the plain-text
line every deployment has always produced must render byte-identical to
before: extras that aren't part of the format string are invisible to it.

Modelled on tests/unit/test_security_headers_middleware.py: a minimal
FastAPI app wrapping only RequestContextMiddleware, not the real create_app().
"""

import logging
import re

import httpx
from _pytest.logging import LogCaptureFixture
from fastapi import FastAPI

from src.modules.platform.adapters.inbound.api.middleware.request_context_middleware import (
    RequestContextMiddleware,
)
from src.modules.platform.infrastructure.logging.logger import log


def _make_app() -> FastAPI:
    app = FastAPI()

    @app.get("/ok")
    def ok() -> dict[str, str]:
        return {"status": "ok"}

    app.add_middleware(RequestContextMiddleware)
    return app


def _find_http_record(records: list[logging.LogRecord]) -> logging.LogRecord:
    for record in records:
        if record.getMessage().startswith("HTTP GET /ok"):
            return record
    raise AssertionError(f"no 'HTTP GET /ok' record among {[r.getMessage() for r in records]}")


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")


async def test_the_http_extra_carries_the_four_structured_fields(
    glados_caplog: LogCaptureFixture,
) -> None:
    client = _client(_make_app())
    response = await client.get("/ok")
    assert response.status_code == 200

    record = _find_http_record(glados_caplog.records)
    http = record.http  # type: ignore[attr-defined]

    assert http["method"] == "GET"
    assert http["path"] == "/ok"
    assert http["status"] == 200
    assert isinstance(http["elapsed_ms"], float)
    # round(elapsed_ms, 1): never more than one decimal place.
    assert http["elapsed_ms"] == round(http["elapsed_ms"], 1)


async def test_the_text_line_is_byte_identical_to_before(glados_caplog: LogCaptureFixture) -> None:
    """The `http` extra must be invisible to the text formatter: it isn't
    named in the format string, so adding it cannot change what stdout
    prints in LOG_FORMAT=text (the default; see test_logging_settings.py)."""
    client = _client(_make_app())
    await client.get("/ok")

    record = _find_http_record(glados_caplog.records)

    # The real StreamHandler logger.py builds (not glados_caplog's own
    # handler, which addHandler()-ed on top of it for this test): renders
    # with the actual production formatter, so this exercises the real
    # ContextFilter + text-formatter pipeline end to end.
    stream_handler = next(
        h
        for h in log.handlers
        if isinstance(h, logging.StreamHandler) and type(h) is logging.StreamHandler
    )
    rendered = stream_handler.formatter.format(record)  # type: ignore[union-attr]

    pattern = (
        r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} \| INFO {5}\| "
        r"rid=[0-9a-fA-F-]+ \| - \| glados \| HTTP GET /ok → 200 \[\d+\.\dms\]$"
    )
    assert re.match(pattern, rendered), rendered
