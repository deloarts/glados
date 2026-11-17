"""
Database metrics and slow-query logging for the app engine.

`glados_db_pool_checked_out` follows the pool's own checkout and checkin
events, so with multiprocess_mode="livesum" it reads as the number of
connections all workers hold right now; compared with the configured
budget it shows how close the pool runs to exhaustion. Statements that
take longer than DATABASE__SLOW_QUERY_THRESHOLD_MS are logged as warnings
(statement text only, never parameters, which can carry personal data) and
counted in `glados_db_slow_queries_total`. Postgres logs the same with
log_min_duration_statement (docker-compose.yml); this side ties a slow
statement to the request id and user of the request that issued it.
"""

import time
from typing import Any

from prometheus_client import Counter
from prometheus_client import Gauge
from sqlalchemy import event
from sqlalchemy.engine import Engine

from src.modules.platform.infrastructure.logging.logger import log

DB_POOL_CHECKED_OUT = Gauge(
    "glados_db_pool_checked_out",
    "Database connections currently checked out of the app pool.",
    multiprocess_mode="livesum",
)
DB_SLOW_QUERIES = Counter(
    "glados_db_slow_queries_total",
    "Statements that ran longer than the slow-query threshold.",
)

_START_KEY = "glados_query_start"
_MAX_LOGGED_STATEMENT = 500


def register_db_observability(sync_engine: Engine, slow_query_threshold_ms: int) -> None:
    """Attaches the pool gauge and the slow-query timer to an engine (the
    sync facade of the async engine). A threshold of 0 disables the
    slow-query log; the pool gauge is always on."""

    @event.listens_for(sync_engine, "checkout")
    def _on_checkout(*_: Any) -> None:
        DB_POOL_CHECKED_OUT.inc()

    @event.listens_for(sync_engine, "checkin")
    def _on_checkin(*_: Any) -> None:
        DB_POOL_CHECKED_OUT.dec()

    if slow_query_threshold_ms <= 0:
        return
    threshold_s = slow_query_threshold_ms / 1000

    @event.listens_for(sync_engine, "before_cursor_execute")
    def _before(conn: Any, cursor: Any, statement: str, *_: Any) -> None:
        conn.info.setdefault(_START_KEY, []).append(time.perf_counter())

    @event.listens_for(sync_engine, "after_cursor_execute")
    def _after(conn: Any, cursor: Any, statement: str, *_: Any) -> None:
        starts = conn.info.get(_START_KEY)
        if not starts:
            return
        elapsed = time.perf_counter() - starts.pop()
        if elapsed >= threshold_s:
            DB_SLOW_QUERIES.inc()
            log.warning(
                "Slow query (%.0f ms): %s",
                elapsed * 1000,
                " ".join(statement.split())[:_MAX_LOGGED_STATEMENT],
            )
