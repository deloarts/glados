"""
Unit coverage for GladosStateCollector and the glados_live_connections
gauge (src/read/adapters/inbound/api/metrics.py). No DB, no Redis, no HTTP: IMetricsSource is
faked (same style as FakeOutbox in test_outbox_relay.py: duck-typed, not
subclassed, IMetricsSource is a runtime_checkable Protocol).

Multiprocess-mode coverage (the harder half, since value storage is chosen at
prometheus_client import time from PROMETHEUS_MULTIPROC_DIR, so it can't be
toggled mid-session) lives in tests/unit/test_metrics_multiprocess.py
instead, in a subprocess.
"""

from prometheus_client import REGISTRY

from src.modules.external_data.domain.value_objects.pdm_file_sync_state import PdmFileSyncState
from src.modules.external_data.domain.value_objects.pdm_reconciliation_category import (
    PdmReconciliationCategory,
)
from src.modules.platform.adapters.inbound.api.live.hub import LiveHub
from src.modules.platform.const import VERSION
from src.read.adapters.inbound.api.metrics import GladosStateCollector


class FakeMetricsSource:
    """IMetricsSource. `raise_on` names the methods that raise instead of
    returning their configured value, so a test can pick exactly one
    failing metric per GladosStateCollector.collect() call."""

    def __init__(
        self,
        *,
        outbox: int = 0,
        stream_length: int = 0,
        pending: dict[str, int] | None = None,
        success_ts: float | None = None,
        failure_ts: float | None = None,
        pdm_success_ts: float | None = None,
        pdm_failure_ts: float | None = None,
        pdm_trigger_ts: float | None = None,
        pdm_last_run: dict[str, int] | None = None,
        pdm_files: dict[str, int] | None = None,
        pdm_findings: dict[str, int] | None = None,
        pdm_folders_cold: int = 0,
        raise_on: frozenset[str] = frozenset(),
    ) -> None:
        self._outbox = outbox
        self._stream_length = stream_length
        self._pending = pending if pending is not None else {}
        self._success_ts = success_ts
        self._failure_ts = failure_ts
        self._pdm_success_ts = pdm_success_ts
        self._pdm_failure_ts = pdm_failure_ts
        self._pdm_trigger_ts = pdm_trigger_ts
        self._pdm_last_run = pdm_last_run
        self._pdm_files = pdm_files if pdm_files is not None else {}
        self._pdm_findings = pdm_findings
        self._pdm_folders_cold = pdm_folders_cold
        self._raise_on = raise_on

    def _value_or_raise(self, name: str, value):
        if name in self._raise_on:
            raise RuntimeError(f"{name} is down")
        return value

    async def outbox_unpublished(self) -> int:
        return self._value_or_raise("outbox_unpublished", self._outbox)

    async def event_stream_length(self) -> int:
        return self._value_or_raise("event_stream_length", self._stream_length)

    async def event_stream_pending(self) -> dict[str, int]:
        return self._value_or_raise("event_stream_pending", self._pending)

    async def backup_last_success_ts(self) -> float | None:
        return self._value_or_raise("backup_last_success_ts", self._success_ts)

    async def backup_last_failure_ts(self) -> float | None:
        return self._value_or_raise("backup_last_failure_ts", self._failure_ts)

    async def pdm_last_poll_success_ts(self) -> float | None:
        return self._value_or_raise("pdm_last_poll_success_ts", self._pdm_success_ts)

    async def pdm_last_poll_failure_ts(self) -> float | None:
        return self._value_or_raise("pdm_last_poll_failure_ts", self._pdm_failure_ts)

    async def pdm_last_trigger_ts(self) -> float | None:
        return self._value_or_raise("pdm_last_trigger_ts", self._pdm_trigger_ts)

    async def pdm_last_run_counters(self) -> dict[str, int] | None:
        return self._value_or_raise("pdm_last_run_counters", self._pdm_last_run)

    async def pdm_files_by_sync_state(self) -> dict[str, int]:
        return self._value_or_raise("pdm_files_by_sync_state", self._pdm_files)

    async def pdm_reconciliation_findings_by_category(self) -> dict[str, int] | None:
        return self._value_or_raise("pdm_reconciliation_findings_by_category", self._pdm_findings)

    async def pdm_folders_cold(self) -> int:
        return self._value_or_raise("pdm_folders_cold", self._pdm_folders_cold)


async def _families(collector: GladosStateCollector) -> dict[str, object]:
    """Runs the scrape sequence GET /metrics performs: refresh() reads the
    async source, collect() then builds the families from those values."""
    await collector.refresh()
    return {family.name: family for family in collector.collect()}


async def test_glados_info_is_always_present():
    collector = GladosStateCollector(FakeMetricsSource())

    families = await _families(collector)

    # InfoMetricFamily("glados", ...) keeps the family's own .name as
    # "glados"; the "_info" suffix is added to the sample name only (see
    # prometheus_client.metrics_core.InfoMetricFamily.add_metric).
    info = families["glados"]
    sample = info.samples[0]
    assert sample.name == "glados_info"
    assert sample.labels == {"version": VERSION}
    assert sample.value == 1


