"""GET /metrics: the HTTP metrics of http_metrics.py plus
GladosStateCollector, which turns IMetricsSource into gauges on every scrape.
The collector reads the state of several modules, so it sits in the read
tier; the HTTP middleware and the live connection gauge are Platform's.

prometheus_client picks multiprocess storage at import time from
PROMETHEUS_MULTIPROC_DIR, so the variable must be set before Python starts.
With it, each scrape aggregates every worker's files in a fresh registry;
without it, the default registry is used.
"""

import os
from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Iterator
from typing import TypeVar
from typing import cast

from fastapi import Response
from prometheus_client import CONTENT_TYPE_LATEST
from prometheus_client import REGISTRY
from prometheus_client import CollectorRegistry
from prometheus_client import generate_latest
from prometheus_client.core import GaugeMetricFamily
from prometheus_client.core import InfoMetricFamily
from prometheus_client.core import Metric
from prometheus_client.multiprocess import MultiProcessCollector

from src.modules.external_data.domain.value_objects.pdm_file_sync_state import PdmFileSyncState
from src.modules.external_data.domain.value_objects.pdm_reconciliation_category import (
    PdmReconciliationCategory,
)
from src.modules.platform.const import VERSION
from src.modules.platform.infrastructure.logging.logger import log
from src.read.adapters.outbound.persistence.metrics_source import SqlAlchemyRedisMetricsSource
from src.read.ports.outbound.metrics_source_port import IMetricsSource

_T = TypeVar("_T")


