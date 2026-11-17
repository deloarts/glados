"""
A caller-supplied X-Request-ID is only propagated when it is a plain token
that fits log_table.request_id; anything else is replaced by a minted ID.
"""

import pytest

from src.modules.platform.adapters.inbound.api.middleware.request_context_middleware import (
    accepted_request_id,
)


@pytest.mark.parametrize(
    "raw",
    [b"abc123", b"0b371855-9dd4-456b-974b-34840742e713", b"a" * 64, b"req.1_2-3"],
)
def test_plain_tokens_up_to_64_characters_are_kept(raw: bytes) -> None:
    assert accepted_request_id(raw) == raw.decode()


@pytest.mark.parametrize(
    "raw",
    [b"", b"a" * 65, b"has space", b"semi;colon", b"\xff\xfe", b"line\nbreak"],
)
def test_anything_else_is_rejected(raw: bytes) -> None:
    assert accepted_request_id(raw) is None
