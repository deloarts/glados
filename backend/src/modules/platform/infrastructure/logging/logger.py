"""
Single logger instance used across the codebase.
A ContextFilter injects request_id / user_id / username from contextvars
into every LogRecord so they appear in every line without manual threading.

The logger itself always stays at DEBUG and each handler applies its own
threshold: cfg.log_level for stdout (the StreamHandler below) and
cfg.log_db_level for DatabaseLogHandler (attached later, see main.py), so
the two can be set independently. cfg.log_format picks text vs JSON for
stdout output. settings.py does not import this module, so reading cfg
here is not a circular import.
"""

import logging

from src.modules.platform.infrastructure.config.settings import cfg
from src.modules.platform.infrastructure.logging.context import request_id_var
from src.modules.platform.infrastructure.logging.context import user_id_var
from src.modules.platform.infrastructure.logging.context import username_var
from src.modules.platform.infrastructure.logging.json_formatter import JsonFormatter


class ContextFilter(logging.Filter):
    """Stamps each LogRecord with the current request context."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        uid = user_id_var.get()
        uname = username_var.get()
        record.user_ctx = f"user={uname}(id={uid})" if uname else "-"
        return True


log = logging.getLogger("glados")
log.setLevel(logging.DEBUG)

if not log.handlers:
    _handler = logging.StreamHandler()
    _handler.setLevel(cfg.log_level)  # throttles stdout only, logger stays DEBUG
    if cfg.log_format == "json":
        _handler.setFormatter(JsonFormatter())
    else:
        _handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | rid=%(request_id)s | %(user_ctx)s | %(name)s | %(message)s"
            )
        )
    _handler.addFilter(ContextFilter())
    log.addHandler(_handler)
    log.propagate = False  # don't double-print via uvicorn's root handler
