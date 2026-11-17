"""Gunicorn worker class that sets uvicorn's graceful shutdown timeout, which
the stock UvicornWorker leaves unbounded. On SIGTERM in-flight requests get a
bounded window before gunicorn would kill the worker; open SSE streams end
right away and browsers reconnect.

The base class comes from the uvicorn-worker package, which replaced the
deprecated uvicorn.workers module. It merges CONFIG_KWARGS into the uvicorn
Config last, so the timeout set here wins over its defaults.
"""

from typing import Any

from uvicorn_worker import UvicornWorker

# Below gunicorn's 30s graceful_timeout (gunicorn_conf.py).
_TIMEOUT_GRACEFUL_SHUTDOWN_SECONDS = 25


class TimeoutUvicornWorker(UvicornWorker):
    # Not ClassVar, to match the base class's annotation.
    CONFIG_KWARGS: dict[str, Any] = {  # noqa: RUF012
        **UvicornWorker.CONFIG_KWARGS,
        "timeout_graceful_shutdown": _TIMEOUT_GRACEFUL_SHUTDOWN_SECONDS,
    }
