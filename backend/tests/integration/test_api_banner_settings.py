"""
HTTP-level coverage of /api/v1/web/admin/settings/banner: a singleton
settings domain, full-replace PUT like maintenance (see
test_api_maintenance_mode.py). admin_banner_settings is seeded disabled
by conftest's autouse `_seed_admin_settings`, same baseline as storage/
maintenance.
"""

from sqlalchemy.orm import Session

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.catalogue.domain.entities.admin_settings.made_items import AdminMadeItemSettings
from src.modules.catalogue.domain.entities.admin_settings.orders import AdminOrderSettings
from src.modules.catalogue.domain.policies.item_field_ownership import default_policy
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.platform.domain.entities.admin_settings.auth import AdminAuthSettings
from src.modules.platform.domain.entities.admin_settings.branding import AdminBrandingSettings
from src.modules.platform.domain.entities.admin_settings.features import AdminFeatureSettings
from src.modules.platform.domain.entities.admin_settings.host import AdminHostSettings
from src.modules.platform.domain.entities.admin_settings.mail import AdminMailSettings
from src.modules.platform.domain.entities.admin_settings.notifications import (
    AdminNotificationSettings,
)
from src.modules.platform.domain.entities.admin_settings.retention import AdminRetentionSettings
from src.modules.platform.domain.entities.admin_settings.security import AdminSecuritySettings

BASE = "/api/v1/web/admin/settings/banner"
ALL_SETTINGS_URL = "/api/v1/web/admin/settings/"


async def _seed_remaining_settings_domains(db: Session) -> None:
    """conftest's autouse `_seed_admin_settings` only seeds General/
    Storage/Maintenance/Banner; GET /admin/settings/ reads every domain,
    so the aggregate test below needs the rest too, using the same values
    as test_api_admin_settings_reads.py's own fixture of the same purpose."""
    repo = SqlAlchemyAdminSettingsRepository(db)
    await repo.save_host(AdminHostSettings(id=1))
    await db.commit()
    await repo.save_auth(
        AdminAuthSettings(
            id=1,
            ldap_enabled=False,
            ldap_host="",
            ldap_port=636,
            ldap_use_ssl=True,
            ldap_start_tls=False,
            ldap_verify_certificate=True,
            ldap_domain="",
            ldap_timeout_seconds=5,
        )
    )
    await db.commit()
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
    await repo.save_features(
        AdminFeatureSettings(
            id=1,
            enable_email_notifications=True,
            enable_production_planning=True,
            allow_private_webhooks=False,
        )
    )
    await db.commit()
    await repo.save_branding(
        AdminBrandingSettings(
            id=1,
            app_name="Glados",
            app_description=None,
            footer_text=None,
            logo_url=None,
            favicon_url=None,
            logo_key=None,
            favicon_key=None,
            login_background_video_key=None,
        )
    )
    await db.commit()
    await repo.save_notifications(
        AdminNotificationSettings(
            id=1,
            webhook_timeout_seconds=10,
        )
    )
    await db.commit()
    await repo.save_retention(
        AdminRetentionSettings(
            id=1, log_retention_days=90, audit_retention_days=365, soft_delete_cleanup_days=0
        )
    )
    await db.commit()
    await repo.save_orders(
        AdminOrderSettings(
            id=1,
            order_number_format="ORD-{yy}-{seq:05d}",
            part_number_format="PUR-{yy}-{seq:05d}",
            part_number_auto=True,
            part_number_editable=False,
            web_creation_allowed=True,
            pdm_part_number_pattern="",
        )
    )
    await db.commit()
    await repo.save_made_items(
        AdminMadeItemSettings(
            id=1,
            item_number_format="FAB-{yy}-{seq:05d}",
            lot_number_format="LOT-{yy}-{seq:05d}",
            part_number_auto=True,
            part_number_editable=False,
            revision_start="0",
            revision_separator=":",
            revision_skip_ambiguous_letters=False,
            revision_only_newest_editable=True,
            revision_predecessor_status_web="ask",
            revision_predecessor_status_pdm="replaced",
            revision_field_policy=default_policy(),
            web_creation_allowed=True,
            pdm_part_number_pattern="",
        )
    )
    await db.commit()
    await repo.save_production(
        AdminProductionSettings(
            id=1,
            production_order_number_format="PON-{yy}-{seq:05d}",
            default_weekly_hours={0: 480, 1: 480, 2: 480, 3: 480, 4: 480, 5: 0, 6: 0},
            default_external_lead_days=0,
            response_time_days=1,
            require_qa=False,
        )
    )
    await db.commit()
    await repo.save_pdm(
        AdminPdmSettings(
            id=1,
            made_item_variable_map={"part_number": "PDM.PartNumber", "revision": "PDM.Revision"},
            bought_item_variable_map={
                "part_number": "PDM.PartNumber",
                "revision": "PDM.Revision",
            },
            enabled=False,
            base_url="",
            vault_name="",
            username="",
            password=None,
            verify_certificate=True,
            timeout_seconds=15,
            watched_folders=[],
            made_released_state_ids=[],
            made_obsolete_state_ids=[],
            made_replaced_state_ids=[],
            bought_released_state_ids=[],
            bought_obsolete_state_ids=[],
            bought_replaced_state_ids=[],
            poll_interval_minutes=15,
            vault_id="",
            cad_items_read_only=True,
            last_poll_at=None,
            last_poll_error=None,
            last_poll_summary=None,
            writeback_enabled=False,
            session_token=None,
            session_user_id=None,
            session_obtained_at=None,
            made_item_extensions=["sldprt"],
            bought_item_extensions=["sldprt", "sldasm"],
            document_categories={"pdf": "drawing", "dxf": "dxf", "step": "step", "stp": "step"},
            thumbnails_enabled=False,
            stuck_after_days=7,
            reconcile_requested_deep=None,
            required_fields={"made": [], "bought": []},
        )
    )
    await db.commit()


