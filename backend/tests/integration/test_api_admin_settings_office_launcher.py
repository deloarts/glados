"""
Backend half of the "Office Waffle" feature (office_launcher_enabled /
office_sharepoint_url on the `general` settings domain). Covers the two
behaviours a plain field addition would not exercise on its own:

  - the SharePoint URL's scheme is rejected with a proper 422, not a bare
    ValueError falling through to an unhandled 500 (exception_handlers.py
    only registers a handler for DomainError, see
    UpdateGeneralSettingsRequest.validate_office_sharepoint_url_scheme);
  - the field is a non-nullable `""`-sentinel column specifically so an
    admin can clear it back to "" (hide the SharePoint tile) without the
    frontend's `None`-means-"leave as-is" partial-update semantics making
    that impossible.

`_seed_admin_settings` (conftest.py, autouse) seeds admin_general_settings
via the raw ORM model without either new column, relying on their
server_default ("false" / ""), so the baseline for every test here is
office_launcher_enabled=False, office_sharepoint_url="".
"""

import pytest

from src.modules.platform.domain.value_objects.permission import Permission

BASE = "/api/v1/web/admin/settings/general"


@pytest.fixture
async def writer(auth_client):
    # READ_SETTINGS too: one test re-GETs after a PUT to prove persistence,
    # not just an echo of the request body.
    return await auth_client(permissions=[Permission.WRITE_SETTINGS, Permission.READ_SETTINGS])


class TestSharePointUrlSchemeValidation:
    async def test_a_non_http_scheme_is_rejected_with_422_not_500(self, writer):
        response = await writer.put(BASE, json={"office_sharepoint_url": "javascript:alert(1)"})

        assert response.status_code == 422, response.text
        body = response.json()
        assert "detail" in body

    async def test_a_valid_https_url_is_accepted_and_persisted(self, writer):
        url = "https://contoso.sharepoint.com/sites/intranet"

        response = await writer.put(BASE, json={"office_sharepoint_url": url})
        assert response.status_code == 200, response.text
        assert response.json()["office_sharepoint_url"] == url

        # Persisted, not just echoed back: a fresh GET agrees.
        get_response = await writer.get(BASE)
        assert get_response.status_code == 200
        assert get_response.json()["office_sharepoint_url"] == url


class TestSharePointUrlClearing:
    async def test_empty_string_clears_a_previously_set_url(self, writer):
        url = "https://contoso.sharepoint.com/sites/intranet"
        set_response = await writer.put(BASE, json={"office_sharepoint_url": url})
        assert set_response.status_code == 200, set_response.text
        assert set_response.json()["office_sharepoint_url"] == url

        clear_response = await writer.put(BASE, json={"office_sharepoint_url": ""})

        assert clear_response.status_code == 200, clear_response.text
        assert clear_response.json()["office_sharepoint_url"] == ""

    async def test_omitting_the_field_leaves_a_previously_set_url_untouched(self, writer):
        """The partial-update contract: only an explicit "" clears it,
        omitting it entirely (None on the wire) must not."""
        url = "https://contoso.sharepoint.com/sites/intranet"
        await writer.put(BASE, json={"office_sharepoint_url": url})

        response = await writer.put(BASE, json={"office_launcher_enabled": True})

        assert response.status_code == 200, response.text
        assert response.json()["office_sharepoint_url"] == url
        assert response.json()["office_launcher_enabled"] is True


class TestOfficeLauncherEnabled:
    async def test_can_be_toggled_on(self, writer):
        response = await writer.put(BASE, json={"office_launcher_enabled": True})

        assert response.status_code == 200, response.text
        assert response.json()["office_launcher_enabled"] is True
