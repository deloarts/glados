"""
DatabaseLogHandler queues records and writes them in batches from its own
thread: the emitting call never touches the database, request context is
captured at emit time, a full queue drops the oldest entries, a failing
write is swallowed, and stop() flushes what is still queued.
"""

import logging
import threading

from src.modules.platform.domain.entities.log_entry import LogEntry
from src.modules.platform.infrastructure.logging.context import request_id_var
from src.modules.platform.infrastructure.logging.db_log_handler import DatabaseLogHandler


def _logger(handler: logging.Handler, name: str) -> logging.Logger:
    logger = logging.getLogger(f"glados.test.dblog.{name}")
    logger.handlers = [handler]
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    return logger


def test_records_are_written_in_batches_and_flushed_on_stop() -> None:
    written: list[LogEntry] = []
    handler = DatabaseLogHandler(persist_batch=written.extend)
    handler.start()
    logger = _logger(handler, "flush")

    for i in range(250):
        logger.info("line %d", i)
    handler.stop()

    assert [e.message for e in written] == [f"line {i}" for i in range(250)]


def test_emit_does_not_wait_for_the_write() -> None:
    release = threading.Event()
    calls: list[int] = []

    def slow_persist(batch: list[LogEntry]) -> None:
        calls.append(len(batch))
        release.wait(5)

    handler = DatabaseLogHandler(persist_batch=slow_persist)
    handler.start()
    logger = _logger(handler, "nonblocking")

    logger.info("first")
    for _ in range(100):
        logger.info("more")  # would hang here if emit wrote synchronously
    release.set()
    handler.stop()

    assert sum(calls) == 101


def test_request_context_is_captured_on_the_emitting_thread() -> None:
    written: list[LogEntry] = []
    handler = DatabaseLogHandler(persist_batch=written.extend)
    handler.start()
    logger = _logger(handler, "context")

    token = request_id_var.set("req-123")
    try:
        logger.warning("inside a request")
    finally:
        request_id_var.reset(token)
    handler.stop()

    assert written[0].request_id == "req-123"
    assert written[0].level == "WARNING"


def test_full_queue_drops_the_oldest_entries() -> None:
    written: list[LogEntry] = []
    handler = DatabaseLogHandler(persist_batch=written.extend, max_queued=3)
    logger = _logger(handler, "bounded")

    for i in range(5):  # writer not started yet, so nothing drains
        logger.info("line %d", i)
    handler.start()
    handler.stop()

    assert [e.message for e in written] == ["line 2", "line 3", "line 4"]
    assert handler.dropped == 2


def test_skip_db_records_and_records_below_the_level_are_not_queued() -> None:
    written: list[LogEntry] = []
    handler = DatabaseLogHandler(persist_batch=written.extend)
    handler.setLevel(logging.INFO)
    handler.start()
    logger = _logger(handler, "filtered")

    logger.debug("too verbose")
    logger.info("stdout only", extra={"_skip_db": True})
    logger.info("kept")
    handler.stop()

    assert [e.message for e in written] == ["kept"]


def test_a_failing_write_is_swallowed_and_later_batches_still_go_through() -> None:
    written: list[LogEntry] = []
    failed = threading.Event()

    def flaky(batch: list[LogEntry]) -> None:
        if not failed.is_set():
            failed.set()
            raise RuntimeError("database down")
        written.extend(batch)

    handler = DatabaseLogHandler(persist_batch=flaky)
    handler.start()
    logger = _logger(handler, "flaky")

    logger.info("lost")
    failed.wait(5)
    logger.info("kept")
    handler.stop()

    assert [e.message for e in written] == ["kept"]
