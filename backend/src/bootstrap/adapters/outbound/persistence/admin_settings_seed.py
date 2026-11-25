"""
Default values for every admin settings singleton, seeded by InitDatabase on
first run. One entry per settings group, in seeding order. Each entry names
the ORM model whose `id=1` row decides whether the group is already present,
the repository method that writes it, and a builder for the default entity.

Builders are functions rather than prebuilt entities so that values read
from env config or the clock are taken at seed time, and so that every seed
gets its own fresh lists and dicts.

To add a settings group, append an entry here; InitDatabase needs no change.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from src.modules.catalogue.adapters.outbound.persistence.models.admin_settings_model.data_import import (
    AdminDataImportSettingsOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.admin_settings_model.made_items import (
    AdminMadeItemSettingsOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.admin_settings_model.orders import (
    AdminOrderSettingsOrmModel,
)
from src.modules.catalogue.domain.entities.admin_settings.data_import import AdminDataImportSettings
from src.modules.catalogue.domain.entities.admin_settings.data_import import DataImportProfile
from src.modules.catalogue.domain.entities.admin_settings.made_items import AdminMadeItemSettings
from src.modules.catalogue.domain.entities.admin_settings.orders import AdminOrderSettings
from src.modules.catalogue.domain.policies.item_field_ownership import default_policy
from src.modules.catalogue.domain.services.data_import_profiles import validate_profile
from src.modules.catalogue.domain.value_objects.data_import_type import DataImportType
from src.modules.external_data.adapters.outbound.persistence.models.admin_settings_model.eplan_data_portal import (
    AdminEdpSettingsOrmModel,
)
from src.modules.external_data.adapters.outbound.persistence.models.admin_settings_model.pdm import (
    AdminPdmSettingsOrmModel,
)
from src.modules.external_data.adapters.outbound.persistence.models.admin_settings_model.stock import (
    AdminStockSettingsOrmModel,
)
from src.modules.external_data.domain.entities.admin_settings.eplan_data_portal import (
    AdminEdpSettings,
)
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.entities.admin_settings.stock import AdminStockSettings
from src.modules.fulfillment.adapters.outbound.persistence.models.admin_settings_model.production import (
    AdminProductionSettingsOrmModel,
)
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.agents import (
    AdminAgentSettingsOrmModel,
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
from src.modules.platform.const import SERVER_DEFAULT_CURRENCY
from src.modules.platform.const import SERVER_DEFAULT_DATE_FORMAT
from src.modules.platform.const import SERVER_DEFAULT_LANGUAGE
from src.modules.platform.const import SERVER_DEFAULT_TIMEZONE
from src.modules.platform.domain.entities.admin_settings.agents import AdminAgentSettings
from src.modules.platform.domain.entities.admin_settings.auth import AdminAuthSettings
from src.modules.platform.domain.entities.admin_settings.banner import AdminBannerSettings
from src.modules.platform.domain.entities.admin_settings.branding import AdminBrandingSettings
from src.modules.platform.domain.entities.admin_settings.features import AdminFeatureSettings
from src.modules.platform.domain.entities.admin_settings.general import AdminGeneralSettings
from src.modules.platform.domain.entities.admin_settings.host import AdminHostSettings
from src.modules.platform.domain.entities.admin_settings.mail import AdminMailSettings
from src.modules.platform.domain.entities.admin_settings.maintenance import AdminMaintenanceSettings
from src.modules.platform.domain.entities.admin_settings.notifications import (
    AdminNotificationSettings,
)
from src.modules.platform.domain.entities.admin_settings.retention import AdminRetentionSettings
from src.modules.platform.domain.entities.admin_settings.security import AdminSecuritySettings
from src.modules.platform.domain.entities.admin_settings.storage import AdminStorageSettings
from src.modules.platform.domain.value_objects.announcement_severity import AnnouncementSeverity
from src.modules.platform.domain.value_objects.date_format import DateFormat
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.infrastructure.config.settings import cfg
from src.read.ports.outbound.repositories.admin_settings_repository import IAdminSettingsRepository
from src.shared_kernel.domain.services.clock import now_utc


@dataclass(frozen=True)
class AdminSettingsSeed[T]:
    """One settings group: how to detect it, build its defaults and save it.

    `label` only feeds the "Admin <label> settings seeded." log line.
    """

    label: str
    model: type[Any]
    save: Callable[[IAdminSettingsRepository], Callable[[T], Awaitable[T]]]
    build: Callable[[], T]


def _data_import_defaults() -> AdminDataImportSettings:
    """One profile per import type with the default header and row settings
    and no column names. Column names are imported by an admin, since the
    names a site's spreadsheets use differ from install to install."""
    return AdminDataImportSettings(
        id=1,
        profiles={t.value: validate_profile(t, DataImportProfile()) for t in DataImportType},
    )


