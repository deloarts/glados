"""
Backend half of the "Locales" feature (default_language/default_timezone/
default_date_format on the `general` settings domain). Covers the two
behaviours a plain field addition would not exercise on its own:

  - each of the three is validated at the wire boundary with a proper 422,
    not a bare exception falling through to an unhandled 500 (timezone via
    UpdateGeneralSettingsRequest.validate_default_timezone, language/
    date_format via being closed Enum types Pydantic itself rejects);
  - the shipped baseline equals the SERVER_DEFAULT_* constants in
    src/modules/platform/const.py, proving the migration's server_default (not some other
    hard-coded value) is what an unconfigured tenant sees.

`_seed_admin_settings` (conftest.py, autouse) seeds admin_general_settings
via the raw ORM model without these three columns, relying on their
server_default, so the baseline for every test here is
default_language="enGB", default_timezone="Europe/Vienna",
default_date_format="iso" (see src/modules/platform/const.py's SERVER_DEFAULT_*).
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
    async def test_baseline_equals_the_server_default_constants(self, writer):
        """conftest seeds the row without these columns at all, so this is
        purely the server_default path from the migration, mirroring
        src/modules/platform/const.py's SERVER_DEFAULT_LANGUAGE/TIMEZONE/DATE_FORMAT."""
        response = await writer.get(BASE)

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["default_language"] == "enGB"
        assert body["default_timezone"] == "Europe/Vienna"
        assert body["default_date_format"] == "iso"


class TestDefaultTimezoneValidation:
    async def test_an_invalid_iana_name_is_rejected_with_422_not_500(self, writer):
        response = await writer.put(BASE, json={"default_timezone": "Mars/Olympus"})

        assert response.status_code == 422, response.text
        body = response.json()
        assert "detail" in body

    async def test_a_valid_iana_name_is_accepted_and_persisted(self, writer):
        response = await writer.put(BASE, json={"default_timezone": "Europe/London"})
        assert response.status_code == 200, response.text
        assert response.json()["default_timezone"] == "Europe/London"

        # Persisted, not just echoed back: a fresh GET agrees.
        get_response = await writer.get(BASE)
        assert get_response.status_code == 200
        assert get_response.json()["default_timezone"] == "Europe/London"


class TestDefaultLanguageValidation:
    async def test_an_unknown_language_code_is_rejected_with_422(self, writer):
        response = await writer.put(BASE, json={"default_language": "frFR"})

        assert response.status_code == 422, response.text

    async def test_a_known_language_code_is_accepted_and_persisted(self, writer):
        response = await writer.put(BASE, json={"default_language": "deAT"})
        assert response.status_code == 200, response.text
        assert response.json()["default_language"] == "deAT"

        get_response = await writer.get(BASE)
        assert get_response.status_code == 200
        assert get_response.json()["default_language"] == "deAT"


class TestDefaultDateFormatValidation:
    async def test_an_unknown_preset_is_rejected_with_422(self, writer):
        response = await writer.put(BASE, json={"default_date_format": "not-a-format"})

        assert response.status_code == 422, response.text

    async def test_a_known_preset_is_accepted_and_persisted(self, writer):
        response = await writer.put(BASE, json={"default_date_format": "dmy_dot"})
        assert response.status_code == 200, response.text
        assert response.json()["default_date_format"] == "dmy_dot"

        get_response = await writer.get(BASE)
        assert get_response.status_code == 200
        assert get_response.json()["default_date_format"] == "dmy_dot"


class TestPartialUpdate:
    async def test_omitting_a_field_leaves_a_previously_set_value_untouched(self, writer):
        """The partial-update contract, same as every other field in this
        domain: only an explicit value changes it, omitting it entirely
        (None on the wire) must not."""
        await writer.put(BASE, json={"default_timezone": "Europe/London"})

        response = await writer.put(BASE, json={"default_language": "deAT"})

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["default_language"] == "deAT"
        assert body["default_timezone"] == "Europe/London"

    async def test_all_three_can_be_set_together(self, writer):
        response = await writer.put(
            BASE,
            json={
                "default_language": "deAT",
                "default_timezone": "Europe/London",
                "default_date_format": "dmy_dot",
            },
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["default_language"] == "deAT"
        assert body["default_timezone"] == "Europe/London"
        assert body["default_date_format"] == "dmy_dot"