async def test_all_metrics_present_when_the_source_never_raises():
    source = FakeMetricsSource(
        outbox=3,
        stream_length=7,
        pending={"notifications": 2},
        success_ts=1000.0,
        failure_ts=500.0,
    )
    collector = GladosStateCollector(source)

    families = await _families(collector)

    assert families["glados_outbox_unpublished_messages"].samples[0].value == 3
    assert families["glados_event_stream_length"].samples[0].value == 7
    pending_family = families["glados_event_stream_pending_messages"]
    assert pending_family.samples[0].labels == {"group": "notifications"}
    assert pending_family.samples[0].value == 2
    assert families["glados_backup_last_success_timestamp_seconds"].samples[0].value == 1000.0
    assert families["glados_backup_last_failure_timestamp_seconds"].samples[0].value == 500.0


class TestPdmFamilies:
    """PDM gauges (src/read/adapters/inbound/api/metrics.py's block after the
    backup gauges): last-poll success/failure/trigger timestamps, the
    newest run's per-counter tallies, snapshot counts by sync_state
    (zero-filled across PdmFileSyncState), reconciliation finding counts
    by category (zero-filled across PdmReconciliationCategory), and the
    cold-folder count."""

    async def test_all_pdm_families_present_with_expected_samples_and_labels(self):
        source = FakeMetricsSource(
            pdm_success_ts=111.0,
            pdm_failure_ts=222.0,
            pdm_trigger_ts=333.0,
            pdm_last_run={
                "files_seen": 10,
                "changed": 4,
                "ingested": 3,
                "skipped": 1,
                "conflicts": 0,
                "errors": 0,
                "missing": 0,
                "folders_walked": 2,
                "folders_skipped_cold": 1,
            },
            pdm_files={"pending": 5, "conflict": 1},
            pdm_findings={"stuck_file": 3},
            pdm_folders_cold=4,
        )
        collector = GladosStateCollector(source)

        families = await _families(collector)

        assert families["glados_pdm_last_poll_success_timestamp_seconds"].samples[0].value == 111.0
        assert families["glados_pdm_last_poll_failure_timestamp_seconds"].samples[0].value == 222.0
        assert families["glados_pdm_last_trigger_timestamp_seconds"].samples[0].value == 333.0

        last_run = families["glados_pdm_last_run"]
        by_counter = {s.labels["counter"]: s.value for s in last_run.samples}
        assert by_counter == {
            "files_seen": 10,
            "changed": 4,
            "ingested": 3,
            "skipped": 1,
            "conflicts": 0,
            "errors": 0,
            "missing": 0,
            "folders_walked": 2,
            "folders_skipped_cold": 1,
        }

        files = families["glados_pdm_files"]
        by_state = {s.labels["sync_state"]: s.value for s in files.samples}
        assert by_state == {state.value: 0 for state in PdmFileSyncState} | {
            "pending": 5,
            "conflict": 1,
        }

        findings = families["glados_pdm_reconciliation_findings"]
        by_category = {s.labels["category"]: s.value for s in findings.samples}
        assert by_category == {category.value: 0 for category in PdmReconciliationCategory} | {
            "stuck_file": 3
        }

        assert families["glados_pdm_folders_cold"].samples[0].value == 4

    async def test_none_returning_pdm_sources_omit_only_their_own_family(self):
        source = FakeMetricsSource(
            pdm_success_ts=None,
            pdm_failure_ts=None,
            pdm_trigger_ts=None,
            pdm_last_run=None,
            pdm_findings=None,
        )
        collector = GladosStateCollector(source)

        families = await _families(collector)

        assert "glados_pdm_last_poll_success_timestamp_seconds" not in families
        assert "glados_pdm_last_poll_failure_timestamp_seconds" not in families
        assert "glados_pdm_last_trigger_timestamp_seconds" not in families
        assert "glados_pdm_last_run" not in families
        assert "glados_pdm_reconciliation_findings" not in families
        # pdm_files_by_sync_state/pdm_folders_cold have no None branch:
        # still present, zero-filled/zero respectively.
        assert "glados_pdm_files" in families
        assert "glados_pdm_folders_cold" in families

    async def test_a_raising_pdm_source_omits_only_its_own_family(self):
        source = FakeMetricsSource(
            pdm_success_ts=111.0,
            pdm_failure_ts=222.0,
            raise_on=frozenset({"pdm_last_poll_success_ts"}),
        )
        collector = GladosStateCollector(source)

        families = await _families(collector)

        assert "glados_pdm_last_poll_success_timestamp_seconds" not in families
        assert families["glados_pdm_last_poll_failure_timestamp_seconds"].samples[0].value == 222.0

    async def test_zero_filled_enum_series_present_when_nothing_has_ever_happened(self):
        """No files ever snapshotted and no reconciliation run ever
        recorded: glados_pdm_files still emits every PdmFileSyncState
        value at 0 (files table is never "None"), while
        glados_pdm_reconciliation_findings is omitted entirely (a
        reconciliation run has never existed)."""
        source = FakeMetricsSource(pdm_files={}, pdm_findings=None)
        collector = GladosStateCollector(source)

        families = await _families(collector)

        files = families["glados_pdm_files"]
        assert {s.labels["sync_state"]: s.value for s in files.samples} == {
            state.value: 0 for state in PdmFileSyncState
        }
        assert "glados_pdm_reconciliation_findings" not in families


