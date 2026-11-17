"""
Guards the read:settings gate that every settings read use case
(get_*_settings.py) enforces: 200 with read:settings, 403 without, on
every one of the 15 routes. test_api_admin_settings_auth.py covers /auth;
this file covers the others.

Every domain but General/Storage needs seeding beyond conftest's autouse
`_seed_admin_settings` fixture (only those two are covered there); values
mirror InitDatabase's own defaults, the same pattern as the made-items/
production/security seeding fixtures already used elsewhere in this suite.
"""

import pytest
from fastapi.testclient import TestClient
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
from src.modules.platform.domain.entities.admin_settings.maintenance import AdminMaintenanceSettings
from src.modules.platform.domain.entities.admin_settings.notifications import (
    AdminNotificationSettings,
)
from src.modules.platform.domain.entities.admin_settings.retention import AdminRetentionSettings
from src.modules.platform.domain.entities.admin_settings.security import AdminSecuritySettings

BASE = "/api/v1/web/admin/settings"

# (route path, is it the two already covered by conftest's autouse fixture?)
ROUTES = [
    "/host",
    "/auth",
    "/mail",
    "/storage",
    "/security",
    "/features",
    "/general",
    "/branding",
    "/notifications",
    "/maintenance",
    "/retention",
    "/orders",
    "/made-items",
    "/pdm",
    "/production",
]


@pytest.fixture(autouse=True)
async def _seed_every_settings_domain(db: Session) -> None:
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
    await repo.save_maintenance(
        AdminMaintenanceSettings(id=1, enabled=False, message=None, allowed_ips=[])
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


@pytest.mark.parametrize("route", ROUTES)
async def test_read_with_permission_succeeds(auth_client, route: str) -> None:
    client: TestClient = await auth_client(permissions=["read:settings"])
    resp = await client.get(f"{BASE}{route}")
    assert resp.status_code == 200, resp.text


@pytest.mark.parametrize("route", ROUTES)
async def test_read_without_permission_is_forbidden(auth_client, route: str) -> None:
    client: TestClient = await auth_client(permissions=[])
    resp = await client.get(f"{BASE}{route}")
    assert resp.status_code == 403, resp.text


async def test_integrations_overview_requires_read_settings(auth_client) -> None:
    client: TestClient = await auth_client(permissions=[])
    resp = await client.get(f"{BASE}/host/integrations")
    assert resp.status_code == 403, resp.text