def _pdm_defaults() -> AdminPdmSettings:
    # SW custom-property defaults are mirrored (not imported) from
    # admin_settings_model/pdm.py's column defaults, per docs/FIELD_OWNERSHIP.md:
    # the shipped default is also the seed value, the same duplication as
    # the numbering formats seeded in the other groups.
    return AdminPdmSettings(
        id=1,
        made_item_variable_map={
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
        bought_item_variable_map={
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
        enabled=False,
        base_url="",
        vault_name="",
        username="",
        password=None,
        verify_certificate=True,
        timeout_seconds=15,
        session_token=None,
        session_user_id=None,
        session_obtained_at=None,
        watched_folders=[],
        made_released_state_ids=[],
        made_obsolete_state_ids=[],
        made_replaced_state_ids=[],
        bought_released_state_ids=[],
        bought_obsolete_state_ids=[],
        bought_replaced_state_ids=[],
        document_released_state_ids=[],
        poll_interval_minutes=15,
        vault_id="",
        cad_items_read_only=True,
        addin_language="",
        last_poll_at=None,
        last_poll_error=None,
        last_poll_summary=None,
        writeback_enabled=False,
        made_item_extensions=["sldprt"],
        bought_item_extensions=["sldprt", "sldasm"],
        document_categories={"pdf": "drawing", "dxf": "dxf", "step": "step", "stp": "step"},
        thumbnails_enabled=False,
        stuck_after_days=7,
        reconcile_requested_deep=None,
        required_fields={"made": ["material", "fabrication_step"], "bought": ["revision"]},
    )


ADMIN_SETTINGS_SEEDS: tuple[AdminSettingsSeed[Any], ...] = (
    AdminSettingsSeed(
        label="host",
        model=AdminHostSettingsOrmModel,
        save=lambda repo: repo.save_host,
        build=lambda: AdminHostSettings(id=1),
    ),
    AdminSettingsSeed(
        label="mail",
        model=AdminMailSettingsOrmModel,
        save=lambda repo: repo.save_mail,
        build=lambda: AdminMailSettings(
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
            attachment_limit_mb=10,
        ),
    ),
    AdminSettingsSeed(
        label="auth",
        model=AdminAuthSettingsOrmModel,
        save=lambda repo: repo.save_auth,
        build=lambda: AdminAuthSettings(
            id=1,
            ldap_enabled=False,
            ldap_host="",
            ldap_port=636,
            ldap_use_ssl=True,
            ldap_start_tls=False,
            ldap_verify_certificate=True,
            ldap_domain="",
            ldap_timeout_seconds=5,
        ),
    ),
    AdminSettingsSeed(
        label="storage",
        model=AdminStorageSettingsOrmModel,
        save=lambda repo: repo.save_storage,
        build=lambda: AdminStorageSettings(
            id=1,
            provider="local",
            enabled=False,
            endpoint_url=None,
            public_endpoint_url=None,
            bucket_name=None,
            access_key=None,
            secret_key=None,
            region=None,
            use_ssl=True,
            backup_enabled=False,
            backup_path=None,
            backup_cron=None,
            backup_retention_count=7,
            disk_warning_percent=90,
        ),
    ),
    AdminSettingsSeed(
        label="security",
        model=AdminSecuritySettingsOrmModel,
        save=lambda repo: repo.save_security,
        build=lambda: AdminSecuritySettings(
            id=1,
            enforce_totp=False,
            allow_rfid_login=cfg.security.allow_rfid_login,
            allow_local_login=True,
            enable_api_key_auth=False,
            min_password_length=cfg.security.min_pw_len,
            session_timeout_minutes=1440,
            totp_trusted_device_days=30,
            max_login_attempts=5,
            lockout_duration_minutes=15,
            token_max_lifetime_days=365,
            session_max_lifetime_days=30,
            enable_terminals=True,
            enable_infoscreen_weather=True,
            terminal_allowed_ips=[],
        ),
    ),
    AdminSettingsSeed(
        label="feature",
        model=AdminFeatureSettingsOrmModel,
        save=lambda repo: repo.save_features,
        build=lambda: AdminFeatureSettings(
            id=1,
            enable_email_notifications=True,
            enable_production_planning=True,
            allow_private_webhooks=True,
            enable_calculations=True,
            enable_checklists=True,
            enable_devices=True,
            enable_sequences=True,
            enable_todos=True,
        ),
    ),
    AdminSettingsSeed(
        label="general",
        model=AdminGeneralSettingsOrmModel,
        save=lambda repo: repo.save_general,
        build=lambda: AdminGeneralSettings(
            id=1,
            company_name=None,
            company_legal_name=None,
            company_logo_key=None,
            contact_email=None,
            imprint_url=None,
            privacy_url=None,
            support_url=None,
            product_number_pattern="",
            project_number_pattern="",
            allow_headless_projects=True,
            empty_value_placeholder="-",
            office_launcher_enabled=False,
            office_sharepoint_url="",
            currency=SERVER_DEFAULT_CURRENCY,
            default_language=Language(SERVER_DEFAULT_LANGUAGE),
            default_timezone=SERVER_DEFAULT_TIMEZONE,
            default_date_format=DateFormat(SERVER_DEFAULT_DATE_FORMAT),
        ),
    ),
    AdminSettingsSeed(
        label="branding",
        model=AdminBrandingSettingsOrmModel,
        save=lambda repo: repo.save_branding,
        build=lambda: AdminBrandingSettings(
            id=1,
            app_name="Glados",
            app_description=None,
            footer_text=None,
            logo_url=None,
            favicon_url=None,
            logo_key=None,
            favicon_key=None,
            login_background_video_key=None,
        ),
    ),
    AdminSettingsSeed(
        label="notification",
        model=AdminNotificationSettingsOrmModel,
        save=lambda repo: repo.save_notifications,
        build=lambda: AdminNotificationSettings(
            id=1,
            webhook_timeout_seconds=10,
        ),
    ),
    AdminSettingsSeed(
        label="maintenance",
        model=AdminMaintenanceSettingsOrmModel,
        save=lambda repo: repo.save_maintenance,
        build=lambda: AdminMaintenanceSettings(id=1, enabled=False, message=None, allowed_ips=[]),
    ),
    AdminSettingsSeed(
        label="retention",
        model=AdminRetentionSettingsOrmModel,
        save=lambda repo: repo.save_retention,
        build=lambda: AdminRetentionSettings(
            id=1,
            log_retention_days=90,
            audit_retention_days=365,
            soft_delete_cleanup_days=0,
            meeting_retention_days=0,
        ),
    ),
    AdminSettingsSeed(
        label="order",
        model=AdminOrderSettingsOrmModel,
        save=lambda repo: repo.save_orders,
        build=lambda: AdminOrderSettings(
            id=1,
            order_number_format="ORD-{yy}-{seq:05d}",
            part_number_format="PUR-{yy}-{seq:05d}",
            part_number_auto=True,
            part_number_editable=False,
            web_creation_allowed=True,
            pdm_part_number_pattern="",
            over_delivery_tolerance_percent=0.0,
            under_delivery_tolerance_percent=0.0,
            quote_request_number_format="RFQ-{yy}-{seq:05d}",
        ),
    ),
    AdminSettingsSeed(
        label="made item",
        model=AdminMadeItemSettingsOrmModel,
        save=lambda repo: repo.save_made_items,
        build=lambda: AdminMadeItemSettings(
            id=1,
            item_number_format="FAB-{yy}-{seq:05d}",
            lot_number_format="LOT-{yy}-{seq:05d}",
            calculation_number_format="CAL-{yy}-{seq:04d}",
            checklist_number_format="CHK-{yy}-{seq:04d}",
            sequence_number_format="SEQ-{yy}-{seq:04d}",
            meeting_number_format="MTG-{yy}-{seq:04d}",
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
        ),
    ),
    AdminSettingsSeed(
        label="PDM",
        model=AdminPdmSettingsOrmModel,
        save=lambda repo: repo.save_pdm,
        build=_pdm_defaults,
    ),
    AdminSettingsSeed(
        label="production",
        model=AdminProductionSettingsOrmModel,
        save=lambda repo: repo.save_production,
        build=lambda: AdminProductionSettings(
            id=1,
            production_order_number_format="PON-{yy}-{seq:05d}",
            default_weekly_hours={0: 480, 1: 480, 2: 480, 3: 480, 4: 480, 5: 0, 6: 0},
            default_external_lead_days=0,
            response_time_days=1,
            external_safety_margin_days=2,
            require_qa=False,
            frozen_window_hours=0,
            require_source_item_approval=False,
            assign_approved_material_to_item=False,
            overwrite_item_material_on_approval=False,
            external_first_step_needs_no_material=True,
        ),
    ),
    AdminSettingsSeed(
        label="banner",
        model=AdminBannerSettingsOrmModel,
        save=lambda repo: repo.save_banner,
        build=lambda: AdminBannerSettings(
            id=1,
            enabled=False,
            text="",
            severity=AnnouncementSeverity.INFO,
            shows_from=None,
            shows_until=None,
            dismissable=True,
            updated_at=now_utc(),
        ),
    ),
    AdminSettingsSeed(
        label="agent",
        model=AdminAgentSettingsOrmModel,
        save=lambda repo: repo.save_agents,
        build=lambda: AdminAgentSettings(id=1),
    ),
    AdminSettingsSeed(
        label="data import",
        model=AdminDataImportSettingsOrmModel,
        save=lambda repo: repo.save_data_import,
        build=_data_import_defaults,
    ),
    AdminSettingsSeed(
        label="EPLAN Data Portal",
        model=AdminEdpSettingsOrmModel,
        save=lambda repo: repo.save_edp,
        build=lambda: AdminEdpSettings(id=1),
    ),
    AdminSettingsSeed(
        label="stock service",
        model=AdminStockSettingsOrmModel,
        save=lambda repo: repo.save_stock,
        build=lambda: AdminStockSettings(id=1),
    ),
)