class GladosStateCollector:
    """Turns one IMetricsSource read into this scrape's gauges. The async
    read happens in refresh(), because collect() is sync.

    Each source call fails on its own and leaves only its metric out.
    Failures log at DEBUG, because /ready already reports the dependencies
    and a scrape cadence would flood the log.
    """

    def __init__(self, source: IMetricsSource) -> None:
        self._source = source
        self._values: dict[str, object] = {}

    async def refresh(self) -> None:
        """Reads every source value for the next collect()."""
        calls: list[tuple[str, Callable[[], Awaitable[object]]]] = [
            ("outbox_unpublished", self._source.outbox_unpublished),
            ("event_stream_length", self._source.event_stream_length),
            ("backup_last_success_ts", self._source.backup_last_success_ts),
            ("backup_last_failure_ts", self._source.backup_last_failure_ts),
            ("pdm_last_poll_success_ts", self._source.pdm_last_poll_success_ts),
            ("pdm_last_poll_failure_ts", self._source.pdm_last_poll_failure_ts),
            ("pdm_last_trigger_ts", self._source.pdm_last_trigger_ts),
            ("pdm_folders_cold", self._source.pdm_folders_cold),
            ("event_stream_pending", self._source.event_stream_pending),
            ("pdm_last_run_counters", self._source.pdm_last_run_counters),
            ("pdm_files_by_sync_state", self._source.pdm_files_by_sync_state),
            (
                "pdm_reconciliation_findings_by_category",
                self._source.pdm_reconciliation_findings_by_category,
            ),
        ]
        values: dict[str, object] = {}
        for name, call in calls:
            value = await self._try(name, call)
            if value is not None:
                values[name] = value
        self._values = values

    def collect(self) -> Iterator[Metric]:
        yield from self._collect_simple_gauges()
        yield from self._collect_labeled_gauges()
        yield self._build_info_metric()

    def _simple(self, name: str) -> float | None:
        value = self._values.get(name)
        return value if isinstance(value, int | float) else None

    def _mapping(self, name: str) -> dict[str, int] | None:
        value = self._values.get(name)
        return cast("dict[str, int]", value) if isinstance(value, dict) else None

    def _collect_simple_gauges(self) -> Iterator[Metric]:
        """The unlabeled gauges, skipping failed reads."""
        specs: list[tuple[str, str, str]] = [
            (
                "outbox_unpublished",
                "glados_outbox_unpublished_messages",
                "Rows in the transactional outbox not yet relayed to the events stream.",
            ),
            (
                "event_stream_length",
                "glados_event_stream_length",
                "XLEN of the glados:events Redis stream.",
            ),
            (
                "backup_last_success_ts",
                "glados_backup_last_success_timestamp_seconds",
                "Unix timestamp of the most recent successful backup run.",
            ),
            (
                "backup_last_failure_ts",
                "glados_backup_last_failure_timestamp_seconds",
                "Unix timestamp of the most recent failed backup run.",
            ),
            (
                "pdm_last_poll_success_ts",
                "glados_pdm_last_poll_success_timestamp_seconds",
                "Unix timestamp of finished_at for the newest scheduled PDM poll "
                "that finished without an error.",
            ),
            (
                "pdm_last_poll_failure_ts",
                "glados_pdm_last_poll_failure_timestamp_seconds",
                "Unix timestamp of finished_at for the newest scheduled PDM poll "
                "that finished with an error.",
            ),
            (
                "pdm_last_trigger_ts",
                "glados_pdm_last_trigger_timestamp_seconds",
                "Unix timestamp of started_at for the newest add-in change-notification "
                "sync, the add-in-is-alive signal.",
            ),
            (
                "pdm_folders_cold",
                "glados_pdm_folders_cold",
                "pdm_folder_poll_state rows whose next_due_at is still in the future.",
            ),
        ]
        for name, metric_name, help_text in specs:
            value = self._simple(name)
            if value is None:
                continue
            family = GaugeMetricFamily(metric_name, help_text)
            family.add_metric([], value)
            yield family

    def _collect_labeled_gauges(self) -> Iterator[Metric]:
        """The labeled gauges."""
        yield from self._collect_pending_gauge()
        yield from self._collect_pdm_last_run_gauge()
        yield from self._collect_pdm_files_gauge()
        yield from self._collect_pdm_findings_gauge()

    def _collect_pending_gauge(self) -> Iterator[Metric]:
        pending = self._mapping("event_stream_pending")
        if pending is None:
            return
        family = GaugeMetricFamily(
            "glados_event_stream_pending_messages",
            "XPENDING count per consumer group on the glados:events stream.",
            labels=["group"],
        )
        for group, count in pending.items():
            family.add_metric([group], count)
        yield family

    def _collect_pdm_last_run_gauge(self) -> Iterator[Metric]:
        pdm_last_run = self._mapping("pdm_last_run_counters")
        if pdm_last_run is None:
            return
        family = GaugeMetricFamily(
            "glados_pdm_last_run",
            "Per-counter tallies of the newest finished PDM sync run, any trigger.",
            labels=["counter"],
        )
        for counter, value in pdm_last_run.items():
            family.add_metric([counter], value)
        yield family

    def _collect_pdm_files_gauge(self) -> Iterator[Metric]:
        pdm_files = self._mapping("pdm_files_by_sync_state")
        if pdm_files is None:
            return
        family = GaugeMetricFamily(
            "glados_pdm_files",
            "pdm_file_snapshot rows grouped by sync_state, zero-filled across every "
            "PdmFileSyncState value so an alert on one state never misses a series.",
            labels=["sync_state"],
        )
        for state in PdmFileSyncState:
            family.add_metric([state.value], pdm_files.get(state.value, 0))
        yield family

    def _collect_pdm_findings_gauge(self) -> Iterator[Metric]:
        pdm_findings = self._mapping("pdm_reconciliation_findings_by_category")
        if pdm_findings is None:
            return
        family = GaugeMetricFamily(
            "glados_pdm_reconciliation_findings",
            "Finding counts per category of the newest PDM reconciliation run, "
            "zero-filled across every PdmReconciliationCategory value.",
            labels=["category"],
        )
        for category in PdmReconciliationCategory:
            family.add_metric([category.value], pdm_findings.get(category.value, 0))
        yield family

    @staticmethod
    def _build_info_metric() -> Metric:
        info = InfoMetricFamily("glados", "Static build info.")
        info.add_metric([], {"version": VERSION})
        return info

    @staticmethod
    async def _try(name: str, call: Callable[[], Awaitable[_T]]) -> _T | None:
        try:
            return await call()
        except Exception:
            log.debug("GladosStateCollector: %s failed; skipping.", name, exc_info=True)
            return None


_default_collector: GladosStateCollector | None = None


def _register_default_collector() -> GladosStateCollector:
    """Registers the collector on the default registry exactly once, since
    a second registration raises.
    """
    global _default_collector
    if _default_collector is None:
        _default_collector = GladosStateCollector(SqlAlchemyRedisMetricsSource())
        REGISTRY.register(_default_collector)
    return _default_collector


async def refresh_metrics() -> CollectorRegistry:
    """Refreshes the collector and returns the registry to render."""
    multiproc_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    if multiproc_dir:
        registry = CollectorRegistry()
        # __init__ is untyped upstream despite the package being py.typed
        # (see multiprocess.py); it self-registers on `registry`, which is
        # why this call's result is discarded.
        MultiProcessCollector(registry)  # type: ignore[no-untyped-call]
        collector = GladosStateCollector(SqlAlchemyRedisMetricsSource())
        await collector.refresh()
        registry.register(collector)
        return registry
    await _register_default_collector().refresh()
    return REGISTRY


async def metrics_response() -> Response:
    """Renders the current Prometheus exposition text for GET /metrics
    (main.py) after refreshing the state gauges."""
    registry = await refresh_metrics()
    return Response(content=generate_latest(registry), media_type=CONTENT_TYPE_LATEST)
