"""
The request validation handler answers like FastAPI's default handler,
the encoded errors under `detail` with status 422, byte for byte. The one
difference is a NaN or infinite input, which it echoes as text because
the response encoder refuses such values.
"""

import json
import math

import pytest
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from starlette.requests import Request

from src.modules.platform.adapters.inbound.api.exception_handlers import (
    request_validation_error_handler,
)


def _request() -> Request:
    return Request({"type": "http", "method": "PUT", "path": "/", "headers": []})


async def test_validation_handler_renders_an_ordinary_error_like_fastapis_default() -> None:
    exc = RequestValidationError(
        [
            {
                "type": "float_parsing",
                "loc": ("query", "quantity"),
                "msg": "Input should be a valid number, unable to parse string as a number",
                "input": "abc",
            },
            {
                "type": "missing",
                "loc": ("body", "rejection_reason"),
                "msg": "Field required",
                "input": {"quantity_rejected": 1.5, "note": "dented"},
            },
        ]
    )

    ours = await request_validation_error_handler(_request(), exc)
    default = await request_validation_exception_handler(_request(), exc)

    assert ours.status_code == default.status_code == 422
    assert ours.body == default.body


@pytest.mark.parametrize(
    ("value", "echoed"),
    [(math.nan, "NaN"), (math.inf, "Infinity"), (-math.inf, "-Infinity")],
)
async def test_validation_handler_echoes_a_non_finite_input_as_text(
    value: float, echoed: str
) -> None:
    exc = RequestValidationError(
        [
            {
                "type": "finite_number",
                "loc": ("body", "quantity_rejected"),
                "msg": "Input should be a finite number",
                "input": value,
            },
            {
                "type": "missing",
                "loc": ("body", "rejections", 0, "rejection_reason"),
                "msg": "Field required",
                "input": {"quantity_rejected": value, "note": "dented", "pieces": [value, 2.0]},
            },
        ]
    )

    response = await request_validation_error_handler(_request(), exc)

    assert response.status_code == 422
    detail = json.loads(response.body)["detail"]
    assert detail[0] == {
        "type": "finite_number",
        "loc": ["body", "quantity_rejected"],
        "msg": "Input should be a finite number",
        "input": echoed,
    }
    assert detail[1]["loc"] == ["body", "rejections", 0, "rejection_reason"]
    assert detail[1]["input"] == {
        "quantity_rejected": echoed,
        "note": "dented",
        "pieces": [echoed, 2.0],
    }
