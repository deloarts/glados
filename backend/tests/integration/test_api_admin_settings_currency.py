"""
Backend half of the "Currency" feature (Settings polish batch): `currency`
on the `general` settings domain. Presentation only: prices remain plain
integer cents regardless, see AdminGeneralSettings.currency. Covers the one
behaviour a plain field addition would not exercise on its own: the ISO
4217 alphabetic-code shape is validated at the wire boundary with a proper
422, not a bare exception falling through to an unhandled 500 (see
UpdateGeneralSettingsRequest.validate_currency).

`_seed_admin_settings` (conftest.py, autouse) seeds admin_general_settings
via the raw ORM model without this column, relying on its server_default,
so the baseline for every test here is currency="EUR" (see
src/modules/platform/const.py's SERVER_DEFAULT_CURRENCY).
"""

import pytest

from src.modules.platform.domain.value_objects.permission import Permission

BASE = "/api/v1/web/admin/settings/general"


@pytest.fixture
async def writer(auth_client):
    # READ_SETTINGS too: one test re-GETs after a PUT to prove persistence,
    # not just an echo of the request body.
    return await auth_client(permissions=[Permission.WRITE_SETTINGS, Permission.READ_SETTINGS])


class TestShippedBaseline:
    async def test_baseline_equals_the_server_default_constant(self, writer):
        """conftest seeds the row without this column at all, so this is
        purely the server_default path from the migration, mirroring
        src/modules/platform/const.py's SERVER_DEFAULT_CURRENCY."""
        response = await writer.get(BASE)

        assert response.status_code == 200, response.text
        assert response.json()["currency"] == "EUR"


class TestCurrencyValidation:
    async def test_a_lowercase_code_is_rejected_with_422_not_500(self, writer):
        response = await writer.put(BASE, json={"currency": "eur"})

        assert response.status_code == 422, response.text
        assert "detail" in response.json()

    async def test_a_four_letter_code_is_rejected_with_422(self, writer):
        response = await writer.put(BASE, json={"currency": "EURO"})

        assert response.status_code == 422, response.text

    async def test_a_valid_code_is_accepted_and_persisted(self, writer):
        response = await writer.put(BASE, json={"currency": "USD"})
        assert response.status_code == 200, response.text
        assert response.json()["currency"] == "USD"

        # Persisted, not just echoed back: a fresh GET agrees.
        get_response = await writer.get(BASE)
        assert get_response.status_code == 200
        assert get_response.json()["currency"] == "USD"


class TestPartialUpdate:
    async def test_omitting_the_field_leaves_a_previously_set_value_untouched(self, writer):
        """The partial-update contract, same as every other field in this
        domain: only an explicit value changes it, omitting it entirely
        (None on the wire) must not."""
        await writer.put(BASE, json={"currency": "GBP"})

        response = await writer.put(BASE, json={"empty_value_placeholder": "n/a"})

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["currency"] == "GBP"
        assert body["empty_value_placeholder"] == "n/a"
