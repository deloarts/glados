"""Whether the long-running background tasks of every worker still run.

The lifespan starts each worker's event consumers, schedulers, outbox relay
and live subscriber as asyncio tasks, and each of them supervises itself, so
a task that still ends is a defect that would otherwise only show in the log.
`mark_running` sets the `glados_background_task_up{task}` gauge to 1 when a
task starts, and `mark_stopped` sets it to 0 when the task ends with anything
but cancellation.

The gauge uses the `livemin` multiprocess mode, so a scrape reads the lowest
value across the live workers: a task that died in one worker reads 0 even
while the others still run it, and a worker that exits takes its values
along. `stopped_tasks` reads the same files, so `/ready` names a task that
died in any worker, not only in the one answering the probe. Without
PROMETHEUS_MULTIPROC_DIR (the development server) both read this process.
"""

import os
from collections.abc import Iterable
from pathlib import Path

from prometheus_client import Gauge
from prometheus_client.metrics_core import Metric
from prometheus_client.multiprocess import MultiProcessCollector

_METRIC = "glados_background_task_up"

BACKGROUND_TASK_UP = Gauge(
    _METRIC,
    "1 while a background task runs in every worker, 0 once it ended in any of them.",
    ["task"],
    multiprocess_mode="livemin",
)


def mark_running(task: str) -> None:
    BACKGROUND_TASK_UP.labels(task=task).set(1)


def mark_stopped(task: str) -> None:
    BACKGROUND_TASK_UP.labels(task=task).set(0)


def stopped_tasks() -> list[str]:
    """The names of the tasks that ended in any live worker, sorted. Reads
    files in multiprocess mode, so an async caller runs it in a thread."""
    directory = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    if directory:
        # Only this gauge uses the livemin mode, so its files are the only
        # ones worth reading.
        files = [str(path) for path in Path(directory).glob("gauge_livemin_*.db")]
        # merge ships without annotations, like mark_process_dead in
        # gunicorn_conf.py.
        metrics: Iterable[Metric] = MultiProcessCollector.merge(files, accumulate=True)  # type: ignore[no-untyped-call]
    else:
        metrics = BACKGROUND_TASK_UP.collect()
    stopped = {
        sample.labels["task"]
        for metric in metrics
        if metric.name == _METRIC
        for sample in metric.samples
        if sample.value == 0
    }
    return sorted(stopped)
