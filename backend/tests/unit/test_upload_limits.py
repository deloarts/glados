"""
The front-door upload size guard: rejects an honestly declared oversized
body with 413, lets a file exactly at its limit through (multipart overhead
included), and leaves a missing or malformed Content-Length to the use
case's own size check.
"""

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from src.modules.platform.adapters.inbound.api.upload_limits import enforce_max_upload_size
from src.modules.platform.adapters.inbound.api.upload_limits import max_upload_size
from src.modules.platform.const import MAX_UPLOAD_BYTES

_MB = 1024 * 1024


def _request(content_length: str | None) -> Request:
    headers = [] if content_length is None else [(b"content-length", content_length.encode())]
    return Request({"type": "http", "method": "POST", "path": "/", "headers": headers})


def test_file_at_its_limit_passes_with_multipart_overhead() -> None:
    max_upload_size(5 * _MB)(_request(str(5 * _MB + 4096)))


def test_declared_body_far_above_the_limit_is_rejected() -> None:
    with pytest.raises(HTTPException) as exc:
        max_upload_size(5 * _MB)(_request(str(50 * _MB)))
    assert exc.value.status_code == 413


@pytest.mark.parametrize("value", [None, "not-a-number"])
def test_missing_or_malformed_length_is_left_to_the_use_case(value: str | None) -> None:
    max_upload_size(5 * _MB)(_request(value))


def test_app_wide_ceiling_is_unchanged() -> None:
    enforce_max_upload_size(_request(str(MAX_UPLOAD_BYTES)))
    with pytest.raises(HTTPException):
        enforce_max_upload_size(_request(str(MAX_UPLOAD_BYTES + 1)))
