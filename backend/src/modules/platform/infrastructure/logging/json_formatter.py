"""
Stdlib-only structured log formatter: one JSON object per line so a log
aggregator (Loki/Elastic) can filter by rid/user_id/level without
regexing the human-readable text format.
No new dependency: only `json` + `logging` from the standard library.

Attached to the StreamHandler only when `LOG_FORMAT=json` (see logger.py);
the DatabaseLogHandler always keeps its own plain `%(message)s` formatting
regardless of this setting.
"""

import json
import logging
from datetime import UTC
from datetime import datetime
from typing import Any

from src.modules.platform.infrastructure.logging.context import request_id_var
from src.modules.platform.infrastructure.logging.context import user_id_var
from src.modules.platform.infrastructure.logging.context import username_var
from src.shared_kernel.domain.services.clock import now_utc


class JsonFormatter(logging.Formatter):
    """Formats a LogRecord as a single-line JSON object.

    Reads request_id/user_id/username directly from the contextvars
    (like DatabaseLogHandler does) rather than from attributes a filter
    might stamp onto the record, so it renders correctly even if it's
    ever used on a handler without ContextFilter attached.

    Must never raise: a formatter blowing up would take stdout logging
    (and, transitively, whatever called `log.info`/`log.exception`) down
    with it. Every path here is guarded, falling back to a minimal object
    carrying just the plain message.
    """

    def format(self, record: logging.LogRecord) -> str:
        try:
            return self._format(record)
        except Exception:
            fallback: dict[str, Any] = {
                "ts": _now_iso(),
                "level": record.levelname,
                "logger": record.name,
                "msg": self._safe_message(record),
            }
            return json.dumps(fallback, ensure_ascii=False, default=str)

    def _format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": _iso(record.created),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "rid": request_id_var.get(),
            "user_id": user_id_var.get(),
            "username": username_var.get(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)

        http = getattr(record, "http", None)
        if http is not None:
            payload["http"] = http

        return json.dumps(payload, ensure_ascii=False, default=str)

    @staticmethod
    def _safe_message(record: logging.LogRecord) -> str:
        try:
            return record.getMessage()
        except Exception:
            return str(record.msg)


def _iso(epoch_seconds: float) -> str:
    """ISO-8601 UTC timestamp with millisecond precision and a `Z` suffix."""
    dt = datetime.fromtimestamp(epoch_seconds, tz=UTC)
    return f"{dt.strftime('%Y-%m-%dT%H:%M:%S')}.{dt.microsecond // 1000:03d}Z"


def _now_iso() -> str:
    return _iso(now_utc().timestamp())
