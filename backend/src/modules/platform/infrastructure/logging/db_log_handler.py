"""
Python logging Handler that persists log records emitted by the glados
logger to log_table, off the caller's thread.

`emit` only builds the LogEntry (request id and user come from contextvars,
which are only correct on the emitting thread) and puts it on a bounded
in-memory queue. One background thread drains the queue and hands batches to
the injected persist callable, so a log call never waits on the database,
whether it comes from a request thread, the event loop or a worker. When the
queue is full the oldest entry is dropped and counted: losing old log lines
under a database outage is preferable to unbounded memory growth or blocking
the application. `stop` flushes what is queued before returning.

Errors are always swallowed, logging must never break the application. The
writer's own failure reports go to stdout only (`_skip_db`), never back into
the queue.
"""

import logging
import queue
import threading
from collections.abc import Callable

from prometheus_client import Counter

from src.modules.platform.domain.entities.log_entry import LogEntry
from src.modules.platform.infrastructure.logging.context import request_id_var
from src.modules.platform.infrastructure.logging.context import user_id_var
from src.modules.platform.infrastructure.logging.context import username_var
from src.shared_kernel.domain.services.clock import now_utc

_DEFAULT_MAX_QUEUED = 10_000
_DEFAULT_BATCH_SIZE = 200
_POLL_SECONDS = 0.5
_SKIP_DB = {"_skip_db": True}

_writer_log = logging.getLogger("glados")

LOG_RECORDS_DROPPED = Counter(
    "glados_log_records_dropped_total",
    "Log records dropped before reaching log_table: queue full, or the write failed.",
)


class DatabaseLogHandler(logging.Handler):
    """Queues log records for log_table and writes them from a background
    thread via an injected batch persist callable."""

    def __init__(
        self,
        persist_batch: Callable[[list[LogEntry]], None],
        *,
        max_queued: int = _DEFAULT_MAX_QUEUED,
        batch_size: int = _DEFAULT_BATCH_SIZE,
    ) -> None:
        super().__init__()
        self._persist_batch = persist_batch
        self._queue: queue.Queue[LogEntry] = queue.Queue(maxsize=max_queued)
        self._batch_size = batch_size
        self._stopping = threading.Event()
        self._thread: threading.Thread | None = None
        self.dropped = 0

    def start(self) -> None:
        self._stopping.clear()
        self._thread = threading.Thread(target=self._run, name="db-log-writer", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Stops the writer after flushing what is queued, waiting at most
        `timeout` seconds."""
        self._stopping.set()
        if self._thread is not None:
            self._thread.join(timeout)
            self._thread = None

    def emit(self, record: logging.LogRecord) -> None:
        # Skip persisting records marked with _skip_db (set by call sites to
        # avoid logging sensitive data or infinite loops).
        if getattr(record, "_skip_db", False) or self._stopping.is_set():
            return
        try:
            rid = request_id_var.get()
            entry = LogEntry(
                id=0,
                timestamp=now_utc(),
                user_id=user_id_var.get(),
                username=username_var.get(),
                level=record.levelname,
                message=self.format(record),
                method=None,
                path=None,
                status_code=None,
                request_id=rid if rid and rid != "-" else None,
            )
            self._enqueue(entry)
        except Exception:
            self.handleError(record)

    def _enqueue(self, entry: LogEntry) -> None:
        while True:
            try:
                self._queue.put_nowait(entry)
                return
            except queue.Full:
                try:
                    self._queue.get_nowait()
                    self.dropped += 1
                    LOG_RECORDS_DROPPED.inc()
                except queue.Empty:
                    pass

    def _run(self) -> None:
        while True:
            batch = self._next_batch()
            if batch:
                self._write(batch)
            elif self._stopping.is_set():
                return

    def _next_batch(self) -> list[LogEntry]:
        try:
            batch = [self._queue.get(timeout=_POLL_SECONDS)]
        except queue.Empty:
            return []
        while len(batch) < self._batch_size:
            try:
                batch.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return batch

    def _write(self, batch: list[LogEntry]) -> None:
        try:
            self._persist_batch(batch)
        except Exception:
            LOG_RECORDS_DROPPED.inc(len(batch))
            _writer_log.exception(
                "Could not write %d log record(s) to the database; dropping them.",
                len(batch),
                extra=_SKIP_DB,
            )
