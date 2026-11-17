"""
GET /host/capabilities: the one settings surface every authenticated user
can read regardless of permissions, because the header renders for
everyone and /admin/settings/ requires read:settings (see host.py's own
docstring). These tests cover the office launcher's
office_launcher_enabled / office_sharepoint_url fields and the locale
defaults default_language / default_timezone / default_date_format
fields: all must be visible here, at the top level of the response
(alongside empty_value_placeholder, not nested under `features`), to a
plain user with no admin permissions at all.
"""

import pytest

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.platform.domain.entities.admin_settings.features import AdminFeatureSettings
from src.modules.platform.domain.entities.admin_settings.mail import AdminMailSettings
from src.modules.platform.domain.entities.admin_settings.security import AdminSecuritySettings

BASE = "/api/v1/web/host/capabilities"


@pytest.fixture(autouse=True)
async def _seed_mail_and_features(db) -> None:
    """conftest's autouse `_seed_admin_settings` only seeds General and
    Storage (the two domains the wider request path reads); this endpoint
    also reads mail.enabled, the feature flags, and (Settings polish batch)
    security.token_max_lifetime_days, so this file needs its own seeding,
    same pattern as test_api_admin_settings_reads.py's
    `_seed_every_settings_domain`."""
    repo = SqlAlchemyAdminSettingsRepository(db)
    await repo.save_mail(
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
    await repo.save_features(
        AdminFeatureSettings(
            id=1,
            enable_email_notifications=True,
            enable_production_planning=True,
            allow_private_webhooks=False,
        )
    )
    await db.commit()
    await repo.save_security(
        AdminSecuritySettings(
            id=1,
            enforce_totp=False,
            allow_rfid_login=True,
            allow_local_login=True,
            enable_api_key_auth=False,
            min_password_length=8,
            session_timeout_minutes=1440,
            totp_trusted_device_days=30,
            max_login_attempts=5,
            lockout_duration_minutes=15,
            token_max_lifetime_days=3650,
        )
    )
    await db.commit()


class TestCapabilitiesVisibleToAnyAuthenticatedUser:
    async def test_a_non_admin_user_sees_the_office_launcher_fields(self, auth_client):
        client = await auth_client(permissions=[])

        response = await client.get(BASE)

        assert response.status_code == 200, response.text
        body = response.json()
        assert "office_launcher_enabled" in body
        assert "office_sharepoint_url" in body
        # Top level, not nested under `features`, the same precedent as
        # empty_value_placeholder.
        assert "office_launcher_enabled" not in body.get("features", {})

    async def test_a_non_admin_user_sees_the_locale_default_fields(self, auth_client):
        """conftest's `_seed_admin_settings` seeds the general row without
        these columns at all, so this is the migration's server_default
        path, the baseline every unconfigured tenant sees, mirroring
        src/modules/platform/const.py's SERVER_DEFAULT_LANGUAGE/TIMEZONE/DATE_FORMAT."""
        client = await auth_client(permissions=[])

        response = await client.get(BASE)

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["default_language"] == "enGB"
        assert body["default_timezone"] == "Europe/Vienna"
        assert body["default_date_format"] == "iso"
        assert "default_language" not in body.get("features", {})

    async def test_reflects_the_stored_general_settings(self, auth_client, db):
        repo = SqlAlchemyAdminSettingsRepository(db)
        general = await repo.get_general()
        general.office_launcher_enabled = True
        general.office_sharepoint_url = "https://contoso.sharepoint.com/sites/intranet"
        await repo.save_general(general)
        await db.commit()

        client = await auth_client(permissions=[])
        response = await client.get(BASE)

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["office_launcher_enabled"] is True
        assert body["office_sharepoint_url"] == "https://contoso.sharepoint.com/sites/intranet"

    async def test_a_non_admin_user_sees_the_currency_field(self, auth_client):
        """Presentation only, but every user's UI needs it: order tables and
        mail previews all render in this currency."""
        client = await auth_client(permissions=[])

        response = await client.get(BASE)

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["currency"] == "EUR"  # conftest's default-seeded general row
        assert "currency" not in body.get("features", {})

    async def test_reflects_a_configured_currency(self, auth_client, db):
        repo = SqlAlchemyAdminSettingsRepository(db)
        general = await repo.get_general()
        general.currency = "USD"
        await repo.save_general(general)
        await db.commit()

        response = await (await auth_client(permissions=[])).get(BASE)

        assert response.status_code == 200, response.text
        assert response.json()["currency"] == "USD"

    async def test_a_non_admin_user_sees_the_token_max_lifetime_days_field(self, auth_client):
        """Any signed-in user can create a PAT, not just an admin, so the
        create dialog needs this without read:settings."""
        client = await auth_client(permissions=[])

        response = await client.get(BASE)

        assert response.status_code == 200, response.text
        assert response.json()["token_max_lifetime_days"] == 3650

    async def test_a_non_admin_user_sees_the_mail_attachment_limit(self, auth_client, db):
        """The send dialog of the meeting notes leaves out the documents
        over this limit, and its user needs no read:settings for it."""
        repo = SqlAlchemyAdminSettingsRepository(db)
        mail = await repo.get_mail()
        mail.attachment_limit_mb = 25
        await repo.save_mail(mail)
        await db.commit()

        response = await (await auth_client(permissions=[])).get(BASE)

        assert response.status_code == 200, response.text
        assert response.json()["mail_attachment_limit_mb"] == 25

    async def test_a_non_admin_user_sees_the_addin_scopes_field(self, auth_client):
        """The add-in token shortcut needs this without read:settings, same
        reasoning as token_max_lifetime_days above; the set itself is
        defined once in token_permission_rules.SOLIDWORKS_ADDIN_SCOPES."""
        client = await auth_client(permissions=[])

        response = await client.get(BASE)

        assert response.status_code == 200, response.text
        assert response.json()["addin_scopes"] == ["write:source_items", "use:data_portal"]

    async def test_a_non_admin_user_sees_the_pdm_addin_scopes_field(self, auth_client):
        """The PDM add-in token shortcut on the API key tab needs this for the
        same reason addin_scopes above does; the set itself is defined once in
        token_permission_rules.PDM_ADDIN_SCOPES."""
        client = await auth_client(permissions=[])

        response = await client.get(BASE)

        assert response.status_code == 200, response.text
        assert response.json()["pdm_addin_scopes"] == ["use:pdm_addin"]

    async def test_reports_the_module_feature_flags(self, auth_client, db):
        repo = SqlAlchemyAdminSettingsRepository(db)
        features = await repo.get_features()
        features.enable_calculations = False
        features.enable_todos = False
        await repo.save_features(features)
        await db.commit()

        client = await auth_client(permissions=[])
        response = await client.get(BASE)

        assert response.status_code == 200, response.text
        flags = response.json()["features"]
        assert flags["calculations"] is False
        assert flags["todos"] is False
        assert flags["checklists"] is True
        assert flags["devices"] is True
        assert flags["sequences"] is True

    async def test_sequences_are_off_while_devices_are_off(self, auth_client, db):
        """A sequence is built from a product's devices, so switching devices
        off takes sequences with them, whatever their own switch says."""
        repo = SqlAlchemyAdminSettingsRepository(db)
        features = await repo.get_features()
        features.enable_devices = False
        await repo.save_features(features)
        await db.commit()

        client = await auth_client(permissions=[])
        response = await client.get(BASE)

        assert response.status_code == 200, response.text
        assert response.json()["features"]["sequences"] is False
