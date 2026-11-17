"""
Backend half of the token lifetime cap admin setting (Settings polish
batch): `token_max_lifetime_days` on the `security` settings domain. The
cap actually being enforced on API-key/PAT creation is covered by
test_api_key_surface.py/test_api_pat_surface.py; this file only covers the
admin-facing PUT/GET contract and its bounds.

UpdateSecuritySettings is a full-replace command that never reads the
current row first, so PUT works even against a completely unseeded
`security` row; `_upsert` creates it.
"""

import pytest

from src.modules.platform.domain.value_objects.permission import Permission

BASE = "/api/v1/web/admin/settings/security"


@pytest.fixture
async def writer(auth_client):
    return await auth_client(permissions=[Permission.WRITE_SETTINGS, Permission.READ_SETTINGS])


class TestShippedDefault:
    async def test_a_bare_full_replace_lands_on_365_days(self, writer):
        response = await writer.put(BASE, json={})

        assert response.status_code == 200, response.text
        assert response.json()["token_max_lifetime_days"] == 365


class TestRoundTrip:
    async def test_a_configured_value_persists(self, writer):
        response = await writer.put(BASE, json={"token_max_lifetime_days": 30})

        assert response.status_code == 200, response.text
        assert response.json()["token_max_lifetime_days"] == 30

        get_response = await writer.get(BASE)
        assert get_response.status_code == 200
        assert get_response.json()["token_max_lifetime_days"] == 30


class TestBounds:
    async def test_zero_lifts_the_cap(self, writer):
        """0 is accepted and means no cap, so tokens may be created
        without an expiry again."""
        response = await writer.put(BASE, json={"token_max_lifetime_days": 0})

        assert response.status_code == 200, response.text
        assert response.json()["token_max_lifetime_days"] == 0

    async def test_a_negative_value_is_rejected_with_422(self, writer):
        response = await writer.put(BASE, json={"token_max_lifetime_days": -1})

        assert response.status_code == 422, response.text

    async def test_above_36500_is_rejected_with_422(self, writer):
        response = await writer.put(BASE, json={"token_max_lifetime_days": 36501})

        assert response.status_code == 422, response.text

    async def test_the_36500_boundary_is_accepted(self, writer):
        response = await writer.put(BASE, json={"token_max_lifetime_days": 36500})

        assert response.status_code == 200, response.text
        assert response.json()["token_max_lifetime_days"] == 36500
