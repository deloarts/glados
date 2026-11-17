"""
Backend half of the webhook delivery timeout field (Settings polish
batch): `webhook_timeout_seconds` on the `notifications` settings domain.
Read per-dispatch by DispatchEventToWebhooks (see
test_webhook_use_cases.py's unit coverage for that wiring); this file only
covers the admin-facing PUT/GET contract and its bounds.

UpdateNotificationSettings is a full-replace command that never reads the
current row first (unlike `mail`), so PUT works even against a completely
unseeded `notifications` row; `_upsert` creates it.
"""

import pytest

from src.modules.platform.domain.value_objects.permission import Permission

BASE = "/api/v1/web/admin/settings/notifications"


@pytest.fixture
async def writer(auth_client):
    return await auth_client(permissions=[Permission.WRITE_SETTINGS, Permission.READ_SETTINGS])


class TestShippedDefault:
    async def test_a_bare_full_replace_lands_on_10_seconds(self, writer):
        response = await writer.put(BASE, json={})

        assert response.status_code == 200, response.text
        assert response.json()["webhook_timeout_seconds"] == 10


class TestRoundTrip:
    async def test_a_configured_value_persists(self, writer):
        response = await writer.put(BASE, json={"webhook_timeout_seconds": 30})

        assert response.status_code == 200, response.text
        assert response.json()["webhook_timeout_seconds"] == 30

        get_response = await writer.get(BASE)
        assert get_response.status_code == 200
        assert get_response.json()["webhook_timeout_seconds"] == 30


class TestBounds:
    async def test_zero_is_rejected_with_422(self, writer):
        response = await writer.put(BASE, json={"webhook_timeout_seconds": 0})

        assert response.status_code == 422, response.text

    async def test_above_120_is_rejected_with_422(self, writer):
        response = await writer.put(BASE, json={"webhook_timeout_seconds": 121})

        assert response.status_code == 422, response.text

    async def test_the_120_boundary_is_accepted(self, writer):
        response = await writer.put(BASE, json={"webhook_timeout_seconds": 120})

        assert response.status_code == 200, response.text
        assert response.json()["webhook_timeout_seconds"] == 120