async def test_a_failing_source_method_is_skipped_but_the_rest_still_yield():
    source = FakeMetricsSource(outbox=3, raise_on=frozenset({"event_stream_length"}))
    collector = GladosStateCollector(source)

    families = await _families(collector)

    assert "glados_event_stream_length" not in families
    assert families["glados_outbox_unpublished_messages"].samples[0].value == 3
    assert "glados" in families  # glados_info, unrelated metric, unaffected


async def test_every_source_method_failing_still_yields_glados_info():
    source = FakeMetricsSource(
        raise_on=frozenset(
            {
                "outbox_unpublished",
                "event_stream_length",
                "event_stream_pending",
                "backup_last_success_ts",
                "backup_last_failure_ts",
                "pdm_last_poll_success_ts",
                "pdm_last_poll_failure_ts",
                "pdm_last_trigger_ts",
                "pdm_last_run_counters",
                "pdm_files_by_sync_state",
                "pdm_reconciliation_findings_by_category",
                "pdm_folders_cold",
            }
        )
    )
    collector = GladosStateCollector(source)

    families = await _families(collector)

    assert set(families) == {"glados"}  # glados_info only


async def test_backup_gauges_omitted_when_there_has_never_been_a_run():
    source = FakeMetricsSource(success_ts=None, failure_ts=None)
    collector = GladosStateCollector(source)

    families = await _families(collector)

    assert "glados_backup_last_success_timestamp_seconds" not in families
    assert "glados_backup_last_failure_timestamp_seconds" not in families


async def test_logs_at_debug_not_warning_when_a_source_method_fails(glados_caplog):
    import logging

    glados_caplog.set_level(logging.DEBUG, logger="glados")
    source = FakeMetricsSource(raise_on=frozenset({"event_stream_length"}))
    collector = GladosStateCollector(source)

    await collector.refresh()
    list(collector.collect())

    matching = [r for r in glados_caplog.records if "event_stream_length" in r.getMessage()]
    assert matching
    assert all(r.levelno == logging.DEBUG for r in matching)


class TestLiveConnectionsGauge:
    """glados_live_connections is a real Gauge (not part of
    GladosStateCollector), incremented/decremented directly by LiveHub;
    see hub.py's module docstring for why every removal path (normal
    disconnect, the _MAX_CONNECTIONS_PER_USER eviction branch, close_all)
    must decrement it exactly once.

    Process-wide state (the Gauge is a module singleton, default-registry
    backed here since PROMETHEUS_MULTIPROC_DIR is unset in this suite), so
    every assertion is relative to a captured baseline rather than an
    assumed 0, because other tests in the same session touch the same LiveHub
    connect()/disconnect() code paths.
    """

    @staticmethod
    def _current() -> float:
        value = REGISTRY.get_sample_value("glados_live_connections")
        assert value is not None
        return value

    def test_increments_on_connect_and_decrements_on_disconnect(self):
        hub = LiveHub()
        baseline = self._current()

        connection = hub.connect(user_id=1)
        assert self._current() == baseline + 1

        hub.disconnect(connection)
        assert self._current() == baseline

    def test_eviction_decrements_for_the_evicted_connection_too(self):
        """hub.py's connect() eviction branch removes the oldest connection
        without going through disconnect(), so the gauge must be
        decremented right there, not left to the evicted connection's own
        (no-op, by then) disconnect() call."""
        from src.modules.platform.adapters.inbound.api.live import hub as hub_module

        hub = LiveHub()
        baseline = self._current()

        for _ in range(hub_module._MAX_CONNECTIONS_PER_USER):
            hub.connect(user_id=1)
        assert self._current() == baseline + hub_module._MAX_CONNECTIONS_PER_USER

        hub.connect(user_id=1)  # evicts the oldest of the five above
        assert self._current() == baseline + hub_module._MAX_CONNECTIONS_PER_USER

    def test_close_all_decrements_for_every_open_connection(self):
        hub = LiveHub()
        baseline = self._current()

        hub.connect(user_id=1)
        hub.connect(user_id=2)
        assert self._current() == baseline + 2

        hub.close_all()
        assert self._current() == baseline
