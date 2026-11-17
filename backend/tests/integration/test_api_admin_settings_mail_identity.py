"""
Backend half of the mail identity + rate limit fields (Settings polish
batch): `from_display_name`/`reply_to`/`send_limit_per_hour`/
`send_lock_minutes` on the `mail` settings domain. `UpdateMailSettingsCommand`
is a full-replace command like every other field in this domain (unlike
`general`'s partial update), so every PUT below repeats the required
`enabled`/`host`/`port`/`user` fields.

`_seed_admin_settings` (conftest.py, autouse) does not seed the `mail`
domain at all. UpdateMailSettings.execute reads `self._repo.get_mail()`
first (to decide whether to keep the existing password), which raises if
unseeded, so every test here seeds a baseline row itself first, the same
pattern as test_api_admin_settings_mail_test.py's own `_seed_mail`.
"""

import pytest

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.platform.domain.entities.admin_settings.mail import AdminMailSettings
from src.modules.platform.domain.value_objects.permission import Permission

BASE = "/api/v1/web/admin/settings/mail"

REQUIRED = {"enabled": True, "host": "smtp.example.com", "port": 587, "user": "noreply"}


@pytest.fixture(autouse=True)
async def _seed_mail(db) -> None:
    await SqlAlchemyAdminSettingsRepository(db).save_mail(
        AdminMailSettings(
            id=1,
            enabled=False,
            host="",
            port=587,
            user="",
            password=None,
            from_address=None,
            use_tls=True,
            use_ssl=False,
            verify_certificate=True,
            from_display_name="",
            reply_to=None,
            send_limit_per_hour=20,
            send_lock_minutes=60,
            alert_recipients=[],
        )
    )
    await db.commit()


@pytest.fixture
async def writer(auth_client):
    return await auth_client(permissions=[Permission.WRITE_SETTINGS, Permission.READ_SETTINGS])


class TestShippedDefaults:
    async def test_a_bare_full_replace_lands_on_the_shipped_defaults(self, writer):
        """No display name, no Reply-To, 20 sends/hour with a 60-minute
        lock."""
        response = await writer.put(BASE, json=REQUIRED)

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["from_display_name"] == ""
        assert body["reply_to"] is None
        assert body["send_limit_per_hour"] == 20
        assert body["send_lock_minutes"] == 60


class TestIdentityRoundTrip:
    async def test_from_display_name_and_reply_to_persist(self, writer):
        response = await writer.put(
            BASE,
            json={
                **REQUIRED,
                "from_display_name": "Glados",
                "reply_to": "support@example.com",
            },
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["from_display_name"] == "Glados"
        assert body["reply_to"] == "support@example.com"

        get_response = await writer.get(BASE)
        assert get_response.status_code == 200
        assert get_response.json()["from_display_name"] == "Glados"
        assert get_response.json()["reply_to"] == "support@example.com"


class TestRateLimitRoundTrip:
    async def test_send_limit_and_lock_minutes_persist(self, writer):
        response = await writer.put(
            BASE, json={**REQUIRED, "send_limit_per_hour": 5, "send_lock_minutes": 15}
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["send_limit_per_hour"] == 5
        assert body["send_lock_minutes"] == 15

    async def test_send_limit_per_hour_rejects_zero_with_422(self, writer):
        response = await writer.put(BASE, json={**REQUIRED, "send_limit_per_hour": 0})

        assert response.status_code == 422, response.text

    async def test_send_lock_minutes_rejects_zero_with_422(self, writer):
        response = await writer.put(BASE, json={**REQUIRED, "send_lock_minutes": 0})

        assert response.status_code == 422, response.text