async def test_get_requires_read_settings(auth_client) -> None:
    client = await auth_client(permissions=[])
    resp = await client.get(BASE)
    assert resp.status_code == 403


async def test_get_returns_seeded_defaults(auth_client) -> None:
    client = await auth_client(permissions=["read:settings"])
    resp = await client.get(BASE)
    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is False
    assert body["text"] == ""
    assert body["severity"] == "info"
    assert body["shows_from"] is None
    assert body["shows_until"] is None
    assert "updated_at" in body


async def test_get_returns_seeded_default_dismissable_true(auth_client) -> None:
    """dismissable is NOT NULL server_default true on admin_banner_settings.
    Conftest's `_seed_admin_settings` inserts this row without setting
    dismissable explicitly, unlike enabled/text/severity above, which it
    does set, so this pins the database's own default rather than an
    application-level one."""
    client = await auth_client(permissions=["read:settings"])
    resp = await client.get(BASE)
    assert resp.status_code == 200
    assert resp.json()["dismissable"] is True


async def test_put_requires_write_settings(auth_client) -> None:
    client = await auth_client(permissions=["read:settings"])
    resp = await client.put(BASE, json={"enabled": False, "text": "", "severity": "info"})
    assert resp.status_code == 403


async def test_put_updates_fields(auth_client) -> None:
    client = await auth_client(permissions=["write:settings", "read:settings"])
    resp = await client.put(
        BASE,
        json={
            "enabled": True,
            "text": "We upgrade at 18:00",
            "severity": "warning",
            "shows_from": "2026-01-01T00:00:00Z",
            "shows_until": "2026-01-02T00:00:00Z",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["enabled"] is True
    assert body["text"] == "We upgrade at 18:00"
    assert body["severity"] == "warning"
    assert body["shows_from"] == "2026-01-01T00:00:00Z"
    assert body["shows_until"] == "2026-01-02T00:00:00Z"

    # Persisted, not just echoed back.
    again = (await client.get(BASE)).json()
    assert again["text"] == "We upgrade at 18:00"


async def test_put_round_trips_dismissable_false_and_true(auth_client) -> None:
    client = await auth_client(permissions=["write:settings", "read:settings"])

    off = await client.put(
        BASE, json={"enabled": False, "text": "", "severity": "info", "dismissable": False}
    )
    assert off.status_code == 200, off.text
    assert off.json()["dismissable"] is False
    assert (await client.get(BASE)).json()["dismissable"] is False

    on = await client.put(
        BASE, json={"enabled": False, "text": "", "severity": "info", "dismissable": True}
    )
    assert on.status_code == 200, on.text
    assert on.json()["dismissable"] is True
    assert (await client.get(BASE)).json()["dismissable"] is True


async def test_put_bumps_updated_at_on_every_save(auth_client) -> None:
    client = await auth_client(permissions=["write:settings", "read:settings"])
    first = (await client.put(BASE, json={"enabled": False, "text": "", "severity": "info"})).json()
    second = (
        await client.put(BASE, json={"enabled": False, "text": "still nothing", "severity": "info"})
    ).json()
    assert second["updated_at"] != first["updated_at"]


async def test_put_422_when_enabled_with_blank_text(auth_client) -> None:
    client = await auth_client(permissions=["write:settings"])
    resp = await client.put(BASE, json={"enabled": True, "text": "", "severity": "info"})
    assert resp.status_code == 422


async def test_put_422_when_shows_until_before_shows_from(auth_client) -> None:
    client = await auth_client(permissions=["write:settings"])
    resp = await client.put(
        BASE,
        json={
            "enabled": False,
            "text": "",
            "severity": "info",
            "shows_from": "2026-01-02T00:00:00Z",
            "shows_until": "2026-01-01T00:00:00Z",
        },
    )
    assert resp.status_code == 422


async def test_disabled_with_blank_text_is_valid(auth_client) -> None:
    client = await auth_client(permissions=["write:settings"])
    resp = await client.put(BASE, json={"enabled": False, "text": "", "severity": "info"})
    assert resp.status_code == 200


async def test_appears_in_all_admin_settings_aggregate(auth_client, db: Session) -> None:
    await _seed_remaining_settings_domains(db)
    client = await auth_client(permissions=["write:settings", "read:settings"])
    await client.put(BASE, json={"enabled": True, "text": "Hello", "severity": "danger"})
    resp = await client.get(ALL_SETTINGS_URL)
    assert resp.status_code == 200
    body = resp.json()
    assert "banner" in body
    assert body["banner"]["enabled"] is True
    assert body["banner"]["text"] == "Hello"
    assert body["banner"]["severity"] == "danger"


async def test_dismissable_appears_in_all_admin_settings_aggregate(
    auth_client, db: Session
) -> None:
    await _seed_remaining_settings_domains(db)
    client = await auth_client(permissions=["write:settings", "read:settings"])
    await client.put(
        BASE, json={"enabled": True, "text": "Hello", "severity": "danger", "dismissable": False}
    )
    resp = await client.get(ALL_SETTINGS_URL)
    assert resp.status_code == 200
    assert resp.json()["banner"]["dismissable"] is False
