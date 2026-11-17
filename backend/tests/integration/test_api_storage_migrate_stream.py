"""
HTTP-level coverage for `POST /api/v1/web/admin/settings/storage/migrate/stream`
and `GET /api/v1/web/admin/settings/storage/migrate/status`: progress frames
per object, the terminal result or error frame, the app-wide mutex and the
status a reloaded page reads.

Like test_api_storage_migrate.py, the migrations here go local -> local,
which drives the same list/download/upload loop as a real cross-provider
migration without any S3 endpoint. Redis is swapped for the run registry's
in-memory fake, as in test_api_auto_plan_stream.py.
"""

import json

import pytest

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.infrastructure import storage_migration_run_registry as registry
from src.modules.platform.infrastructure.run_registry import update_snapshot
from tests.integration.test_api_auto_plan_stream import _parse_sse_frames
from tests.integration.test_api_storage_migrate import _enable_local_storage
from tests.integration.test_api_storage_migrate import _local_body
from tests.unit.test_autoplan_run_registry import FakeRedis

BASE = "/api/v1/web/admin/settings/storage/migrate"
STREAM = f"{BASE}/stream"
STATUS = f"{BASE}/status"


@pytest.fixture
def fake_redis(monkeypatch) -> FakeRedis:
    fake = FakeRedis()
    monkeypatch.setattr(registry, "get_async_redis_client", lambda: fake)
    return fake


@pytest.fixture
async def owner(create_user) -> User:
    return await create_user(username="migration-owner", email="migration-owner@example.com")


async def test_storage_migrate_stream_requires_write_settings(fake_redis, auth_client) -> None:
    client = await auth_client(permissions=[Permission.READ_SETTINGS])

    resp = await client.post(STREAM, json=_local_body())

    assert resp.status_code == 403
    assert not resp.headers.get("content-type", "").startswith("text/event-stream")
    assert await registry.read() is None


async def test_storage_migrate_stream_reports_each_object_then_the_result(
    fake_redis, auth_client, db, tmp_path, monkeypatch
) -> None:
    await _enable_local_storage(db, tmp_path, monkeypatch)
    (tmp_path / "media" / "avatars").mkdir()
    (tmp_path / "media" / "avatars" / "1.png").write_bytes(b"fake-png-bytes")
    (tmp_path / "media" / "docket.pdf").write_bytes(b"fake-pdf-bytes")
    client = await auth_client(permissions=[Permission.WRITE_SETTINGS])

    resp = await client.post(STREAM, json=_local_body(backup_enabled=True))

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    frames = _parse_sse_frames(resp.text)
    progress = [json.loads(data) for event, data in frames if event == "progress"]
    assert [(p["current"], p["total"]) for p in progress] == [(1, 2), (2, 2)]
    assert {p["key"] for p in progress} == {"avatars/1.png", "docket.pdf"}

    assert [event for event, _ in frames if event in ("result", "error")] == ["result"]
    result = json.loads(next(data for event, data in frames if event == "result"))
    assert result == {"migrated_count": 2, "failed_count": 0, "errors": [], "committed": True}
    db.expire_all()
    assert (await SqlAlchemyAdminSettingsRepository(db).get_storage()).backup_enabled is True


async def test_storage_migrate_stream_releases_the_mutex_when_done(
    fake_redis, auth_client, db, tmp_path, monkeypatch
) -> None:
    await _enable_local_storage(db, tmp_path, monkeypatch)
    client = await auth_client(permissions=[Permission.READ_SETTINGS, Permission.WRITE_SETTINGS])

    first = await client.post(STREAM, json=_local_body())
    assert [event for event, _ in _parse_sse_frames(first.text)] == ["result"]

    assert (await client.get(STATUS)).json() == {"running": False, "run": None}
    second = await client.post(STREAM, json=_local_body())
    assert second.status_code == 200


async def test_storage_migrate_stream_reports_a_bad_target_as_an_error_frame(
    fake_redis, auth_client, db, tmp_path, monkeypatch
) -> None:
    await _enable_local_storage(db, tmp_path, monkeypatch)
    client = await auth_client(permissions=[Permission.WRITE_SETTINGS])

    resp = await client.post(STREAM, json=_local_body(provider="seaweedfs", bucket_name=None))

    frames = _parse_sse_frames(resp.text)
    assert [event for event, _ in frames] == ["error"]
    assert "bucket_name is required" in json.loads(frames[0][1])["detail"]
    db.expire_all()
    assert (await SqlAlchemyAdminSettingsRepository(db).get_storage()).provider == "local"
    assert await registry.read() is None


async def test_storage_migrate_stream_returns_409_while_another_migration_runs(
    fake_redis, auth_client, owner: User
) -> None:
    handle = await registry.try_acquire(user_id=owner.id, user_name=owner.full_name)
    assert handle is not None
    client = await auth_client(permissions=[Permission.WRITE_SETTINGS])

    resp = await client.post(STREAM, json=_local_body())

    assert resp.status_code == 409
    assert resp.json()["code"] == "StorageMigrationInProgressError"


async def test_storage_migration_status_reports_the_running_migration(
    fake_redis, auth_client, owner: User
) -> None:
    handle = await registry.try_acquire(user_id=owner.id, user_name=owner.full_name)
    assert handle is not None
    update_snapshot(handle, "copying", 12, 458, "documents/42/preview.png")
    await registry.heartbeat_once(handle)
    client = await auth_client(permissions=[Permission.READ_SETTINGS])

    body = (await client.get(STATUS)).json()

    assert body["running"] is True
    assert body["run"]["user_name"] == owner.full_name
    assert body["run"]["current"] == 12
    assert body["run"]["total"] == 458
    assert body["run"]["detail"] == "documents/42/preview.png"


async def test_storage_migration_status_requires_read_settings(fake_redis, auth_client) -> None:
    client = await auth_client(permissions=[])

    resp = await client.get(STATUS)

    assert resp.status_code == 403
