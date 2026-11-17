"""
GET /ready: distinct from /health,
which never touches a dependency. These tests drive the real HTTP stack and
monkeypatch `check_database`/`check_redis` on the `readiness` module rather
than hitting a real Postgres/Redis. `readiness_report` looks those names up
on its own module's globals at call time (see readiness.py's docstring), so
patching them there is what the production code path actually consults.
"""

import pytest
from sqlalchemy import select

from src.modules.platform.adapters.inbound.api import readiness
from src.modules.platform.adapters.outbound.persistence.models.log_model import LogOrmModel
from src.modules.platform.adapters.outbound.persistence.statements import count_rows

# Kept before the autouse fixture below replaces it, for the one test that
# reads the real settings.
_real_check_backups = readiness.check_backups


async def _ok() -> None:
    return None


async def _boom() -> None:
    raise RuntimeError("dependency is down")


async def _no_backup_warnings() -> list[str]:
    return []


@pytest.fixture(autouse=True)
def _backups_fully_configured(monkeypatch):
    """The test database leaves backups at their defaults, which earn
    warnings; the tests below are about the dependency checks."""
    monkeypatch.setattr(readiness, "check_backups", _no_backup_warnings)


class TestReadyOk:
    @pytest.mark.smoke
    async def test_200_with_both_checks_ok(self, client, monkeypatch):
        monkeypatch.setattr(readiness, "check_database", _ok)
        monkeypatch.setattr(readiness, "check_redis", _ok)

        response = await client.get("/ready")

        assert response.status_code == 200
        assert response.json() == {
            "status": "ok",
            "checks": {"database": "ok", "redis": "ok"},
            "warnings": [],
        }

    async def test_needs_no_auth(self, client, monkeypatch):
        monkeypatch.setattr(readiness, "check_database", _ok)
        monkeypatch.setattr(readiness, "check_redis", _ok)

        response = await client.get("/ready")

        assert response.status_code == 200


class TestReadyFailure:
    async def test_503_with_redis_fail_when_redis_check_raises(self, client, monkeypatch):
        monkeypatch.setattr(readiness, "check_database", _ok)
        monkeypatch.setattr(readiness, "check_redis", _boom)

        response = await client.get("/ready")

        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "fail"
        assert body["checks"] == {"database": "ok", "redis": "fail"}

    async def test_database_fail_when_database_check_raises(self, client, monkeypatch):
        monkeypatch.setattr(readiness, "check_database", _boom)
        monkeypatch.setattr(readiness, "check_redis", _ok)

        response = await client.get("/ready")

        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "fail"
        assert body["checks"] == {"database": "fail", "redis": "ok"}

    async def test_both_failing_are_both_reported(self, client, monkeypatch):
        monkeypatch.setattr(readiness, "check_database", _boom)
        monkeypatch.setattr(readiness, "check_redis", _boom)

        response = await client.get("/ready")

        assert response.status_code == 503
        assert response.json() == {
            "status": "fail",
            "checks": {"database": "fail", "redis": "fail"},
            "warnings": [],
        }


class TestReadyBackupWarnings:
    async def test_backup_warnings_ride_along_without_failing_the_probe(self, client, monkeypatch):
        """Read for real from the test database, whose storage settings are
        the defaults: backups off, local provider, and no backup key."""
        monkeypatch.setattr(readiness, "check_database", _ok)
        monkeypatch.setattr(readiness, "check_redis", _ok)
        monkeypatch.setattr(readiness, "check_backups", _real_check_backups)

        response = await client.get("/ready")

        assert response.status_code == 200
        assert response.json()["warnings"] == [
            "disabled",
            "stored_on_host",
            "encryption_key_missing",
        ]

    async def test_unreadable_settings_give_no_warnings(self, client, monkeypatch):
        monkeypatch.setattr(readiness, "check_database", _ok)
        monkeypatch.setattr(readiness, "check_redis", _ok)

        async def _broken() -> list[str]:
            raise RuntimeError("database is down")

        monkeypatch.setattr(readiness, "check_backups", _broken)

        response = await client.get("/ready")

        assert response.status_code == 200
        assert response.json()["warnings"] == []


class TestReadyLeavesNoAuditTrail:
    """DatabaseLoggingMiddleware/RequestContextMiddleware both skip /ready
    (like /health), so a prober hitting this every 10-30s never fills
    log_table or the request-line log. A POST to a protected endpoint is the
    "normal request that does" comparison: unauthenticated so it needs no
    fixture setup, and its 401 still goes through both middleware layers
    (see logging_middleware.py's `is_write` check, method+path only, not
    outcome)."""

    async def test_no_log_table_row(self, client, db, monkeypatch):
        monkeypatch.setattr(readiness, "check_database", _ok)
        monkeypatch.setattr(readiness, "check_redis", _ok)

        await client.get("/ready")
        assert await count_rows(db, select(LogOrmModel)) == 0

        await client.post("/api/v1/web/customers/", json={})
        assert await count_rows(db, select(LogOrmModel)) == 1

    async def test_no_http_request_line_in_glados_caplog(self, client, glados_caplog, monkeypatch):
        monkeypatch.setattr(readiness, "check_database", _ok)
        monkeypatch.setattr(readiness, "check_redis", _ok)

        await client.get("/ready")
        assert not any("HTTP GET /ready" in r.message for r in glados_caplog.records)

        # /health is itself in _SKIP_LOG_PATHS, so it wouldn't prove
        # anything here; /openapi.json isn't in either skip list, so
        # its request line is the "normal request that does" baseline.
        glados_caplog.clear()
        await client.get("/openapi.json")
        assert any("HTTP GET /openapi.json" in r.message for r in glados_caplog.records)


class TestReadyIsHiddenFromTheOpenApiSchema:
    async def test_ready_has_no_schema_entry(self, auth_client):
        schema = (await (await auth_client()).get("/openapi.json")).json()

        assert "/ready" not in schema["paths"]
