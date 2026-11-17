"""
Proves that the admin settings writes without a round-trip test elsewhere
persist what they report: the feature, maintenance, retention, order and
branding saves, and uploading and removing the branding logo, favicon,
login video and company logo. Each write is read back through a separate request, the
settings themselves where the response shows them and the audit log in
every case, so a use case that forgets to commit its unit of work fails
here instead of silently losing the change.
"""

from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy import text

from src.bootstrap.adapters.outbound.persistence.admin_settings_seed import ADMIN_SETTINGS_SEEDS
from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.platform.domain.entities.admin_settings.storage import AdminStorageSettings
from src.modules.platform.domain.value_objects.permission import Permission

BASE = "/api/v1/web/admin/settings"


@pytest.fixture(autouse=True)
async def _seed_every_domain(db) -> None:
    """Seeds every settings row the conftest baseline leaves out, the way
    InitDatabase does on first start."""
    repo = SqlAlchemyAdminSettingsRepository(db)
    for seed in ADMIN_SETTINGS_SEEDS:
        if await db.scalar(select(seed.model).filter_by(id=1).limit(1)) is None:
            await seed.save(repo)(seed.build())
    await db.commit()


@pytest.fixture
async def settings_admin(auth_client) -> Any:
    return await auth_client(permissions=[Permission.READ_SETTINGS, Permission.WRITE_SETTINGS])


async def _latest_audit(client: Any) -> tuple[str, str]:
    response = await client.get(f"{BASE}/audit")
    assert response.status_code == 200, response.text
    newest = response.json()["items"][0]
    return newest["settings_domain"], newest["summary"]


async def _get(client: Any, path: str) -> dict[str, Any]:
    response = await client.get(f"{BASE}/{path}")
    assert response.status_code == 200, response.text
    return dict(response.json())


async def test_feature_settings_are_persisted(settings_admin) -> None:
    saved = await settings_admin.put(f"{BASE}/features", json={"enable_email_notifications": False})
    assert saved.status_code == 200, saved.text
    assert (await _get(settings_admin, "features"))["enable_email_notifications"] is False
    assert (await _latest_audit(settings_admin))[0] == "features"


async def test_maintenance_settings_are_persisted(settings_admin) -> None:
    saved = await settings_admin.put(
        f"{BASE}/maintenance", json={"enabled": False, "message": "Back at noon"}
    )
    assert saved.status_code == 200, saved.text
    assert (await _get(settings_admin, "maintenance"))["message"] == "Back at noon"
    assert (await _latest_audit(settings_admin))[0] == "maintenance"


async def test_retention_settings_are_persisted(settings_admin) -> None:
    saved = await settings_admin.put(f"{BASE}/retention", json={"log_retention_days": 30})
    assert saved.status_code == 200, saved.text
    assert (await _get(settings_admin, "retention"))["log_retention_days"] == 30
    assert (await _latest_audit(settings_admin))[0] == "retention"


async def test_order_settings_are_persisted(settings_admin) -> None:
    saved = await settings_admin.put(f"{BASE}/orders", json={"part_number_editable": True})
    assert saved.status_code == 200, saved.text
    assert (await _get(settings_admin, "orders"))["part_number_editable"] is True
    assert (await _latest_audit(settings_admin))[0] == "orders"


async def test_branding_settings_are_persisted(settings_admin) -> None:
    saved = await settings_admin.put(f"{BASE}/branding", json={"app_name": "Shopfloor"})
    assert saved.status_code == 200, saved.text
    assert (await _get(settings_admin, "branding"))["app_name"] == "Shopfloor"
    assert (await _latest_audit(settings_admin))[0] == "branding"


@pytest.mark.parametrize(
    "path",
    ["branding/logo", "branding/favicon", "branding/login-video", "general/company-logo"],
)
async def test_removing_a_branding_asset_is_persisted(settings_admin, path: str) -> None:
    removed = await settings_admin.delete(f"{BASE}/{path}")
    assert removed.status_code == 200, removed.text
    assert "removed" in (await _latest_audit(settings_admin))[1]


@pytest.fixture
async def storage(db, tmp_path, monkeypatch):
    """Enables the local storage provider, rooted in a temp dir."""
    from src.modules.platform.infrastructure.config.settings import cfg

    monkeypatch.setattr(cfg.local_storage, "base_dir", str(tmp_path))
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
            backup_path="backups",
            backup_cron=None,
            backup_retention_count=3,
        )
    )
    await db.commit()
    return tmp_path


_PNG = b"\x89PNG\r\n\x1a\n" + b"rest-of-the-file"
_MP4 = b"\x00\x00\x00\x18ftypmp42" + b"rest-of-the-file"


@pytest.mark.parametrize(
    ("path", "data", "mime", "read_path", "flag"),
    [
        ("branding/logo", _PNG, "image/png", "branding", "has_logo"),
        ("branding/favicon", _PNG, "image/png", "branding", "has_favicon"),
        ("branding/login-video", _MP4, "video/mp4", "branding", "has_login_background_video"),
        ("general/company-logo", _PNG, "image/png", "general", "has_company_logo"),
    ],
)
async def test_uploading_a_branding_asset_is_persisted(
    settings_admin, storage, path: str, data: bytes, mime: str, read_path: str, flag: str
) -> None:
    uploaded = await settings_admin.post(f"{BASE}/{path}", files={"file": ("asset", data, mime)})
    assert uploaded.status_code == 200, uploaded.text
    assert (await _get(settings_admin, read_path))[flag] is True
    assert "uploaded" in (await _latest_audit(settings_admin))[1]
