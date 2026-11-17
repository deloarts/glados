"""
HTTP-level coverage for `POST /api/v1/web/admin/settings/storage/test`
(TestStorageConnection) and `POST /api/v1/web/admin/settings/storage/migrate`
(MigrateStorage).

The `local` provider ignores every AdminStorageSettings field except
`provider`/`enabled` (see create_storage_adapter in
src/modules/platform/adapters/outbound/external/storage/factory.py): it always builds a
LocalStorageAdapter rooted at cfg.local_storage.base_dir. That makes it the
only provider these tests can exercise without a real S3/Azure endpoint;
migrating local -> local still drives the exact same list_keys/download/
upload loop MigrateStorage runs for a real cross-provider migration, it
just happens to write the copy back into the same directory.

For "bad config" error mapping, an s3 or azure target with no
bucket_name is ideal: create_storage_adapter raises StorageMigrationError
(a DomainError, mapped to 400) before attempting any network I/O at all,
see that module's docstring and TestStorageConnection's own comment.
"""

from sqlalchemy import text

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.platform.domain.entities.admin_settings.storage import AdminStorageSettings
from src.modules.platform.domain.value_objects.permission import Permission

TEST_URL = "/api/v1/web/admin/settings/storage/test"
MIGRATE_URL = "/api/v1/web/admin/settings/storage/migrate"


def _local_body(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "provider": "local",
        "enabled": True,
        "endpoint_url": None,
        "public_endpoint_url": None,
        "bucket_name": None,
        "access_key": None,
        "secret_key": None,
        "region": None,
        "use_ssl": False,
        "backup_enabled": False,
        "backup_path": None,
        "backup_cron": None,
        "backup_retention_count": 7,
    }
    body.update(overrides)
    return body


async def _enable_local_storage(db, tmp_path, monkeypatch) -> None:
    from src.modules.platform.infrastructure.config.settings import cfg

    media = tmp_path / "media"
    media.mkdir()
    monkeypatch.setattr(cfg.local_storage, "base_dir", str(media))

    await db.execute(text("DELETE FROM admin_storage_settings"))
    await db.commit()
    await SqlAlchemyAdminSettingsRepository(db).save_storage(
        AdminStorageSettings(
            id=1,
            provider="local",
            enabled=True,
            endpoint_url=None,
            public_endpoint_url=None,
            bucket_name=None,
            access_key=None,
            secret_key=None,
            region=None,
            use_ssl=False,
            backup_enabled=False,
            backup_path=None,
            backup_cron=None,
            backup_retention_count=7,
        )
    )
    await db.commit()


class TestConnectionPermission:
    async def test_requires_write_settings(self, auth_client):
        client = await auth_client(permissions=[])

        response = await client.post(TEST_URL, json=_local_body())

        assert response.status_code == 403


class TestConnectionHappyPath:
    async def test_local_provider_succeeds(self, auth_client, db, tmp_path, monkeypatch):
        await _enable_local_storage(db, tmp_path, monkeypatch)
        client = await auth_client(permissions=[Permission.WRITE_SETTINGS])

        response = await client.post(TEST_URL, json=_local_body())

        assert response.status_code == 204


class TestConnectionErrorMapping:
    async def test_s3_without_bucket_name_maps_to_400(self, auth_client, db, tmp_path, monkeypatch):
        """create_storage_adapter raises StorageMigrationError before any
        network call is attempted, so this needs no real S3 endpoint."""
        await _enable_local_storage(db, tmp_path, monkeypatch)
        client = await auth_client(permissions=[Permission.WRITE_SETTINGS])

        response = await client.post(TEST_URL, json=_local_body(provider="s3", bucket_name=None))

        assert response.status_code == 400
        assert response.json()["code"] == "StorageMigrationError"


class TestMigratePermission:
    async def test_requires_write_settings(self, auth_client):
        client = await auth_client(permissions=[])

        response = await client.post(MIGRATE_URL, json=_local_body())

        assert response.status_code == 403


class TestMigrateHappyPath:
    async def test_local_to_local_copies_existing_objects_and_commits(
        self, auth_client, db, tmp_path, monkeypatch
    ):
        await _enable_local_storage(db, tmp_path, monkeypatch)

        (tmp_path / "media" / "avatars").mkdir()
        (tmp_path / "media" / "avatars" / "1.png").write_bytes(b"fake-png-bytes")
        (tmp_path / "media" / "docket.pdf").write_bytes(b"fake-pdf-bytes")
        client = await auth_client(permissions=[Permission.WRITE_SETTINGS])

        response = await client.post(MIGRATE_URL, json=_local_body(backup_enabled=True))

        assert response.status_code == 200
        body = response.json()
        assert body["migrated_count"] == 2
        assert body["failed_count"] == 0
        assert body["errors"] == []
        assert body["committed"] is True

        # The files are still there (copied onto themselves) and the new
        # settings (backup_enabled=True) were actually persisted.
        assert (tmp_path / "media" / "avatars" / "1.png").read_bytes() == b"fake-png-bytes"
        settings_row = await SqlAlchemyAdminSettingsRepository(db).get_storage()
        assert settings_row.backup_enabled is True

        rows = (
            await db.execute(text("SELECT settings_domain FROM admin_settings_audit"))
        ).fetchall()
        audit_domains = [row[0] for row in rows]
        assert "storage" in audit_domains


class TestMigrateErrorMapping:
    async def test_s3_without_bucket_name_maps_to_400_and_leaves_settings_untouched(
        self, auth_client, db, tmp_path, monkeypatch
    ):
        await _enable_local_storage(db, tmp_path, monkeypatch)
        client = await auth_client(permissions=[Permission.WRITE_SETTINGS])

        response = await client.post(MIGRATE_URL, json=_local_body(provider="s3", bucket_name=None))

        assert response.status_code == 400
        assert response.json()["code"] == "StorageMigrationError"
        # Nothing was committed: the provider on file is still local.
        assert (await SqlAlchemyAdminSettingsRepository(db).get_storage()).provider == "local"


class TestMigrateInvalidProvider:
    async def test_unknown_provider_string_should_be_a_client_error_not_a_500(
        self, auth_client, db, tmp_path, monkeypatch
    ):
        """BUG (src/modules/platform/application/use_cases/admin_settings/migrate_storage.py,
        `_VALID_PROVIDERS` check): `UpdateStorageSettingsRequest.provider` is
        a bare `str` with no enum/Literal validation at the schema layer, so
        an unrecognised provider string reaches MigrateStorage.execute() and
        hits `raise ValueError(...)` there. ValueError is not a DomainError,
        so exception_handlers.py has no mapping for it and
        UnhandledExceptionMiddleware turns it into a generic 500
        ("Internal server error" / code "InternalError") instead of a 400
        naming the actual problem. This test asserts the correct client-error
        behaviour and is expected to fail until that use case raises (or the
        schema validates) a proper DomainError instead.
        """
        await _enable_local_storage(db, tmp_path, monkeypatch)
        client = await auth_client(permissions=[Permission.WRITE_SETTINGS])

        response = await client.post(MIGRATE_URL, json=_local_body(provider="totally-bogus"))

        assert response.status_code == 400
