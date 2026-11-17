"""
Path traversal tests for the storage-restore endpoint.

`snapshot_key` arrives straight from the request body and is used as a
storage prefix for both reads and writes. Without containment in
LocalStorageAdapter, this would let a `write:settings` admin copy
arbitrary host files, including `.env`, i.e. the JWT signing key, into a
served directory, turning a settings admin into "can forge a token for
any user".

Both defences are exercised here: the use-case level prefix validation
(which also protects S3/Azure, where keys are opaque and the adapter's
path check does not apply) and the end-to-end rejection.
"""

import pytest
from sqlalchemy import text

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.platform.domain.entities.admin_settings.storage import AdminStorageSettings
from src.modules.platform.domain.value_objects.permission import Permission

BACKUP_PATH = "backups"
SNAPSHOT = f"{BACKUP_PATH}/files/2026-01-01T00-00-00"


@pytest.fixture
async def storage(db, tmp_path, monkeypatch):
    """Enable the local storage provider, rooted in a temp dir, with a
    sibling directory standing in for the application root."""
    from src.modules.platform.infrastructure.config.settings import cfg

    media = tmp_path / "media"
    media.mkdir()
    app_root = tmp_path / "app_root"
    app_root.mkdir()
    (app_root / ".env.prod").write_text("SECURITY__SECRET_KEY_PERSISTENT=SUPER-SECRET\n")

    monkeypatch.setattr(cfg.local_storage, "base_dir", str(media))

    # Persist through the repository rather than raw SQL, so the fixture
    # doesn't have to track schema additions (e.g. the NOT NULL public_id).
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
            # True (not just backup_path set) so DownloadBackup's "backups
            # configured" check passes for the backup-download tests below;
            # RestoreFiles itself never reads backup_enabled.
            backup_enabled=True,
            backup_path=BACKUP_PATH,
            backup_cron=None,
            backup_retention_count=3,
        )
    )
    await db.commit()
    return media, app_root


@pytest.fixture
async def admin(auth_client):
    return await auth_client(permissions=[Permission.WRITE_SETTINGS, Permission.READ_SETTINGS])


async def _restore(client, key):
    return await client.post(
        "/api/v1/web/admin/settings/storage/backups/files/restore",
        json={"snapshot_key": key},
    )


# ── Traversal out of the storage root ─────────────────────────────────


class TestTraversalIsRejected:
    async def test_the_original_exploit_no_longer_works(self, admin, storage):
        """A key that climbs out of the storage root is a 400 and copies
        nothing."""
        media, _ = storage

        response = await _restore(admin, "../app_root")

        assert response.status_code == 400
        assert not (media / ".env.prod").exists()

    async def test_nothing_is_exfiltrated_into_the_public_media_dir(self, admin, storage):
        media, _ = storage

        await _restore(admin, "../app_root")

        assert list(media.iterdir()) == []

    @pytest.mark.parametrize(
        "key",
        ["..", "../app_root", f"{BACKUP_PATH}/files/../../../app_root", "/etc"],
        ids=["bare-parent", "parent-traversal", "nested-traversal", "absolute"],
    )
    async def test_escape_attempts_are_rejected(self, admin, storage, key):
        assert (await _restore(admin, key)).status_code == 400

    async def test_rejection_is_a_4xx_not_a_500(self, admin, storage):
        """A rejected key is a bad request, not a server error, an
        unregistered domain exception would surface as 500."""
        assert (await _restore(admin, "../app_root")).status_code < 500


# ── Prefix confinement (provider-agnostic) ────────────────────────────


class TestSnapshotKeyMustNameASnapshot:
    async def test_a_key_outside_the_snapshot_area_is_rejected(self, admin, storage):
        assert (await _restore(admin, "users/avatars")).status_code == 400

    async def test_the_snapshot_area_itself_is_rejected(self, admin, storage):
        """Restoring the whole area would merge every snapshot at once."""
        assert (await _restore(admin, f"{BACKUP_PATH}/files")).status_code == 400

    async def test_the_db_backup_area_is_rejected(self, admin, storage):
        assert (await _restore(admin, f"{BACKUP_PATH}/db")).status_code == 400

    async def test_an_empty_key_is_rejected(self, admin, storage):
        assert (await _restore(admin, "")).status_code == 400


# ── The happy path ────────────────────────────────────────────────────


class TestValidSnapshotRestores:
    async def test_a_real_snapshot_is_restored_to_its_original_keys(self, admin, storage):
        media, _ = storage
        snap = media / BACKUP_PATH / "files" / "2026-01-01T00-00-00" / "users" / "avatars"
        snap.mkdir(parents=True)
        (snap / "1.png").write_bytes(b"avatar-bytes")

        response = await _restore(admin, SNAPSHOT)

        assert response.status_code == 200
        assert response.json()["restored_count"] == 1
        assert (media / "users" / "avatars" / "1.png").read_bytes() == b"avatar-bytes"

    async def test_an_empty_snapshot_restores_nothing_without_erroring(self, admin, storage):
        media, _ = storage
        (media / BACKUP_PATH / "files" / "2026-01-01T00-00-00").mkdir(parents=True)

        response = await _restore(admin, SNAPSHOT)

        assert response.status_code == 200
        assert response.json()["restored_count"] == 0


# ── Authorisation ─────────────────────────────────────────────────────


class TestAuthorisation:
    async def test_requires_write_settings(self, auth_client, storage):
        client = await auth_client(permissions=[Permission.READ_SETTINGS])

        assert (await _restore(client, SNAPSHOT)).status_code == 403

    async def test_requires_authentication(self, client, storage):
        assert (await _restore(client, SNAPSHOT)).status_code == 401


# ── Backup download ──────────────────────────────────────────────────


class TestBackupDownload:
    async def test_admin_downloads_a_db_archive(self, admin, storage):
        media, _ = storage
        db_dir = media / BACKUP_PATH / "db"
        db_dir.mkdir(parents=True)
        (db_dir / "2026-01-01T00-00-00.sql.gz").write_bytes(b"gzip-bytes")

        response = await admin.get(
            "/api/v1/web/admin/settings/storage/backups/download",
            params={"key": f"{BACKUP_PATH}/db/2026-01-01T00-00-00.sql.gz"},
        )

        assert response.status_code == 200
        assert response.content == b"gzip-bytes"
        assert response.headers["x-content-type-options"] == "nosniff"

    @pytest.mark.parametrize("key", ["users/avatars/1.jpg", "../.env"])
    async def test_a_key_outside_the_backup_prefix_is_rejected(self, admin, storage, key):
        response = await admin.get(
            "/api/v1/web/admin/settings/storage/backups/download", params={"key": key}
        )
        assert response.status_code == 400

    async def test_requires_write_settings(self, auth_client, storage):
        client = await auth_client(permissions=[Permission.READ_SETTINGS])

        response = await client.get(
            "/api/v1/web/admin/settings/storage/backups/download",
            params={"key": f"{BACKUP_PATH}/db/2026-01-01T00-00-00.sql.gz"},
        )
        assert response.status_code == 403

    async def test_requires_authentication(self, client, storage):
        response = await client.get(
            "/api/v1/web/admin/settings/storage/backups/download",
            params={"key": f"{BACKUP_PATH}/db/2026-01-01T00-00-00.sql.gz"},
        )
        assert response.status_code == 401
