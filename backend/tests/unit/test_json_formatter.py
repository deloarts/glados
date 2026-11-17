"""
Coverage for JsonFormatter (src/modules/platform/infrastructure/logging/json_formatter.py),
added for LOG_FORMAT=json. Pins the exact key set a JSON line carries,
that rid/user_id/username come from the request-context contextvars
(not from ContextFilter's record attributes: JsonFormatter must render
correctly even without that filter attached), and that a formatter
failure never raises out of `format()`.
"""

import json
import logging
import sys
from types import TracebackType

import pytest

from src.modules.platform.infrastructure.logging.context import request_id_var
from src.modules.platform.infrastructure.logging.context import user_id_var
from src.modules.platform.infrastructure.logging.context import username_var
from src.modules.platform.infrastructure.logging.json_formatter import JsonFormatter

_BASE_KEYS = {"ts", "level", "logger", "msg", "rid", "user_id", "username"}

_ExcInfo = (
    tuple[type[BaseException], BaseException, TracebackType | None] | tuple[None, None, None] | None
)


def _make_record(
    msg: object = "hello",
    args: tuple[object, ...] = (),
    level: int = logging.INFO,
    exc_info: _ExcInfo = None,
    extra: dict[str, object] | None = None,
) -> logging.LogRecord:
    record = logging.LogRecord(
        name="glados.test",
        level=level,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=args,
        exc_info=exc_info,
    )
    for key, value in (extra or {}).items():
        setattr(record, key, value)
    return record


@pytest.fixture
def formatter() -> JsonFormatter:
    return JsonFormatter()


@pytest.fixture(autouse=True)
def _reset_context_vars():
    """Every context var pinned to its default before and after each test,
    so a value set here (or left over from some other test elsewhere in
    the suite, sharing the same thread-local context) never leaks in."""

    def _defaults() -> None:
        request_id_var.set("-")
        user_id_var.set(None)
        username_var.set(None)

    _defaults()
    yield
    _defaults()


class TestKeySet:
    def test_plain_record_has_exactly_the_base_keys(self, formatter: JsonFormatter) -> None:
        payload = json.loads(formatter.format(_make_record()))
        assert set(payload.keys()) == _BASE_KEYS

    def test_exc_key_added_only_when_exc_info_present(self, formatter: JsonFormatter) -> None:
        payload = json.loads(formatter.format(_make_record()))
        assert "exc" not in payload

        try:
            raise ValueError("boom")
        except ValueError:
            record = _make_record(msg="it failed", exc_info=sys.exc_info())
        payload = json.loads(formatter.format(record))
        assert set(payload.keys()) == _BASE_KEYS | {"exc"}
        assert "ValueError: boom" in payload["exc"]

    def test_http_key_added_only_when_extra_present(self, formatter: JsonFormatter) -> None:
        http = {"method": "GET", "path": "/api/v1/web/users/", "status": 200, "elapsed_ms": 12.3}
        record = _make_record(extra={"http": http})
        payload = json.loads(formatter.format(record))
        assert set(payload.keys()) == _BASE_KEYS | {"http"}
        assert payload["http"] == http

    def test_unknown_extras_are_ignored(self, formatter: JsonFormatter) -> None:
        record = _make_record(extra={"_skip_db": True, "some_random_field": "noise"})
        payload = json.loads(formatter.format(record))
        assert set(payload.keys()) == _BASE_KEYS


class TestContextVars:
    def test_rid_user_id_username_come_from_contextvars(self, formatter: JsonFormatter) -> None:
        request_id_var.set("req-abc123")
        user_id_var.set(42)
        username_var.set("alice")

        payload = json.loads(formatter.format(_make_record()))

        assert payload["rid"] == "req-abc123"
        assert payload["user_id"] == 42
        assert payload["username"] == "alice"

    def test_defaults_when_no_context_set(self, formatter: JsonFormatter) -> None:
        payload = json.loads(formatter.format(_make_record()))
        assert payload["rid"] == "-"
        assert payload["user_id"] is None
        assert payload["username"] is None


class TestMessageFormatting:
    def test_percent_args_are_formatted(self, formatter: JsonFormatter) -> None:
        record = _make_record(msg="Hello %s, you are %d", args=("world", 42))
        payload = json.loads(formatter.format(record))
        assert payload["msg"] == "Hello world, you are 42"

    def test_non_ascii_is_kept_literal_not_escaped(self, formatter: JsonFormatter) -> None:
        record = _make_record(msg="café 文字")
        rendered = formatter.format(record)

        # ensure_ascii=False: the raw line itself must carry the literal
        # characters, not a \uXXXX escape sequence.
        assert "café" in rendered
        assert "文字" in rendered
        assert json.loads(rendered)["msg"] == "café 文字"


class TestNeverRaises:
    def test_unserialisable_extra_still_yields_valid_json(self, formatter: JsonFormatter) -> None:
        class Explodes:
            def __str__(self) -> str:
                raise RuntimeError("even __str__ is broken")

        record = _make_record(msg="carries a broken extra", extra={"http": {"bad": Explodes()}})

        rendered = formatter.format(record)
        payload = json.loads(rendered)  # must not raise
        assert "msg" in payload

    def test_message_that_cannot_be_formatted_still_yields_valid_json(
        self, formatter: JsonFormatter
    ) -> None:
        # %d with a non-numeric arg raises inside record.getMessage().
        record = _make_record(msg="count: %d", args=("not-a-number",))
        rendered = formatter.format(record)
        payload = json.loads(rendered)  # must not raise
        assert "msg" in payload
