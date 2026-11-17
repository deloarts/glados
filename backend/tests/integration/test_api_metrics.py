"""
GET /metrics: prometheus-fastapi-instrumentator's HTTP metrics plus
GladosStateCollector's app-state gauges, driven through the real HTTP
stack the same way test_api_readiness.py drives /ready.

Content-type note: prometheus_client's classic `text/plain; version=0.0.4`
exposition format is not the default: prometheus-client 0.26.0's
CONTENT_TYPE_LATEST points at the newer `text/plain; version=1.0.0` text
format instead (see
prometheus_client/exposition.py); metrics.py deliberately uses
CONTENT_TYPE_LATEST (not a hardcoded version) so this stays correct across
future prometheus-client upgrades, and the assertions below check the
`text/plain` prefix rather than an exact version pin for the same reason.
"""

import time
from datetime import UTC
from datetime import datetime
from datetime import timedelta

from prometheus_client.parser import text_string_to_metric_families
from sqlalchemy import select

from src.modules.external_data.adapters.outbound.persistence.models.pdm_file_snapshot_model import (
    PdmFileSnapshotOrmModel,
)
from src.modules.external_data.adapters.outbound.persistence.models.pdm_folder_poll_state_model import (
    PdmFolderPollStateOrmModel,
)
from src.modules.external_data.adapters.outbound.persistence.models.pdm_sync_run_model import (
    PdmSyncRunOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.event_outbox_model import (
    EventOutboxOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.log_model import LogOrmModel
from src.modules.platform.adapters.outbound.persistence.statements import count_rows
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.infrastructure.config.settings import cfg
from src.modules.platform.infrastructure.redis_client import new_probe_redis_client
from src.read.adapters.outbound.persistence import metrics_source


def _families(body: str) -> dict[str, object]:
    return {f.name: f for f in text_string_to_metric_families(body)}


class TestMetricsBasics:
    async def test_200_with_prometheus_content_type(self, client):
        response = await client.get("/metrics")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")

    async def test_needs_no_auth(self, client):
        response = await client.get("/metrics")

        assert response.status_code == 200

    async def test_hidden_from_the_openapi_schema(self, auth_client):
        schema = (await (await auth_client()).get("/openapi.json")).json()

        assert "/metrics" not in schema["paths"]

    async def test_scraping_twice_does_not_raise(self, client):
        """Regression coverage for GladosStateCollector's default-registry
        registration guard (metrics.py's _register_default_collector): a
        second REGISTRY.register() with the same metric names raises
        'Duplicated timeseries in CollectorRegistry' without it."""
        first = await client.get("/metrics")
        second = await client.get("/metrics")

        assert first.status_code == 200
        assert second.status_code == 200
        assert "glados_info" in first.text
        assert "glados_info" in second.text


class TestHttpRequestsTotal:
    async def test_uses_the_route_template_and_exact_status(self, create_user, auth_client):
        target = await create_user(username="metrics-target", email="metrics-target@example.com")
        actor = await auth_client(permissions=[Permission.READ_SETTINGS])

        response = await actor.get(f"/api/v1/web/users/{target.id}")
        assert response.status_code == 200

        body = (await actor.get("/metrics")).text
        # text_string_to_metric_families keys a Counter family by its name
        # with the "_total" suffix stripped (verified in .venv, the same
        # round-trip behaviour as InfoMetricFamily's "glados" vs
        # "glados_info", see test_metrics_collector.py); the samples
        # underneath keep the full "http_requests_total" name.
        total = _families(body)["http_requests"]

        matching = [
            s
            for s in total.samples
            if s.name == "http_requests_total"
            and s.labels.get("handler") == "/api/v1/web/users/{user_id}"
            and s.labels.get("status") == "200"
        ]
        assert matching, [s.labels for s in total.samples if s.name == "http_requests_total"]

    async def test_health_ready_and_metrics_are_excluded(self, client):
        # A non-excluded request first, run in isolation or not, so the
        # http_requests_total family is guaranteed to exist below: an
        # all-excluded run would leave the Counter unlabelled and absent
        # from the scrape entirely (generate_latest skips zero-sample
        # families), which would make this test vacuously pass rather
        # than actually exercise the exclusion.
        await client.get("/openapi.json")
        await client.get("/health")
        await client.get("/ready")
        await client.get("/metrics")  # a scrape of itself must not instrument itself

        body = (await client.get("/metrics")).text
        # "http_requests" (not "http_requests_total"), see the family-vs-
        # sample name note in test_uses_the_route_template_and_exact_status
        # above.
        total = _families(body)["http_requests"]

        excluded_handlers = {"/health", "/ready", "/metrics"}
        offending = [s for s in total.samples if s.labels.get("handler") in excluded_handlers]
        assert offending == []


class TestOutboxGauge:
    async def test_equals_the_number_of_unpublished_rows(self, client, db):
        for i in range(3):
            db.add(
                EventOutboxOrmModel(
                    event_id=f"evt-metrics-test-{i}",
                    event_type="ProjectCreated",
                    payload="{}",
                    created=datetime.now(UTC),
                )
            )
        # One published row must NOT count.
        db.add(
            EventOutboxOrmModel(
                event_id="evt-metrics-test-published",
                event_type="ProjectCreated",
                payload="{}",
                created=datetime.now(UTC),
                published_at=datetime.now(UTC),
            )
        )
        await db.commit()

        body = (await client.get("/metrics")).text
        family = _families(body)["glados_outbox_unpublished_messages"]

        assert family.samples[0].value == 3


class TestRedisDependentGaugesFailOpen:
    async def test_absent_not_erroring_when_redis_is_unreachable(self, client, monkeypatch):
        """The production probe client (see metrics_source.py's module
        docstring for why this isn't get_async_redis_client()) pointed at an
        unroutable address. GladosStateCollector must still answer 200 within
        a few seconds, just without the Redis-backed gauges."""
        # TEST-NET-1 (RFC 5737): reserved, never routed.
        monkeypatch.setattr(cfg.redis, "url", "redis://192.0.2.1:6379/0")
        unroutable = new_probe_redis_client()
        monkeypatch.setattr(metrics_source, "_get_metrics_redis_client", lambda: unroutable)

        started = time.perf_counter()
        response = await client.get("/metrics")
        elapsed = time.perf_counter() - started

        assert response.status_code == 200
        assert elapsed < 5, f"scrape took {elapsed:.1f}s, should be bounded by the 1s timeouts"

        families = _families(response.text)
        assert "glados_event_stream_length" not in families
        assert "glados_event_stream_pending_messages" not in families
        # Unaffected: DB-backed, not Redis-backed.
        assert "glados_outbox_unpublished_messages" in families
        assert "glados_info" in families


class TestPdmGauges:
    """The PDM block of GladosStateCollector (src/adapters/inbound/api/
    metrics.py, after the backup gauges): last-poll success/failure
    timestamps, the add-in-alive trigger timestamp, the newest run's
    per-counter tallies, file counts by sync_state (zero-filled across
    every PdmFileSyncState value), and the cold-folder count."""

    async def test_pdm_metrics_reflect_seeded_rows(self, client, db):
        scheduled_started = datetime(2026, 9, 22, 11, 50, tzinfo=UTC)
        scheduled_finished = datetime(2026, 9, 22, 11, 51, tzinfo=UTC)
        db.add(
            PdmSyncRunOrmModel(
                started_at=scheduled_started,
                finished_at=scheduled_finished,
                trigger="scheduled",
                files_seen=5,
                changed=2,
                ingested=2,
                skipped=0,
                conflicts=0,
                errors=0,
                missing=0,
                error=None,
                summary="5 files seen, 2 changed",
                folders_walked=3,
                folders_skipped_cold=1,
            )
        )

        # Newer than the scheduled run above, so this is both "the newest
        # file_trigger run" and "the newest finished run of any trigger":
        # glados_pdm_last_run below must reflect THIS run's own counters.
        trigger_started = datetime(2026, 9, 22, 11, 55, tzinfo=UTC)
        trigger_finished = datetime(2026, 9, 22, 11, 56, tzinfo=UTC)
        db.add(
            PdmSyncRunOrmModel(
                started_at=trigger_started,
                finished_at=trigger_finished,
                trigger="file_trigger",
                files_seen=1,
                changed=1,
                ingested=1,
                skipped=0,
                conflicts=0,
                errors=0,
                missing=0,
                error=None,
                summary="1 file seen, 1 changed",
                folders_walked=0,
                folders_skipped_cold=0,
            )
        )

        db.add(
            PdmFileSnapshotOrmModel(
                vault_id="V1",
                file_id=1,
                kind="made",
                name="Bracket.SLDPRT",
                path="\\Made-Parts\\Bracket.SLDPRT",
                parent_folder_id=10,
                version=1,
                state_id=1,
                state="Released",
                first_seen_at=scheduled_started,
                last_seen_at=scheduled_finished,
                sync_state="ingested",
            )
        )
        db.add(
            PdmFileSnapshotOrmModel(
                vault_id="V1",
                file_id=2,
                kind="made",
                name="Bracket2.SLDPRT",
                path="\\Made-Parts\\Bracket2.SLDPRT",
                parent_folder_id=10,
                version=1,
                state_id=1,
                state="Released",
                first_seen_at=scheduled_started,
                last_seen_at=scheduled_finished,
                sync_state="conflict",
            )
        )

        # next_due_at relative to wall-clock "now", not a fixed date, since
        # glados_pdm_folders_cold compares against datetime.now(UTC).
        db.add(
            PdmFolderPollStateOrmModel(
                vault_id="V1",
                folder_key="10",
                consecutive_unchanged_runs=3,
                next_due_at=datetime.now(UTC) + timedelta(hours=1),
                last_changed_at=None,
                updated_at=scheduled_finished,
            )
        )
        await db.commit()

        body = (await client.get("/metrics")).text
        families = _families(body)

        success = families["glados_pdm_last_poll_success_timestamp_seconds"]
        assert success.samples[0].value == scheduled_finished.timestamp()

        trigger = families["glados_pdm_last_trigger_timestamp_seconds"]
        assert trigger.samples[0].value == trigger_started.timestamp()

        # No scheduled run recorded an error.
        assert "glados_pdm_last_poll_failure_timestamp_seconds" not in families

        last_run = families["glados_pdm_last_run"]
        by_counter = {s.labels["counter"]: s.value for s in last_run.samples}
        assert by_counter["files_seen"] == 1
        assert by_counter["changed"] == 1
        assert by_counter["ingested"] == 1

        files = families["glados_pdm_files"]
        by_state = {s.labels["sync_state"]: s.value for s in files.samples}
        assert by_state["ingested"] == 1
        assert by_state["conflict"] == 1
        assert by_state["pending"] == 0  # zero-filled, no row in this state

        assert families["glados_pdm_folders_cold"].samples[0].value == 1

        # No reconciliation run was ever recorded.
        assert "glados_pdm_reconciliation_findings" not in families


class TestMetricsLeavesNoAuditTrail:
    """Same story as /ready's own TestReadyLeavesNoAuditTrail
    (test_api_readiness.py): both skip lists (logging_middleware.py's
    _SKIP_PATHS, request_context_middleware.py's _SKIP_LOG_PATHS) must
    carry "/metrics" too, or every scrape (every few seconds, in prod)
    would fill log_table and the request-line log with noise."""

    async def test_no_log_table_row(self, client, db):
        await client.get("/metrics")
        assert await count_rows(db, select(LogOrmModel)) == 0

        await client.post("/api/v1/web/customers/", json={})
        assert await count_rows(db, select(LogOrmModel)) == 1

    async def test_no_http_request_line_in_glados_caplog(self, client, glados_caplog):
        await client.get("/metrics")
        assert not any("HTTP GET /metrics" in r.message for r in glados_caplog.records)

        glados_caplog.clear()
        await client.get("/openapi.json")
        assert any("HTTP GET /openapi.json" in r.message for r in glados_caplog.records)
