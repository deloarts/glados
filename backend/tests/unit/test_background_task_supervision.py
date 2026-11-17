"""
Unit tests for the lifespan background-task done-callback, the
`glados_background_task_up` gauge it sets and the `/ready` warning built on it.

Only the helper is imported, never create_app / lifespan: the point of the
callback is that it can be reasoned about (and asserted on) in isolation,
without a running app, a Redis client or a DB.
"""

import asyncio
import contextlib
import logging
import os
import subprocess
import sys

import pytest

from src.bootstrap.main import _log_task_completion
from src.modules.platform.adapters.inbound.api import readiness
from src.modules.platform.infrastructure.background_tasks import BACKGROUND_TASK_UP
from src.modules.platform.infrastructure.background_tasks import mark_running
from src.modules.platform.infrastructure.background_tasks import stopped_tasks


def _glados_records(caplog) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == "glados"]


def _gauge(task: str) -> float:
    return BACKGROUND_TASK_UP.labels(task=task)._value.get()


async def _run_supervised(coro, *, name: str = "task-under-test") -> asyncio.Task:
    task = asyncio.create_task(coro, name=name)
    task.add_done_callback(_log_task_completion)
    with contextlib.suppress(BaseException):
        await task
    await asyncio.sleep(0)  # let the done-callback run
    return task


async def test_done_callback_logs_a_crashed_task(glados_caplog):
    async def crashes() -> None:
        raise RuntimeError("worker exploded")

    await _run_supervised(crashes(), name="event-worker:webhooks")

    (record,) = _glados_records(glados_caplog)
    assert record.levelno == logging.CRITICAL
    assert "event-worker:webhooks" in record.getMessage()
    assert record.exc_info is not None  # traceback carried, not just the message


async def test_done_callback_is_silent_for_a_cancelled_task(glados_caplog):
    async def forever() -> None:
        await asyncio.Event().wait()

    task = asyncio.create_task(forever(), name="live-subscriber")
    task.add_done_callback(_log_task_completion)
    await asyncio.sleep(0)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.sleep(0)

    assert _glados_records(glados_caplog) == []  # cancellation is normal shutdown


async def test_done_callback_reports_a_task_that_returned(glados_caplog):
    """Every supervised task runs forever, so a clean return is a death too."""

    async def returns() -> None:
        return None

    await _run_supervised(returns(), name="notification-digest")

    (record,) = _glados_records(glados_caplog)
    assert record.levelno == logging.CRITICAL
    assert "notification-digest" in record.getMessage()
    assert "notification-digest" in stopped_tasks()


async def test_a_crashed_task_reads_zero_and_a_cancelled_one_stays_up():
    async def crashes() -> None:
        raise RuntimeError("worker exploded")

    async def forever() -> None:
        await asyncio.Event().wait()

    mark_running("event-worker:crashes")
    mark_running("event-worker:cancelled")
    await _run_supervised(crashes(), name="event-worker:crashes")
    task = asyncio.create_task(forever(), name="event-worker:cancelled")
    task.add_done_callback(_log_task_completion)
    await asyncio.sleep(0)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    await asyncio.sleep(0)

    assert _gauge("event-worker:crashes") == 0
    assert _gauge("event-worker:cancelled") == 1
    assert "event-worker:crashes" in stopped_tasks()
    assert "event-worker:cancelled" not in stopped_tasks()


async def test_ready_warns_about_each_stopped_task(monkeypatch):
    monkeypatch.setattr(readiness, "stopped_tasks", lambda: ["outbox-relay", "schedule-tick"])

    assert await readiness.background_task_warnings_report() == [
        "background_task_stopped:outbox-relay",
        "background_task_stopped:schedule-tick",
    ]


async def test_ready_has_no_task_warning_when_the_states_cannot_be_read(monkeypatch):
    def broken() -> list[str]:
        raise OSError("metrics directory is gone")

    monkeypatch.setattr(readiness, "stopped_tasks", broken)

    assert await readiness.background_task_warnings_report() == []


async def test_done_callback_never_raises_into_the_event_loop(monkeypatch, glados_caplog):
    """log.critical also writes to log_table via DatabaseLogHandler in a
    running app; a failing DB round-trip there must not escape the callback
    into the event loop's exception handler."""
    import src.bootstrap.main as main_module

    def exploding_critical(*args, **kwargs):
        raise RuntimeError("log sink is down")

    monkeypatch.setattr(main_module.log, "critical", exploding_critical)

    async def crashes() -> None:
        raise RuntimeError("worker exploded")

    task = await _run_supervised(crashes())  # no raise

    # The task still carries its own crash, not the callback's failure.
    assert isinstance(task.exception(), RuntimeError)
    assert str(task.exception()) == "worker exploded"


def test_stopped_tasks_reads_every_worker_in_multiprocess_mode(tmp_path):
    """A task stopped in one worker counts as stopped although another
    worker still runs it. Each worker is a separate interpreter, since
    prometheus_client picks multiprocess storage at import time."""
    environment = {**os.environ, "PROMETHEUS_MULTIPROC_DIR": str(tmp_path)}
    module = "src.modules.platform.infrastructure.background_tasks"

    def run(code: str) -> str:
        return subprocess.run(
            [sys.executable, "-c", f"from {module} import *\n{code}"],
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    run("mark_running('outbox-relay')\nmark_running('schedule-tick')")
    run("mark_running('outbox-relay')\nmark_stopped('schedule-tick')")

    assert run("print(','.join(stopped_tasks()))") == "schedule-tick"
