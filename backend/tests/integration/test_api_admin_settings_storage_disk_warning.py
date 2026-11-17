"""
Backend half of the disk_warning_percent field
on the Storage settings domain: the shipped baseline (90, matching
InitDatabase/the migration's server_default), a PUT round trip, and the
0-100 wire-boundary validation.

conftest.py's autouse `_seed_admin_settings` seeds admin_storage_settings
via the raw ORM model without this column, relying on its server_default
("90"), so the baseline for every test here is disk_warning_percent=90,
same pattern as test_api_admin_settings_locales.py.
"""

import pytest

from src.modules.platform.domain.value_objects.permission import Permission

BASE = "/api/v1/web/admin/settings/storage"


@pytest.fixture
async def writer(auth_client):
    # READ_SETTINGS too: one test re-GETs after a PUT to prove persistence,
    # not just an echo of the request body.
    return await auth_client(permissions=[Permission.WRITE_SETTINGS, Permission.READ_SETTINGS])


class TestShippedBaseline:
    async def test_baseline_is_90(self, writer):
        response = await writer.get(BASE)

        assert response.status_code == 200, response.text
        assert response.json()["disk_warning_percent"] == 90


class TestRoundTrip:
    async def test_a_new_value_is_accepted_and_persisted(self, writer):
        response = await writer.put(
            BASE, json={"provider": "local", "enabled": False, "disk_warning_percent": 75}
        )

        assert response.status_code == 200, response.text
        assert response.json()["disk_warning_percent"] == 75

        get_response = await writer.get(BASE)
        assert get_response.status_code == 200
        assert get_response.json()["disk_warning_percent"] == 75

    async def test_zero_disables_and_is_accepted(self, writer):
        response = await writer.put(
            BASE, json={"provider": "local", "enabled": False, "disk_warning_percent": 0}
        )

        assert response.status_code == 200, response.text
        assert response.json()["disk_warning_percent"] == 0


class TestValidation:
    async def test_above_100_is_rejected_with_422(self, writer):
        response = await writer.put(
            BASE, json={"provider": "local", "enabled": False, "disk_warning_percent": 101}
        )

        assert response.status_code == 422, response.text

    async def test_below_0_is_rejected_with_422(self, writer):
        response = await writer.put(
            BASE, json={"provider": "local", "enabled": False, "disk_warning_percent": -1}
        )

        assert response.status_code == 422, response.text

    async def test_omitting_the_field_falls_back_to_the_command_default_of_90(self, writer):
        """UpdateStorageSettingsCommand is a full replace, not a partial
        update (unlike e.g. UpdateGeneralSettingsCommand). Omitting the
        field lands on its own default of 90, it does not preserve a
        previously-saved value."""
        await writer.put(
            BASE, json={"provider": "local", "enabled": False, "disk_warning_percent": 5}
        )

        response = await writer.put(BASE, json={"provider": "local", "enabled": False})

        assert response.status_code == 200, response.text
        assert response.json()["disk_warning_percent"] == 90
