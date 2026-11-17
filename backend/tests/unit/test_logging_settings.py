"""
Coverage for LOG_LEVEL / LOG_FORMAT (src/modules/platform/infrastructure/config/settings.py,
src/modules/platform/infrastructure/logging/logger.py):

  - Settings defaults and validation (invalid LOG_LEVEL must fail boot,
    the way any other misconfigured env var does).
  - The handler-level split relies on: the "glados" logger itself
    stays at DEBUG, only a handler's own level throttles it, so a second
    handler (modelling DatabaseLogHandler, which is attached at DEBUG in
    main.py) still receives everything a WARNING-level stdout handler
    drops. This is stdlib logging behaviour, pinned here because the
    whole design depends on it.
  - The text format string itself is stable: LOG_FORMAT is "text" by
    default, so request_context_middleware.py produces a byte-identical
    line.

tests/conftest.py sets SECURITY__/DATABASE__/REDIS__/INIT__ env vars
process-wide (via os.environ.setdefault) whenever ENV_FILE is unset, which
is the case for this suite, so constructing a fresh Settings() here always
has everything it needs even though LOG_LEVEL/LOG_FORMAT themselves are
monkeypatched per test.
"""

import logging

import pytest
from pydantic import ValidationError

from src.modules.platform.infrastructure.config.settings import Settings
from src.modules.platform.infrastructure.logging.logger import log

_TEXT_FORMAT = (
    "%(asctime)s | %(levelname)-8s | rid=%(request_id)s | %(user_ctx)s | %(name)s | %(message)s"
)


class TestDefaults:
    def test_log_level_defaults_to_debug(self) -> None:
        assert Settings().log_level == "DEBUG"  # type: ignore[call-arg]

    def test_log_format_defaults_to_text(self) -> None:
        assert Settings().log_format == "text"  # type: ignore[call-arg]


class TestValidation:
    def test_invalid_log_level_fails_at_construction(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LOG_LEVEL", "TRACE")
        with pytest.raises(ValidationError, match="log_level"):
            Settings()  # type: ignore[call-arg]

    def test_invalid_log_format_fails_at_construction(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LOG_FORMAT", "xml")
        with pytest.raises(ValidationError, match="log_format"):
            Settings()  # type: ignore[call-arg]

    def test_valid_log_level_values_are_all_accepted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for value in ("DEBUG", "INFO", "WARNING", "ERROR"):
            monkeypatch.setenv("LOG_LEVEL", value)
            assert Settings().log_level == value  # type: ignore[call-arg]


class TestHandlerLevelSplit:
    """Models the handler-level split design: the logger stays at DEBUG, only a handler's own level
    (LOG_LEVEL, applied to the StreamHandler in logger.py) throttles what
    reaches it. A second handler at a lower level (DatabaseLogHandler,
    always attached without a level restriction, see main.py) still gets
    every record."""

    def test_warning_level_handler_drops_info_but_a_second_handler_still_gets_it(self) -> None:
        test_logger = logging.getLogger("glados.test.handler-level-split")
        test_logger.setLevel(logging.DEBUG)  # logger itself: always DEBUG
        test_logger.propagate = False

        stdout_like: list[logging.LogRecord] = []
        db_like: list[logging.LogRecord] = []

        class _Collector(logging.Handler):
            def __init__(self, sink: list[logging.LogRecord]) -> None:
                super().__init__()
                self._sink = sink

            def emit(self, record: logging.LogRecord) -> None:
                self._sink.append(record)

        stream_handler = _Collector(stdout_like)
        stream_handler.setLevel("WARNING")  # mirrors cfg.log_level="WARNING"

        db_handler = _Collector(db_like)  # no setLevel(): mirrors DatabaseLogHandler

        test_logger.addHandler(stream_handler)
        test_logger.addHandler(db_handler)
        try:
            test_logger.info("only the DB-like handler should see this")
            test_logger.warning("both handlers should see this")
        finally:
            test_logger.removeHandler(stream_handler)
            test_logger.removeHandler(db_handler)

        assert [r.getMessage() for r in stdout_like] == ["both handlers should see this"]
        assert [r.getMessage() for r in db_like] == [
            "only the DB-like handler should see this",
            "both handlers should see this",
        ]


class TestTextFormatRegression:
    def test_real_logger_stream_handler_uses_the_unchanged_text_format(self) -> None:
        """The real "glados" logger's StreamHandler is built
        with the plain-text formatter. Pins the exact format string so a
        future edit to logger.py can't silently change the on-disk /
        stdout log line shape."""
        stream_handlers = [
            h
            for h in log.handlers
            if isinstance(h, logging.StreamHandler) and type(h) is logging.StreamHandler
        ]
        assert len(stream_handlers) == 1, "expected exactly the one StreamHandler logger.py builds"

        formatter = stream_handlers[0].formatter
        assert formatter is not None
        # `_fmt` is CPython's own attribute name (logging.Formatter keeps it for
        # back-compat); there is no public accessor for the raw format string.
        assert formatter._fmt == _TEXT_FORMAT
