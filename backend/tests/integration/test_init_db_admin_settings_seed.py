"""
Characterization coverage for InitDatabase._ensure_admin_settings against a
real (SQLite) database: every column of every seeded admin settings
singleton on a fresh install, plus the rule that a row which already exists
is left exactly as it is, custom values and NULLs alike, while every other
still-absent row is seeded in the same pass.

The unit test in tests/unit/test_init_db_seed_defaults.py pins a handful of
literals through a fake repository; this one goes through the real
repository and ORM so that column defaults, JSON round trips and the
repository's entity-to-row mapping are part of what is pinned.
"""

from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Any

from sqlalchemy import delete
from sqlalchemy import inspect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bootstrap.adapters.outbound.persistence.init_db import InitDatabase
from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.models.admin_settings_model.made_items import (
    AdminMadeItemSettingsOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.admin_settings_model.orders import (
    AdminOrderSettingsOrmModel,
)
from src.modules.catalogue.domain.policies.item_field_ownership import default_policy
from src.modules.external_data.adapters.outbound.persistence.models.admin_settings_model.pdm import (
    AdminPdmSettingsOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.admin_settings_model.production import (
    AdminProductionSettingsOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.auth import (
    AdminAuthSettingsOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.banner import (
    AdminBannerSettingsOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.branding import (
    AdminBrandingSettingsOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.features import (
    AdminFeatureSettingsOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.general import (
    AdminGeneralSettingsOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.host import (
    AdminHostSettingsOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.mail import (
    AdminMailSettingsOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.maintenance import (
    AdminMaintenanceSettingsOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.notifications import (
    AdminNotificationSettingsOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.retention import (
    AdminRetentionSettingsOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.security import (
    AdminSecuritySettingsOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.storage import (
    AdminStorageSettingsOrmModel,
)
from src.modules.platform.infrastructure.config.settings import cfg

_SETTINGS_MODELS: tuple[type[Any], ...] = (
    AdminHostSettingsOrmModel,
    AdminMailSettingsOrmModel,
    AdminAuthSettingsOrmModel,
    AdminStorageSettingsOrmModel,
    AdminSecuritySettingsOrmModel,
    AdminFeatureSettingsOrmModel,
    AdminGeneralSettingsOrmModel,
    AdminBrandingSettingsOrmModel,
    AdminNotificationSettingsOrmModel,
    AdminMaintenanceSettingsOrmModel,
    AdminRetentionSettingsOrmModel,
    AdminOrderSettingsOrmModel,
    AdminMadeItemSettingsOrmModel,
    AdminPdmSettingsOrmModel,
    AdminProductionSettingsOrmModel,
    AdminBannerSettingsOrmModel,
)

# Random or clock-dependent columns, checked separately rather than pinned.
_VOLATILE_COLUMNS = {"public_id", "updated_at"}


async def _clear_settings(db: AsyncSession) -> None:
    """The integration conftest pre-seeds a few bare settings rows for the
    request path; remove them so the seed runs against a fresh install."""
    for model in _SETTINGS_MODELS:
        await db.execute(delete(model))
    await db.commit()


async def _snapshot(db: AsyncSession) -> dict[str, dict[str, Any] | None]:
    snapshot: dict[str, dict[str, Any] | None] = {}
    for model in _SETTINGS_MODELS:
        orm = await db.scalar(
            select(model).filter_by(id=1).execution_options(populate_existing=True)
        )
        if orm is None:
            snapshot[model.__tablename__] = None
            continue
        snapshot[model.__tablename__] = {
            attr.key: getattr(orm, attr.key)
            for attr in inspect(model).column_attrs
            if attr.key not in _VOLATILE_COLUMNS
        }
    return snapshot


async def _seed(db: AsyncSession) -> None:
    await InitDatabase(
        user_repo=None,  # type: ignore[arg-type]
        admin_settings_repo=SqlAlchemyAdminSettingsRepository(db),
        print_template_repo=None,  # type: ignore[arg-type]
        db=db,
    )._ensure_admin_settings()


def _expected_fresh_install() -> dict[str, dict[str, Any] | None]:
    """Every seeded column on a fresh install. Values taken from env config
    or from a domain default function are referenced rather than copied."""
    return {
        "admin_host_settings": {"id": 1},
        "admin_mail_settings": {
            "id": 1,
            "enabled": False,
            "host": "",
            "port": 587,
            "user": "",
            "password": None,
            "from_address": None,
            "use_tls": True,
            "use_ssl": False,
            "verify_certificate": True,
            "from_display_name": "",
            "reply_to": None,
            "send_limit_per_hour": 20,
            "send_lock_minutes": 60,
            "alert_recipients": [],
            "attachment_limit_mb": 10,
        },
        "admin_auth_settings": {
            "id": 1,
            "ldap_enabled": False,
            "ldap_host": "",
            "ldap_port": 636,
            "ldap_use_ssl": True,
            "ldap_start_tls": False,
            "ldap_verify_certificate": True,
            "ldap_domain": "",
            "ldap_timeout_seconds": 5,
        },
        "admin_storage_settings": {
            "id": 1,
            "provider": "local",
            "enabled": False,
            "endpoint_url": None,
            "public_endpoint_url": None,
            "bucket_name": None,
            "access_key": None,
            "secret_key": None,
            "region": None,
            "use_ssl": True,
            "backup_enabled": False,
            "backup_path": None,
            "backup_cron": None,
            "backup_retention_count": 7,
            "disk_warning_percent": 90,
        },
        "admin_security_settings": {
            "id": 1,
            "enforce_totp": False,
            "allow_rfid_login": cfg.security.allow_rfid_login,
            "allow_local_login": True,
            "enable_api_key_auth": False,
            "min_password_length": cfg.security.min_pw_len,
            "session_timeout_minutes": 1440,
            "totp_trusted_device_days": 30,
            "max_login_attempts": 5,
            "lockout_duration_minutes": 15,
            "token_max_lifetime_days": 365,
            "session_max_lifetime_days": 30,
            "enable_terminals": True,
            "enable_infoscreen_weather": True,
            "terminal_allowed_ips": [],
        },
        "admin_feature_settings": {
            "id": 1,
            "enable_email_notifications": True,
            "enable_production_planning": True,
            "allow_private_webhooks": True,
            "enable_calculations": True,
            "enable_checklists": True,
            "enable_devices": True,
            "enable_sequences": True,
            "enable_todos": True,
        },
        "admin_general_settings": {
            "id": 1,
            "company_name": None,
            "company_legal_name": None,
            "company_logo_key": None,
            "contact_email": None,
            "imprint_url": None,
            "privacy_url": None,
            "support_url": None,
            "product_number_pattern": "",
            "project_number_pattern": "",
            "allow_headless_projects": True,
            "empty_value_placeholder": "-",
            "office_launcher_enabled": False,
            "office_sharepoint_url": "",
            "currency": "EUR",
            "default_language": "enGB",
            "default_timezone": "Europe/Vienna",
            "default_date_format": "iso",
        },
        "admin_branding_settings": {
            "id": 1,
            "app_name": "Glados",
            "app_description": None,
            "footer_text": None,
            "logo_url": None,
            "favicon_url": None,
            "logo_key": None,
            "favicon_key": None,
            "login_background_video_key": None,
        },
        "admin_notification_settings": {
            "id": 1,
            "webhook_timeout_seconds": 10,
        },
        "admin_maintenance_settings": {
            "id": 1,
            "enabled": False,
            "message": None,
            "allowed_ips": [],
        },
        "admin_retention_settings": {
            "id": 1,
            "log_retention_days": 90,
            "audit_retention_days": 365,
            "soft_delete_cleanup_days": 0,
            "meeting_retention_days": 0,
        },
        "admin_order_settings": {
            "id": 1,
            "order_number_format": "ORD-{yy}-{seq:05d}",
            "part_number_format": "PUR-{yy}-{seq:05d}",
            "part_number_auto": True,
            "part_number_editable": False,
            "web_creation_allowed": True,
            "pdm_part_number_pattern": "",
            "over_delivery_tolerance_percent": 0.0,
            "under_delivery_tolerance_percent": 0.0,
            "quote_request_number_format": "RFQ-{yy}-{seq:05d}",
        },
        "admin_made_item_settings": {
            "id": 1,
            "item_number_format": "FAB-{yy}-{seq:05d}",
            "lot_number_format": "LOT-{yy}-{seq:05d}",
            "calculation_number_format": "CAL-{yy}-{seq:04d}",
            "checklist_number_format": "CHK-{yy}-{seq:04d}",
            "sequence_number_format": "SEQ-{yy}-{seq:04d}",
            "meeting_number_format": "MTG-{yy}-{seq:04d}",
            "part_number_auto": True,
            "part_number_editable": False,
            "revision_start": "0",
            "revision_separator": ":",
            "revision_skip_ambiguous_letters": False,
            "revision_only_newest_editable": True,
            "revision_predecessor_status_web": "ask",
            "revision_predecessor_status_pdm": "replaced",
            "revision_field_policy": [
                {
                    "field": p.field,
                    "web_requires_revision": p.web_requires_revision,
                    "pdm_update_in_place": p.pdm_update_in_place,
                }
                for p in default_policy()
            ],
            "web_creation_allowed": True,
            "pdm_part_number_pattern": "",
        },
        "admin_pdm_settings": {
            "id": 1,
            "made_item_variable_map": {
                "part_number": "PDM.PartNumber",
                "revision": "PDM.Revision",
                "revision_date": "PDM.RevisionDate",
                "revision_note": "PDM.RevisionNote",
                "article_name": "Glados.ArticleName",
                "material": "Glados.Material",
                "mass": "Glados.Mass",
                "base_size": "Glados.BaseSize",
                "note": "Glados.Note",
                "weblink": "Glados.Weblink",
                "article_group_ids": "Glados.ArticleGroupIds",
                "bought_item_id": "Glados.BoughtItemId",
                "source_item_id": "Glados.SourceItemId",
                "customer_id": "Glados.CustomerId",
                "customer_part_number": "Glados.CustomerPartNumber",
                "customer_revision": "Glados.CustomerRevision",
                "processes": "Glados.Processes",
                "article_group_names": "Glados.ArticleGroupNames",
                "process_names": "Glados.ProcessNames",
                "source_item_name": "Glados.SourceItemName",
                "customer_name": "Glados.CustomerName",
                "feature_tree_representation": "Glados.FeatureTreeRepresentation",
            },
            "bought_item_variable_map": {
                "part_number": "PDM.PartNumber",
                "revision": "PDM.Revision",
                "article_name": "Glados.ArticleName",
                "order_code_1": "Glados.OrderCode1",
                "order_code_2": "Glados.OrderCode2",
                "gtin": "Glados.Gtin",
                "ean": "Glados.Ean",
                "tariff_number": "Glados.TariffNumber",
                "mass": "Glados.Mass",
                "note": "Glados.Note",
                "weblink": "Glados.Weblink",
                "manufacturer_id": "Glados.ManufacturerId",
                "article_group_ids": "Glados.ArticleGroupIds",
                "edp_part_id": "Glados.EdpPartId",
                "manufacturer_name": "Glados.ManufacturerName",
                "article_group_names": "Glados.ArticleGroupNames",
                "feature_tree_representation": "Glados.FeatureTreeRepresentation",
            },
            "enabled": False,
            "base_url": "",
            "vault_name": "",
            "username": "",
            "password": None,
            "verify_certificate": True,
            "timeout_seconds": 15,
            "session_token": None,
            "session_user_id": None,
            "session_obtained_at": None,
            "watched_folders": [],
            "made_released_state_ids": [],
            "made_obsolete_state_ids": [],
            "bought_released_state_ids": [],
            "bought_obsolete_state_ids": [],
            "made_replaced_state_ids": [],
            "bought_replaced_state_ids": [],
            "document_released_state_ids": [],
            "poll_interval_minutes": 15,
            "cold_folder_max_multiplier": 8,
            "ingest_concurrency": 4,
            "vault_id": "",
            "cad_items_read_only": True,
            "addin_language": "",
            "last_poll_at": None,
            "last_poll_error": None,
            "last_poll_summary": None,
            "writeback_enabled": False,
            "made_item_extensions": ["sldprt"],
            "bought_item_extensions": ["sldprt", "sldasm"],
            "document_categories": {"pdf": "drawing", "dxf": "dxf", "step": "step", "stp": "step"},
            "document_excluded_kinds": {},
            "thumbnails_enabled": False,
            "stuck_after_days": 7,
            "reconcile_requested_deep": None,
            "required_fields": {"made": ["material", "fabrication_step"], "bought": ["revision"]},
            "set_approver_from_pdm": False,
            "made_feature_tree_template": (
                '$PRP:"PDM.PartNumber" Rev$PRP:"PDM.Revision" ($PRP:"Glados.ArticleName")'
            ),
            "bought_feature_tree_template": (
                '$PRP:"Glados.ArticleName" - $PRP:"Glados.OrderCode1" - '
                '$PRP:"Glados.ManufacturerName"'
            ),
        },
        "admin_production_settings": {
            "id": 1,
            "production_order_number_format": "PON-{yy}-{seq:05d}",
            # JSON object keys read back as strings; Monday to Friday work
            # one interval from 08:00 for 480 minutes.
            "default_weekly_hours": {
                str(day): ([{"start_minute": 480, "minutes": 480}] if day < 5 else [])
                for day in range(7)
            },
            "default_external_lead_days": 0,
            "response_time_days": 1,
            "require_qa": False,
            "require_source_item_approval": False,
            "assign_approved_material_to_item": False,
            "overwrite_item_material_on_approval": False,
            "default_inspection_method_id": None,
            "frozen_window_hours": 0,
        },
        "admin_banner_settings": {
            "id": 1,
            "enabled": False,
            "text": "",
            "severity": "info",
            "shows_from": None,
            "shows_until": None,
            "dismissable": True,
        },
    }


async def test_fresh_install_seeds_every_settings_row(db: AsyncSession) -> None:
    await _clear_settings(db)
    before = datetime.now(UTC)

    await _seed(db)

    assert await _snapshot(db) == _expected_fresh_install()
    banner = await db.scalar(select(AdminBannerSettingsOrmModel).filter_by(id=1))
    assert banner is not None
    updated_at = banner.updated_at
    if updated_at.tzinfo is None:
        # SQLite reads timezone-aware values back naive, digits preserved.
        updated_at = updated_at.replace(tzinfo=UTC)
    slack = timedelta(seconds=1)
    assert before - slack <= updated_at <= datetime.now(UTC) + slack


async def test_a_second_run_changes_nothing(db: AsyncSession) -> None:
    await _clear_settings(db)
    await _seed(db)
    first = await _snapshot(db)

    await _seed(db)

    assert await _snapshot(db) == first


async def test_existing_rows_are_left_alone_and_absent_rows_are_seeded(db: AsyncSession) -> None:
    """A pre-existing row keeps its custom values and its NULLs; nothing is
    backfilled into it, even where the seed would write a non-NULL value."""
    await _clear_settings(db)
    db.add(
        AdminMailSettingsOrmModel(
            id=1,
            enabled=True,
            host="smtp.example.test",
            port=2525,
            user="mailer",
            use_tls=False,
            use_ssl=True,
            verify_certificate=False,
            from_display_name="Custom",
            send_limit_per_hour=99,
            send_lock_minutes=5,
        )
    )
    db.add(AdminBrandingSettingsOrmModel(id=1, app_name="Custom App"))
    db.add(
        AdminSecuritySettingsOrmModel(
            id=1,
            enforce_totp=True,
            allow_rfid_login=False,
            allow_local_login=False,
            enable_api_key_auth=True,
            min_password_length=20,
            session_timeout_minutes=60,
            totp_trusted_device_days=1,
            max_login_attempts=0,
            lockout_duration_minutes=1,
            token_max_lifetime_days=7,
        )
    )
    await db.commit()
    preexisting = await _snapshot(db)

    await _seed(db)

    after = await _snapshot(db)
    expected = _expected_fresh_install()
    for table, row in after.items():
        if preexisting[table] is not None:
            assert row == preexisting[table], table
        else:
            assert row == expected[table], table
    mail = after["admin_mail_settings"]
    branding = after["admin_branding_settings"]
    assert mail is not None
    assert branding is not None
    assert mail["host"] == "smtp.example.test"
    assert mail["from_address"] is None
    assert branding["app_name"] == "Custom App"
