"""initial schema

Revision ID: 0dcb223dd17a
Revises:
Create Date: 2026-11-16 10:25:05.476468

Creates the whole Glados schema as the ORM models describe it. On Postgres it
also enables pg_trgm and creates the GIN trigram indexes behind global search
and the log filters, which no model declares (see
autogenerate_filters.HAND_MAINTAINED_OBJECTS); other dialects skip them. It
inserts no data: InitDatabase seeds the system user, the settings singletons
and the print template slots at startup. Downgrade is refused.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0dcb223dd17a"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The columns behind the single-column trigram indexes, kept equal to
# autogenerate_filters.TRGM_INDEX_COLUMNS and LOG_TRGM_INDEX_COLUMNS.
_TRGM_COLUMNS: tuple[tuple[str, str], ...] = (
    ("product_table", "product_number"),
    ("product_table", "description"),
    ("project_table", "project_number"),
    ("project_table", "description"),
    ("bought_item_table", "article_name"),
    ("bought_item_table", "order_code_1"),
    ("bought_item_table", "order_code_2"),
    ("bought_item_table", "part_number"),
    ("bought_item_table", "gtin"),
    ("bought_item_table", "ean"),
    ("bought_item_table", "note"),
    ("made_item_table", "article_name"),
    ("made_item_table", "part_number"),
    ("made_item_table", "material"),
    ("made_item_table", "note"),
    ("source_item_table", "material"),
    ("source_item_table", "order_code_1"),
    ("source_item_table", "order_code_2"),
    ("source_item_table", "dimension"),
    ("source_item_table", "note"),
    ("order_table", "order_number"),
    ("order_table", "note"),
    ("order_table", "storage_place"),
    ("production_lot_table", "lot_number"),
    ("production_lot_table", "note"),
    ("production_order_table", "production_order_number"),
    ("production_order_table", "note"),
    ("calculation_table", "document_number"),
    ("calculation_table", "title"),
    ("checklist_table", "document_number"),
    ("checklist_table", "title"),
    ("log_table", "message"),
    ("log_table", "path"),
)

_BOUGHT_ITEM_SEARCH_INDEX = """
    CREATE INDEX IF NOT EXISTS ix_bought_item_trgm_search
    ON bought_item_table
    USING GIN ((
        order_code_1 || ' ' ||
        article_name || ' ' ||
        coalesce(order_code_2, '') || ' ' ||
        coalesce(part_number, '') || ' ' ||
        coalesce(gtin, '') || ' ' ||
        coalesce(ean, '') || ' ' ||
        coalesce(note, '')
    ) gin_trgm_ops)
"""


def _create_trigram_indexes() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(_BOUGHT_ITEM_SEARCH_INDEX)
    for table, column in _TRGM_COLUMNS:
        op.execute(
            f"CREATE INDEX IF NOT EXISTS ix_{table}_{column}_trgm "
            f"ON {table} USING GIN ({column} gin_trgm_ops)"
        )


def upgrade() -> None:
    op.create_table(
        "admin_agent_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("token_max_lifetime_days", sa.Integer(), server_default="30", nullable=False),
        sa.Column("token_idle_revoke_days", sa.Integer(), server_default="14", nullable=False),
        sa.Column("include_person_names", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("include_costs", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("allowed_origins", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("calls_per_minute", sa.Integer(), server_default="120", nullable=False),
        sa.Column("drafts_per_hour", sa.Integer(), server_default="20", nullable=False),
        sa.Column("approved_providers", sa.String(), server_default="", nullable=False),
        sa.Column("ai_policy_url", sa.String(), nullable=True),
        sa.Column("processing_approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_admin_agent_settings_public_id"),
        "admin_agent_settings",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "admin_auth_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ldap_enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("ldap_host", sa.String(), server_default="", nullable=False),
        sa.Column("ldap_port", sa.Integer(), server_default="636", nullable=False),
        sa.Column("ldap_use_ssl", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("ldap_start_tls", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("ldap_verify_certificate", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("ldap_domain", sa.String(), server_default="", nullable=False),
        sa.Column("ldap_timeout_seconds", sa.Integer(), server_default="5", nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_admin_auth_settings_public_id"), "admin_auth_settings", ["public_id"], unique=True
    )
    op.create_table(
        "admin_banner_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("text", sa.String(), server_default="", nullable=False),
        sa.Column("severity", sa.String(), server_default="info", nullable=False),
        sa.Column("shows_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("shows_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissable", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_admin_banner_settings_public_id"),
        "admin_banner_settings",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "admin_branding_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("app_name", sa.String(), server_default="Glados", nullable=False),
        sa.Column("app_description", sa.String(), nullable=True),
        sa.Column("footer_text", sa.String(), nullable=True),
        sa.Column("logo_url", sa.String(), nullable=True),
        sa.Column("favicon_url", sa.String(), nullable=True),
        sa.Column("logo_key", sa.String(), nullable=True),
        sa.Column("favicon_key", sa.String(), nullable=True),
        sa.Column("login_background_video_key", sa.String(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_admin_branding_settings_public_id"),
        "admin_branding_settings",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "admin_data_import_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profiles", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_admin_data_import_settings_public_id"),
        "admin_data_import_settings",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "admin_edp_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "base_url",
            sa.String(),
            server_default="https://dataportal.eplan.com/api",
            nullable=False,
        ),
        sa.Column(
            "pat",
            sa.String(),
            nullable=True,
        ),
        sa.Column("default_article_group_ids", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("language", sa.String(length=8), server_default="de_DE", nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_admin_edp_settings_public_id"), "admin_edp_settings", ["public_id"], unique=True
    )
    op.create_table(
        "admin_feature_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "enable_email_notifications", sa.Boolean(), server_default="true", nullable=False
        ),
        sa.Column(
            "enable_production_planning", sa.Boolean(), server_default="true", nullable=False
        ),
        sa.Column("allow_private_webhooks", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("enable_calculations", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("enable_checklists", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("enable_devices", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("enable_sequences", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("enable_todos", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_admin_feature_settings_public_id"),
        "admin_feature_settings",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "admin_general_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_name", sa.String(), nullable=True),
        sa.Column("company_legal_name", sa.String(), nullable=True),
        sa.Column("company_logo_key", sa.String(), nullable=True),
        sa.Column("contact_email", sa.String(), nullable=True),
        sa.Column("imprint_url", sa.String(), nullable=True),
        sa.Column("privacy_url", sa.String(), nullable=True),
        sa.Column("support_url", sa.String(), nullable=True),
        sa.Column("product_number_pattern", sa.String(), server_default="", nullable=False),
        sa.Column("project_number_pattern", sa.String(), server_default="", nullable=False),
        sa.Column("allow_headless_projects", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("empty_value_placeholder", sa.String(), server_default="-", nullable=False),
        sa.Column("office_launcher_enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("office_sharepoint_url", sa.String(), server_default="", nullable=False),
        sa.Column("currency", sa.String(), server_default="EUR", nullable=False),
        sa.Column("default_language", sa.String(), server_default="enGB", nullable=False),
        sa.Column("default_timezone", sa.String(), server_default="Europe/Vienna", nullable=False),
        sa.Column("default_date_format", sa.String(), server_default="iso", nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_admin_general_settings_public_id"),
        "admin_general_settings",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "admin_host_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_admin_host_settings_public_id"), "admin_host_settings", ["public_id"], unique=True
    )
    op.create_table(
        "admin_made_item_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "item_number_format", sa.String(), server_default="FAB-{yy}-{seq:05d}", nullable=False
        ),
        sa.Column(
            "lot_number_format", sa.String(), server_default="LOT-{yy}-{seq:05d}", nullable=False
        ),
        sa.Column(
            "calculation_number_format",
            sa.String(),
            server_default="CAL-{yy}-{seq:04d}",
            nullable=False,
        ),
        sa.Column(
            "checklist_number_format",
            sa.String(),
            server_default="CHK-{yy}-{seq:04d}",
            nullable=False,
        ),
        sa.Column(
            "sequence_number_format",
            sa.String(),
            server_default="SEQ-{yy}-{seq:04d}",
            nullable=False,
        ),
        sa.Column(
            "meeting_number_format",
            sa.String(),
            server_default="MTG-{yy}-{seq:04d}",
            nullable=False,
        ),
        sa.Column("part_number_auto", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("part_number_editable", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("revision_start", sa.String(), server_default="0", nullable=False),
        sa.Column("revision_separator", sa.String(), server_default=":", nullable=False),
        sa.Column(
            "revision_skip_ambiguous_letters", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column(
            "revision_only_newest_editable", sa.Boolean(), server_default="true", nullable=False
        ),
        sa.Column(
            "revision_predecessor_status_web", sa.String(), server_default="ask", nullable=False
        ),
        sa.Column(
            "revision_predecessor_status_pdm",
            sa.String(),
            server_default="replaced",
            nullable=False,
        ),
        sa.Column(
            "revision_field_policy",
            sa.JSON(),
            server_default=(
                '[{"field": "article_name", "web_requires_revision": true, '
                '"pdm_update_in_place": false}, {"field": "material", "web_requires_revision": '
                'true, "pdm_update_in_place": false}, {"field": "mass", "web_requires_revision": '
                'true, "pdm_update_in_place": true}, {"field": "base_size", '
                '"web_requires_revision": true, "pdm_update_in_place": false}, {"field": "note", '
                '"web_requires_revision": false, "pdm_update_in_place": true}, {"field": '
                '"weblink", "web_requires_revision": false, "pdm_update_in_place": true}, '
                '{"field": "article_group_ids", "web_requires_revision": false, '
                '"pdm_update_in_place": true}, {"field": "bought_item_id", '
                '"web_requires_revision": true, "pdm_update_in_place": false}, {"field": '
                '"source_item_id", "web_requires_revision": true, "pdm_update_in_place": false}, '
                '{"field": "customer_id", "web_requires_revision": true, "pdm_update_in_place": '
                'true}, {"field": "customer_part_number", "web_requires_revision": true, '
                '"pdm_update_in_place": true}, {"field": "customer_revision", '
                '"web_requires_revision": true, "pdm_update_in_place": true}, {"field": '
                '"revision_date", "web_requires_revision": false, "pdm_update_in_place": true}, '
                '{"field": "revision_note", "web_requires_revision": false, '
                '"pdm_update_in_place": true}, {"field": "processes", "web_requires_revision": '
                'false, "pdm_update_in_place": false}]'
            ),
            nullable=False,
        ),
        sa.Column("web_creation_allowed", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("pdm_part_number_pattern", sa.String(), server_default="", nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_admin_made_item_settings_public_id"),
        "admin_made_item_settings",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "admin_mail_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("host", sa.String(), server_default="localhost", nullable=False),
        sa.Column("port", sa.Integer(), server_default="587", nullable=False),
        sa.Column("user", sa.String(), server_default="", nullable=False),
        sa.Column(
            "password",
            sa.String(),
            nullable=True,
        ),
        sa.Column("from_address", sa.String(), nullable=True),
        sa.Column("use_tls", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("use_ssl", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("verify_certificate", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("from_display_name", sa.String(), server_default="", nullable=False),
        sa.Column("reply_to", sa.String(), nullable=True),
        sa.Column("send_limit_per_hour", sa.Integer(), server_default="20", nullable=False),
        sa.Column("send_lock_minutes", sa.Integer(), server_default="60", nullable=False),
        sa.Column("alert_recipients", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("attachment_limit_mb", sa.Integer(), server_default="10", nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_admin_mail_settings_public_id"), "admin_mail_settings", ["public_id"], unique=True
    )
    op.create_table(
        "admin_mail_template",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("language", sa.String(), nullable=False),
        sa.Column("subject", sa.String(), server_default="", nullable=False),
        sa.Column("body", sa.Text(), server_default="", nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("kind", "language", name="uq_admin_mail_template_kind_language"),
    )
    op.create_index(
        op.f("ix_admin_mail_template_public_id"), "admin_mail_template", ["public_id"], unique=True
    )
    op.create_table(
        "admin_maintenance_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("message", sa.String(), nullable=True),
        sa.Column("allowed_ips", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_admin_maintenance_settings_public_id"),
        "admin_maintenance_settings",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "admin_notification_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("webhook_timeout_seconds", sa.Integer(), server_default="10", nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_admin_notification_settings_public_id"),
        "admin_notification_settings",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "admin_order_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "order_number_format", sa.String(), server_default="ORD-{yy}-{seq:05d}", nullable=False
        ),
        sa.Column(
            "part_number_format", sa.String(), server_default="PUR-{yy}-{seq:05d}", nullable=False
        ),
        sa.Column("part_number_auto", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("part_number_editable", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("web_creation_allowed", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("pdm_part_number_pattern", sa.String(), server_default="", nullable=False),
        sa.Column(
            "over_delivery_tolerance_percent",
            sa.Numeric(precision=7, scale=3, asdecimal=False),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "under_delivery_tolerance_percent",
            sa.Numeric(precision=7, scale=3, asdecimal=False),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "quote_request_number_format",
            sa.String(),
            server_default="RFQ-{yy}-{seq:05d}",
            nullable=False,
        ),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_admin_order_settings_public_id"),
        "admin_order_settings",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "admin_pdm_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "made_item_variable_map",
            sa.JSON(),
            server_default=(
                '{"part_number": "PDM.PartNumber", "revision": "PDM.Revision", "revision_date": '
                '"PDM.RevisionDate", "revision_note": "PDM.RevisionNote", "article_name": '
                '"Glados.ArticleName", "material": "Glados.Material", "mass": "Glados.Mass", '
                '"base_size": "Glados.BaseSize", "note": "Glados.Note", "weblink": '
                '"Glados.Weblink", "article_group_ids": "Glados.ArticleGroupIds", '
                '"bought_item_id": "Glados.BoughtItemId", "source_item_id": '
                '"Glados.SourceItemId", "customer_id": "Glados.CustomerId", '
                '"customer_part_number": "Glados.CustomerPartNumber", "customer_revision": '
                '"Glados.CustomerRevision", "processes": "Glados.Processes", '
                '"article_group_names": "Glados.ArticleGroupNames", "process_names": '
                '"Glados.ProcessNames", "source_item_name": "Glados.SourceItemName", '
                '"customer_name": "Glados.CustomerName", "feature_tree_representation": '
                '"Glados.FeatureTreeRepresentation", "kind": "Glados.Kind", "glados_ids": '
                '"Glados.Ids", "newest_revision_sync_state": "Glados.NewestRevisionSyncState", '
                '"newest_revision_synced_at": "Glados.NewestRevisionSyncedAt"}'
            ),
            nullable=False,
        ),
        sa.Column(
            "bought_item_variable_map",
            sa.JSON(),
            server_default=(
                '{"part_number": "PDM.PartNumber", "revision": "PDM.Revision", "article_name": '
                '"Glados.ArticleName", "order_code_1": "Glados.OrderCode1", "order_code_2": '
                '"Glados.OrderCode2", "gtin": "Glados.Gtin", "ean": "Glados.Ean", '
                '"tariff_number": "Glados.TariffNumber", "mass": "Glados.Mass", "note": '
                '"Glados.Note", "weblink": "Glados.Weblink", "manufacturer_id": '
                '"Glados.ManufacturerId", "article_group_ids": "Glados.ArticleGroupIds", '
                '"edp_part_id": "Glados.EdpPartId", "manufacturer_name": '
                '"Glados.ManufacturerName", "article_group_names": "Glados.ArticleGroupNames", '
                '"feature_tree_representation": "Glados.FeatureTreeRepresentation", "kind": '
                '"Glados.Kind", "glados_ids": "Glados.Ids", "newest_revision_sync_state": '
                '"Glados.NewestRevisionSyncState", "newest_revision_synced_at": '
                '"Glados.NewestRevisionSyncedAt"}'
            ),
            nullable=False,
        ),
        sa.Column("enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("base_url", sa.String(), server_default="", nullable=False),
        sa.Column("vault_name", sa.String(), server_default="", nullable=False),
        sa.Column("username", sa.String(), server_default="", nullable=False),
        sa.Column(
            "password",
            sa.String(),
            nullable=True,
        ),
        sa.Column("verify_certificate", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), server_default="15", nullable=False),
        sa.Column(
            "session_token",
            sa.String(),
            nullable=True,
        ),
        sa.Column("session_user_id", sa.Integer(), nullable=True),
        sa.Column("session_obtained_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("watched_folders", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("made_released_state_ids", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("made_obsolete_state_ids", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("bought_released_state_ids", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("bought_obsolete_state_ids", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("made_replaced_state_ids", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("bought_replaced_state_ids", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("document_released_state_ids", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("poll_interval_minutes", sa.Integer(), server_default="15", nullable=False),
        sa.Column("cold_folder_max_multiplier", sa.Integer(), server_default="8", nullable=False),
        sa.Column("ingest_concurrency", sa.Integer(), server_default="4", nullable=False),
        sa.Column("vault_id", sa.String(), server_default="", nullable=False),
        sa.Column("cad_items_read_only", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("addin_language", sa.String(), server_default="", nullable=False),
        sa.Column("last_poll_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_poll_error", sa.Text(), nullable=True),
        sa.Column("last_poll_summary", sa.Text(), nullable=True),
        sa.Column("writeback_enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("made_item_extensions", sa.JSON(), server_default='["sldprt"]', nullable=False),
        sa.Column(
            "bought_item_extensions",
            sa.JSON(),
            server_default='["sldprt", "sldasm"]',
            nullable=False,
        ),
        sa.Column(
            "document_categories",
            sa.JSON(),
            server_default='{"pdf": "drawing", "dxf": "dxf", "step": "step", "stp": "step"}',
            nullable=False,
        ),
        sa.Column("document_excluded_kinds", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("thumbnails_enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("stuck_after_days", sa.Integer(), server_default="7", nullable=False),
        sa.Column("reconcile_requested_deep", sa.Boolean(), nullable=True),
        sa.Column(
            "required_fields",
            sa.JSON(),
            server_default='{"made": ["material", "fabrication_step"], "bought": ["revision"]}',
            nullable=False,
        ),
        sa.Column("set_approver_from_pdm", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "made_feature_tree_template",
            sa.String(),
            server_default=(
                '$PRP:"PDM.PartNumber" Rev$PRP:"PDM.Revision" ($PRP:"Glados.ArticleName")'
            ),
            nullable=False,
        ),
        sa.Column(
            "bought_feature_tree_template",
            sa.String(),
            server_default=(
                '$PRP:"Glados.ArticleName" - $PRP:"Glados.OrderCode1" - '
                '$PRP:"Glados.ManufacturerName"'
            ),
            nullable=False,
        ),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_admin_pdm_settings_public_id"), "admin_pdm_settings", ["public_id"], unique=True
    )
    op.create_table(
        "admin_retention_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("log_retention_days", sa.Integer(), server_default="90", nullable=False),
        sa.Column("audit_retention_days", sa.Integer(), server_default="365", nullable=False),
        sa.Column("soft_delete_cleanup_days", sa.Integer(), server_default="0", nullable=False),
        sa.Column("meeting_retention_days", sa.Integer(), server_default="0", nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_admin_retention_settings_public_id"),
        "admin_retention_settings",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "admin_security_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("enforce_totp", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("allow_rfid_login", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("allow_local_login", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("enable_api_key_auth", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("min_password_length", sa.Integer(), server_default="8", nullable=False),
        sa.Column("session_timeout_minutes", sa.Integer(), server_default="1440", nullable=False),
        sa.Column("totp_trusted_device_days", sa.Integer(), server_default="30", nullable=False),
        sa.Column("max_login_attempts", sa.Integer(), server_default="5", nullable=False),
        sa.Column("lockout_duration_minutes", sa.Integer(), server_default="15", nullable=False),
        sa.Column("token_max_lifetime_days", sa.Integer(), server_default="365", nullable=False),
        sa.Column("session_max_lifetime_days", sa.Integer(), server_default="30", nullable=False),
        sa.Column("enable_terminals", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("enable_infoscreen_weather", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("terminal_allowed_ips", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_admin_security_settings_public_id"),
        "admin_security_settings",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "admin_settings_audit",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("changed_by_username", sa.String(), nullable=True),
        sa.Column("settings_domain", sa.String(), nullable=False),
        sa.Column("summary", sa.String(), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_admin_settings_audit_public_id"),
        "admin_settings_audit",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_admin_settings_audit_settings_domain"),
        "admin_settings_audit",
        ["settings_domain"],
        unique=False,
    )
    op.create_table(
        "admin_stock_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("service_url", sa.String(), server_default="", nullable=False),
        sa.Column(
            "api_key",
            sa.String(),
            nullable=True,
        ),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_admin_stock_settings_public_id"),
        "admin_stock_settings",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "admin_storage_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(), server_default="local", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("endpoint_url", sa.String(), nullable=True),
        sa.Column("public_endpoint_url", sa.String(), nullable=True),
        sa.Column("bucket_name", sa.String(), nullable=True),
        sa.Column(
            "access_key",
            sa.String(),
            nullable=True,
        ),
        sa.Column(
            "secret_key",
            sa.String(),
            nullable=True,
        ),
        sa.Column("region", sa.String(), nullable=True),
        sa.Column("use_ssl", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("backup_enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("backup_path", sa.String(), nullable=True),
        sa.Column("backup_cron", sa.String(), nullable=True),
        sa.Column("backup_retention_count", sa.Integer(), server_default="7", nullable=False),
        sa.Column("disk_warning_percent", sa.Integer(), server_default="90", nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_admin_storage_settings_public_id"),
        "admin_storage_settings",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "admin_time_tracking_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("service_url", sa.String(), server_default="", nullable=False),
        sa.Column(
            "api_key",
            sa.String(),
            nullable=True,
        ),
        sa.Column("credential_public_key", sa.String(length=128), nullable=True),
        sa.Column("credential_key_id", sa.String(length=64), nullable=True),
        sa.Column("provider_label", sa.String(length=64), nullable=True),
        sa.Column("privacy_policy_url", sa.String(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_admin_time_tracking_settings_public_id"),
        "admin_time_tracking_settings",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "agent_call_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("called_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_kind", sa.String(length=16), nullable=False),
        sa.Column("pat_id", sa.Integer(), nullable=True),
        sa.Column("api_key_id", sa.Integer(), nullable=True),
        sa.Column("token_name", sa.String(), nullable=False),
        sa.Column("tool", sa.String(length=64), nullable=False),
        sa.Column("arguments", sa.JSON(), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("created_refs", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_agent_call_table_api_key_id_called_at",
        "agent_call_table",
        ["api_key_id", "called_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_call_table_called_at"), "agent_call_table", ["called_at"], unique=False
    )
    op.create_index(
        "ix_agent_call_table_pat_id_called_at",
        "agent_call_table",
        ["pat_id", "called_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_call_table_public_id"), "agent_call_table", ["public_id"], unique=True
    )
    op.create_index(op.f("ix_agent_call_table_tool"), "agent_call_table", ["tool"], unique=False)
    op.create_index(
        "ix_agent_call_table_user_id_called_at",
        "agent_call_table",
        ["user_id", "called_at"],
        unique=False,
    )
    op.create_table(
        "backup_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slot", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trigger", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("db_key", sa.String(), nullable=True),
        sa.Column("files_key", sa.String(), nullable=True),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("worker", sa.String(), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_backup_runs_public_id"), "backup_runs", ["public_id"], unique=True)
    op.create_index(op.f("ix_backup_runs_slot"), "backup_runs", ["slot"], unique=True)
    op.create_table(
        "email_notification_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("receiver_id", sa.Integer(), nullable=False),
        sa.Column("demand_item_id", sa.Integer(), nullable=True),
        sa.Column("order_item_id", sa.Integer(), nullable=True),
        sa.Column("meeting_id", sa.Integer(), nullable=True),
        sa.Column("message", sa.String(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_email_notification_table_public_id"),
        "email_notification_table",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "event_outbox_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("payload", sa.String(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.String(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_event_outbox_table_event_id"), "event_outbox_table", ["event_id"], unique=True
    )
    op.create_index(
        op.f("ix_event_outbox_table_public_id"), "event_outbox_table", ["public_id"], unique=True
    )
    op.create_index(
        op.f("ix_event_outbox_table_published_at"),
        "event_outbox_table",
        ["published_at"],
        unique=False,
    )
    op.create_index(
        "ix_event_outbox_table_unpublished",
        "event_outbox_table",
        ["id"],
        unique=False,
        postgresql_where=sa.text("published_at IS NULL"),
        sqlite_where=sa.text("published_at IS NULL"),
    )
    op.create_table(
        "infoscreen_display_default",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("display_schedule", sa.JSON(), nullable=True),
        sa.Column("off_on_holidays", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_infoscreen_display_default_public_id"),
        "infoscreen_display_default",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "log_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("username", sa.String(), nullable=True),
        sa.Column("level", sa.String(length=16), nullable=False),
        sa.Column("message", sa.String(), nullable=True),
        sa.Column("method", sa.String(length=10), nullable=True),
        sa.Column("path", sa.String(), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_log_table_level"), "log_table", ["level"], unique=False)
    op.create_index(op.f("ix_log_table_public_id"), "log_table", ["public_id"], unique=True)
    op.create_index(op.f("ix_log_table_request_id"), "log_table", ["request_id"], unique=False)
    op.create_index(op.f("ix_log_table_timestamp"), "log_table", ["timestamp"], unique=False)
    op.create_index(op.f("ix_log_table_user_id"), "log_table", ["user_id"], unique=False)
    op.create_table(
        "notification_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("message", sa.String(), nullable=False),
        sa.Column("is_read", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("demand_item_id", sa.Integer(), nullable=True),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("meeting_id", sa.Integer(), nullable=True),
        sa.Column("source_event_id", sa.String(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_notification_table_public_id"), "notification_table", ["public_id"], unique=True
    )
    op.create_index(
        op.f("ix_notification_table_user_id"), "notification_table", ["user_id"], unique=False
    )
    op.create_index(
        "uq_notification_table_source_event_id_user_id",
        "notification_table",
        ["source_event_id", "user_id"],
        unique=True,
    )
    op.create_table(
        "number_counter_table",
        sa.Column("family", sa.String(length=32), nullable=False),
        sa.Column("prefix", sa.String(length=255), nullable=False),
        sa.Column("last_value", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("family", "prefix"),
    )
    op.create_index(
        op.f("ix_number_counter_table_public_id"),
        "number_counter_table",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "part_number_registry",
        sa.Column("part_number", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("part_number"),
    )
    op.create_index(
        op.f("ix_part_number_registry_public_id"),
        "part_number_registry",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "pdm_document_link_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("item_file_id", sa.Integer(), nullable=True),
        sa.Column("vault_id", sa.String(), nullable=False),
        sa.Column("file_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("item_picture_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_pdm_document_link_item_file_id",
        "pdm_document_link_table",
        ["item_file_id"],
        unique=False,
    )
    op.create_index(
        "ix_pdm_document_link_item_picture_id",
        "pdm_document_link_table",
        ["item_picture_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_pdm_document_link_table_public_id"),
        "pdm_document_link_table",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        "uq_pdm_document_link_vault_file",
        "pdm_document_link_table",
        ["vault_id", "file_id"],
        unique=True,
    )
    op.create_table(
        "pdm_file_snapshot_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("vault_id", sa.String(), nullable=False),
        sa.Column("file_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("path", sa.String(), nullable=False),
        sa.Column("parent_folder_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("state_id", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_ingested_version", sa.Integer(), nullable=True),
        sa.Column("sync_state", sa.String(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("part_number", sa.String(), nullable=True),
        sa.Column("revision", sa.String(), nullable=True),
        sa.Column("item_id", sa.Integer(), nullable=True),
        sa.Column("parked_payload", sa.JSON(), nullable=True),
        sa.Column("article_name", sa.String(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_pdm_file_snapshot_last_seen_at",
        "pdm_file_snapshot_table",
        ["last_seen_at"],
        unique=False,
    )
    op.create_index(
        "ix_pdm_file_snapshot_sync_state", "pdm_file_snapshot_table", ["sync_state"], unique=False
    )
    op.create_index(
        op.f("ix_pdm_file_snapshot_table_public_id"),
        "pdm_file_snapshot_table",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        "ix_pdm_file_snapshot_vault_name_lower",
        "pdm_file_snapshot_table",
        ["vault_id", sa.literal_column("lower(name)")],
        unique=False,
    )
    op.create_index(
        "ix_pdm_file_snapshot_vault_parent_folder",
        "pdm_file_snapshot_table",
        ["vault_id", "parent_folder_id"],
        unique=False,
    )
    op.create_index(
        "uq_pdm_file_snapshot_vault_file",
        "pdm_file_snapshot_table",
        ["vault_id", "file_id"],
        unique=True,
    )
    op.create_table(
        "pdm_folder_poll_state_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("vault_id", sa.String(), nullable=False),
        sa.Column("folder_key", sa.String(), nullable=False),
        sa.Column("consecutive_unchanged_runs", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_pdm_folder_poll_state_table_public_id"),
        "pdm_folder_poll_state_table",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        "uq_pdm_folder_poll_state_vault_folder",
        "pdm_folder_poll_state_table",
        ["vault_id", "folder_key"],
        unique=True,
    )
    op.create_table(
        "pdm_sync_run_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trigger", sa.String(), nullable=False),
        sa.Column("files_seen", sa.Integer(), nullable=False),
        sa.Column("changed", sa.Integer(), nullable=False),
        sa.Column("ingested", sa.Integer(), nullable=False),
        sa.Column("skipped", sa.Integer(), nullable=False),
        sa.Column("conflicts", sa.Integer(), nullable=False),
        sa.Column("errors", sa.Integer(), nullable=False),
        sa.Column("missing", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("folders_walked", sa.Integer(), server_default="0", nullable=False),
        sa.Column("folders_skipped_cold", sa.Integer(), server_default="0", nullable=False),
        sa.Column("phase", sa.String(), nullable=True),
        sa.Column("current_path", sa.String(), nullable=True),
        sa.Column("files_queued", sa.Integer(), server_default="0", nullable=False),
        sa.Column("files_processed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("progress_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("change_reason", sa.String(), nullable=True),
        sa.Column("change_state", sa.String(), nullable=True),
        sa.Column("requested_by_name", sa.String(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_pdm_sync_run_started_at", "pdm_sync_run_table", ["started_at"], unique=False
    )
    op.create_index(
        op.f("ix_pdm_sync_run_table_public_id"), "pdm_sync_run_table", ["public_id"], unique=True
    )
    op.create_table(
        "user_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("token_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_logged_in", sa.DateTime(timezone=True), nullable=True),
        sa.Column("password_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("full_name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("rfid_lookup", sa.String(), nullable=True),
        sa.Column("language", sa.String(), server_default="enGB", nullable=False),
        sa.Column("date_format", sa.String(), server_default="iso", nullable=False),
        sa.Column("start_page", sa.String(), server_default="dashboard", nullable=False),
        sa.Column("theme_preset", sa.String(), server_default="Aura", nullable=False),
        sa.Column("theme_surface", sa.String(), server_default="slate", nullable=False),
        sa.Column("theme_primary", sa.String(), server_default="emerald", nullable=False),
        sa.Column("theme_dark_mode", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("button_flat_style", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("table_gridlines", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("table_striped_rows", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_systemuser", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_service_account", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_shared_account", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("auth_provider", sa.String(), server_default="local", nullable=False),
        sa.Column("permissions", sa.JSON(), server_default="[]", nullable=False),
        sa.Column(
            "totp_secret",
            sa.String(),
            nullable=True,
        ),
        sa.Column("totp_enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("avatar_key", sa.String(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_table_email"), "user_table", ["email"], unique=True)
    op.create_index(op.f("ix_user_table_public_id"), "user_table", ["public_id"], unique=True)
    op.create_index(op.f("ix_user_table_username"), "user_table", ["username"], unique=True)
    op.create_index(
        "uq_user_rfid_lookup_active",
        "user_table",
        ["rfid_lookup"],
        unique=True,
        postgresql_where=sa.text("rfid_lookup IS NOT NULL"),
        sqlite_where=sa.text("rfid_lookup IS NOT NULL"),
    )
    op.create_index(
        "uq_user_single_systemuser",
        "user_table",
        ["is_systemuser"],
        unique=True,
        postgresql_where=sa.text("is_systemuser IS true"),
        sqlite_where=sa.text("is_systemuser = 1"),
    )
    op.create_table(
        "acknowledgements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("text", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("show_when", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["user_table.id"],
            name="fk_acknowledgements_created_by_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_acknowledgements_created_by_id"),
        "acknowledgements",
        ["created_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_acknowledgements_public_id"), "acknowledgements", ["public_id"], unique=True
    )
    op.create_table(
        "agent_created_record",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("call_id", sa.Integer(), nullable=False),
        sa.Column("ref", sa.String(length=80), nullable=False),
        sa.Column("called_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["call_id"],
            ["agent_call_table.id"],
            name="fk_agent_created_record_call_id_agent_call_table",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_agent_created_record_call_id"), "agent_created_record", ["call_id"], unique=False
    )
    op.create_index(
        op.f("ix_agent_created_record_called_at"),
        "agent_created_record",
        ["called_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_created_record_public_id"),
        "agent_created_record",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_agent_created_record_ref"), "agent_created_record", ["ref"], unique=False
    )
    op.create_table(
        "api_key_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("token_prefix", sa.String(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("permissions", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["user_table.id"], name="fk_api_key_table_created_by_id_user_table"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user_table.id"], name="fk_api_key_table_user_id_user_table"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(
        op.f("ix_api_key_table_created_by_id"), "api_key_table", ["created_by_id"], unique=False
    )
    op.create_index(op.f("ix_api_key_table_public_id"), "api_key_table", ["public_id"], unique=True)
    op.create_index(
        op.f("ix_api_key_table_token_hash"), "api_key_table", ["token_hash"], unique=True
    )
    op.create_table(
        "article_group_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "changes",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column("archived", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("name", sa.JSON(), nullable=False),
        sa.Column("label_color", sa.String(), nullable=False),
        sa.Column("label_font_color", sa.String(), server_default="#000000", nullable=False),
        sa.Column("description", sa.JSON(), nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["changed_by_id"], ["user_table.id"], name="fk_article_group_table_changed_by_id"
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"], ["user_table.id"], name="fk_article_group_creator_id"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_article_group_table_changed_by_id"),
        "article_group_table",
        ["changed_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_article_group_table_creator_id"),
        "article_group_table",
        ["creator_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_article_group_table_public_id"), "article_group_table", ["public_id"], unique=True
    )
    op.create_table(
        "bought_item_demand_bucket_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("color", sa.String(), nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["creator_id"], ["user_table.id"], name="fk_bought_item_demand_bucket_creator_id"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_bought_item_demand_bucket_name"),
    )
    op.create_index(
        op.f("ix_bought_item_demand_bucket_table_creator_id"),
        "bought_item_demand_bucket_table",
        ["creator_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_bought_item_demand_bucket_table_public_id"),
        "bought_item_demand_bucket_table",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "customer_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "changes",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column("archived", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("legal_name", sa.String(), nullable=True),
        sa.Column("vat_id", sa.String(), nullable=True),
        sa.Column("level", sa.String(), server_default="B", nullable=False),
        sa.Column("street", sa.String(), nullable=True),
        sa.Column("city", sa.String(), nullable=True),
        sa.Column("country", sa.String(), nullable=True),
        sa.Column("postal_code", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("weblink", sa.String(), nullable=True),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("edit_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["changed_by_id"], ["user_table.id"], name="fk_customer_table_changed_by_id"
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"], ["user_table.id"], name="fk_customer_table_creator_id_user_table"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_customer_table_changed_by_id"), "customer_table", ["changed_by_id"], unique=False
    )
    op.create_index(
        op.f("ix_customer_table_creator_id"), "customer_table", ["creator_id"], unique=False
    )
    op.create_index(op.f("ix_customer_table_name"), "customer_table", ["name"], unique=False)
    op.create_index(
        op.f("ix_customer_table_public_id"), "customer_table", ["public_id"], unique=True
    )
    op.create_index(
        "uq_customer_vat_id_active",
        "customer_table",
        ["vat_id"],
        unique=True,
        postgresql_where=sa.text("archived IS false"),
        sqlite_where=sa.text("archived = 0"),
    )
    op.create_table(
        "idempotency_key_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("route", sa.String(), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("resources", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user_table.id"],
            name="fk_idempotency_key_table_user_id_user_table",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "key", name="uq_idempotency_key_table_user_id_key"),
    )
    op.create_index(
        op.f("ix_idempotency_key_table_created_at"),
        "idempotency_key_table",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_idempotency_key_table_public_id"),
        "idempotency_key_table",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_idempotency_key_table_user_id"), "idempotency_key_table", ["user_id"], unique=False
    )
    op.create_table(
        "infoscreen_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "changes",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column("archived", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("color_mode", sa.String(), server_default="dark", nullable=False),
        sa.Column("theme_preset", sa.String(), nullable=True),
        sa.Column("primary_color", sa.String(), nullable=True),
        sa.Column("rotation_seconds", sa.Integer(), server_default="30", nullable=False),
        sa.Column("show_banner", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("pages", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("show_header", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "header",
            sa.JSON(),
            server_default=(
                '{"left": ["logo", "title"], "center": [], "right": ["clock"], "text": null}'
            ),
            nullable=False,
        ),
        sa.Column("show_footer", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "footer",
            sa.JSON(),
            server_default='{"left": [], "center": [], "right": ["last_updated"], "text": null}',
            nullable=False,
        ),
        sa.Column("language", sa.String(), nullable=True),
        sa.Column(
            "display_schedule_mode", sa.String(length=16), server_default="default", nullable=False
        ),
        sa.Column("display_schedule", sa.JSON(), nullable=True),
        sa.Column("off_on_holidays", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["changed_by_id"], ["user_table.id"], name="fk_infoscreen_table_changed_by_id"
        ),
        sa.ForeignKeyConstraint(["creator_id"], ["user_table.id"], name="fk_infoscreen_creator_id"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_infoscreen_table_changed_by_id"),
        "infoscreen_table",
        ["changed_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_infoscreen_table_creator_id"), "infoscreen_table", ["creator_id"], unique=False
    )
    op.create_index(
        op.f("ix_infoscreen_table_public_id"), "infoscreen_table", ["public_id"], unique=True
    )
    op.create_index(
        "uq_infoscreen_name_active",
        "infoscreen_table",
        ["name"],
        unique=True,
        postgresql_where=sa.text("archived IS false"),
        sqlite_where=sa.text("archived = 0"),
    )
    op.create_table(
        "machine_pool_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "changes",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column("archived", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["changed_by_id"], ["user_table.id"], name="fk_machine_pool_table_changed_by_id"
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"], ["user_table.id"], name="fk_machine_pool_creator_id"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_machine_pool_table_changed_by_id"),
        "machine_pool_table",
        ["changed_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_machine_pool_table_creator_id"), "machine_pool_table", ["creator_id"], unique=False
    )
    op.create_index(
        op.f("ix_machine_pool_table_name"), "machine_pool_table", ["name"], unique=False
    )
    op.create_index(
        op.f("ix_machine_pool_table_public_id"), "machine_pool_table", ["public_id"], unique=True
    )
    op.create_table(
        "made_item_demand_bucket_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("color", sa.String(), nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["creator_id"], ["user_table.id"], name="fk_made_item_demand_bucket_creator_id"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_made_item_demand_bucket_name"),
    )
    op.create_index(
        op.f("ix_made_item_demand_bucket_table_creator_id"),
        "made_item_demand_bucket_table",
        ["creator_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_made_item_demand_bucket_table_public_id"),
        "made_item_demand_bucket_table",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "pat_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("token_prefix", sa.String(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("permissions", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user_table.id"], name="fk_pat_table_user_id_user_table"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pat_table_public_id"), "pat_table", ["public_id"], unique=True)
    op.create_index(op.f("ix_pat_table_token_hash"), "pat_table", ["token_hash"], unique=True)
    op.create_index(op.f("ix_pat_table_user_id"), "pat_table", ["user_id"], unique=False)
    op.create_table(
        "pdm_reconciliation_finding_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=True),
        sa.Column("item_id", sa.Integer(), nullable=True),
        sa.Column("file_id", sa.Integer(), nullable=True),
        sa.Column("part_number", sa.String(), nullable=True),
        sa.Column("revision", sa.String(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["pdm_sync_run_table.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_pdm_reconciliation_finding_run_id",
        "pdm_reconciliation_finding_table",
        ["run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_pdm_reconciliation_finding_table_public_id"),
        "pdm_reconciliation_finding_table",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "pdm_sync_run_entry_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("vault_id", sa.String(), nullable=False),
        sa.Column("file_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("path", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["pdm_sync_run_table.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_pdm_sync_run_entry_run_id", "pdm_sync_run_entry_table", ["run_id"], unique=False
    )
    op.create_index(
        op.f("ix_pdm_sync_run_entry_table_public_id"),
        "pdm_sync_run_entry_table",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        "ix_pdm_sync_run_entry_vault_file",
        "pdm_sync_run_entry_table",
        ["vault_id", "file_id"],
        unique=False,
    )
    op.create_table(
        "plc_environment_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "changes",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("name_key", sa.String(), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("prefixes", sa.JSON(), nullable=False),
        sa.Column("max_tag_length", sa.Integer(), nullable=False),
        sa.Column("conversions", sa.JSON(), nullable=False),
        sa.Column("tag_table", sa.String(), nullable=False),
        sa.Column("safety_tag_table", sa.String(), nullable=True),
        sa.Column("export_sheet", sa.String(), nullable=False),
        sa.Column("export_columns", sa.JSON(), nullable=False),
        sa.Column("archived", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=True),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["changed_by_id"], ["user_table.id"], name="fk_plc_environment_table_changed_by_id"
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"], ["user_table.id"], name="fk_plc_environment_creator_id"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_plc_environment_table_changed_by_id"),
        "plc_environment_table",
        ["changed_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_plc_environment_table_creator_id"),
        "plc_environment_table",
        ["creator_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_plc_environment_table_public_id"),
        "plc_environment_table",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        "uq_plc_environment_name_active",
        "plc_environment_table",
        ["name_key"],
        unique=True,
        postgresql_where=sa.text("archived IS false"),
        sqlite_where=sa.text("archived = 0"),
    )
    op.create_table(
        "printer_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "changes",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column("archived", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("internal_name", sa.String(), nullable=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("host", sa.String(), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("timeout_seconds", sa.Float(), server_default="5", nullable=False),
        sa.Column("transport", sa.String(), nullable=False),
        sa.Column("ipp_uri_path", sa.String(), server_default="/", nullable=False),
        sa.Column("head_dpi", sa.Integer(), nullable=True),
        sa.Column("format_convert_factor", sa.Integer(), nullable=True),
        sa.Column("default_media", sa.String(), nullable=True),
        sa.Column("location", sa.String(), nullable=True),
        sa.Column("vendor", sa.String(), nullable=True),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column("firmware", sa.String(), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["changed_by_id"], ["user_table.id"], name="fk_printer_table_changed_by_id"
        ),
        sa.ForeignKeyConstraint(["creator_id"], ["user_table.id"], name="fk_printer_creator_id"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_printer_table_changed_by_id"), "printer_table", ["changed_by_id"], unique=False
    )
    op.create_index(
        op.f("ix_printer_table_creator_id"), "printer_table", ["creator_id"], unique=False
    )
    op.create_index(op.f("ix_printer_table_name"), "printer_table", ["name"], unique=False)
    op.create_index(op.f("ix_printer_table_public_id"), "printer_table", ["public_id"], unique=True)
    op.create_table(
        "product_device_kind_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "changes",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column("label", sa.JSON(), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("archived", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "without_driving_medium", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["changed_by_id"], ["user_table.id"], name="fk_product_device_kind_table_changed_by_id"
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"], ["user_table.id"], name="fk_product_device_kind_creator_id"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_product_device_kind_table_changed_by_id"),
        "product_device_kind_table",
        ["changed_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_device_kind_table_creator_id"),
        "product_device_kind_table",
        ["creator_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_device_kind_table_public_id"),
        "product_device_kind_table",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "product_device_option_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "changes",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("label", sa.JSON(), nullable=False),
        sa.Column("letter", sa.String(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("archived", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["changed_by_id"],
            ["user_table.id"],
            name="fk_product_device_option_table_changed_by_id",
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"], ["user_table.id"], name="fk_product_device_option_creator_id"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_product_device_option_table_category"),
        "product_device_option_table",
        ["category"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_device_option_table_changed_by_id"),
        "product_device_option_table",
        ["changed_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_device_option_table_creator_id"),
        "product_device_option_table",
        ["creator_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_device_option_table_public_id"),
        "product_device_option_table",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        "uq_product_device_option_letter",
        "product_device_option_table",
        ["letter"],
        unique=True,
        postgresql_where=sa.text("letter IS NOT NULL"),
        sqlite_where=sa.text("letter IS NOT NULL"),
    )
    op.create_table(
        "product_family_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "changes",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column("archived", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("label_color", sa.String(), server_default="#999999", nullable=False),
        sa.Column("label_font_color", sa.String(), server_default="#000000", nullable=False),
        sa.Column("description", sa.String(), server_default="", nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["changed_by_id"], ["user_table.id"], name="fk_product_family_table_changed_by_id"
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"], ["user_table.id"], name="fk_product_family_creator_id"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_product_family_table_changed_by_id"),
        "product_family_table",
        ["changed_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_family_table_creator_id"),
        "product_family_table",
        ["creator_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_family_table_name"), "product_family_table", ["name"], unique=False
    )
    op.create_index(
        op.f("ix_product_family_table_public_id"),
        "product_family_table",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        "uq_product_family_name_active",
        "product_family_table",
        ["name"],
        unique=True,
        postgresql_where=sa.text("archived IS false"),
        sqlite_where=sa.text("archived = 0"),
    )
    op.create_table(
        "production_machine_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "changes",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column("archived", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("internal_name", sa.String(), nullable=False),
        sa.Column("vendor", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("max_part_dimension", sa.String(), nullable=True),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("is_qa_machine", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["changed_by_id"], ["user_table.id"], name="fk_production_machine_table_changed_by_id"
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"], ["user_table.id"], name="fk_production_machine_creator_id"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_production_machine_table_changed_by_id"),
        "production_machine_table",
        ["changed_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_machine_table_creator_id"),
        "production_machine_table",
        ["creator_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_machine_table_internal_name"),
        "production_machine_table",
        ["internal_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_machine_table_public_id"),
        "production_machine_table",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "quote_request_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("request_number", sa.String(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "changes",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("deadline", sa.Date(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("edit_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["changed_by_id"], ["user_table.id"], name="fk_quote_request_table_changed_by_id"
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"], ["user_table.id"], name="fk_quote_request_creator_id"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_quote_request_table_changed_by_id"),
        "quote_request_table",
        ["changed_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_quote_request_table_creator_id"),
        "quote_request_table",
        ["creator_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_quote_request_table_public_id"), "quote_request_table", ["public_id"], unique=True
    )
    op.create_index(
        op.f("ix_quote_request_table_request_number"),
        "quote_request_table",
        ["request_number"],
        unique=True,
    )
    op.create_table(
        "security_event",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("actor_username", sa.String(length=255), nullable=True),
        sa.Column("target_user_id", sa.Integer(), nullable=True),
        sa.Column("target_username", sa.String(length=255), nullable=True),
        sa.Column("target_id", sa.Integer(), nullable=True),
        sa.Column("client_ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("detail", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["user_table.id"],
            name="fk_security_event_actor_user_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["target_user_id"],
            ["user_table.id"],
            name="fk_security_event_target_user_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_security_event_actor_user_id"), "security_event", ["actor_user_id"], unique=False
    )
    op.create_index(
        op.f("ix_security_event_event_type"), "security_event", ["event_type"], unique=False
    )
    op.create_index(
        op.f("ix_security_event_occurred_at"), "security_event", ["occurred_at"], unique=False
    )
    op.create_index(
        op.f("ix_security_event_public_id"), "security_event", ["public_id"], unique=True
    )
    op.create_index(
        op.f("ix_security_event_target_user_id"), "security_event", ["target_user_id"], unique=False
    )
    op.create_table(
        "shared_account_member_table",
        sa.Column("shared_account_id", sa.Integer(), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["member_id"],
            ["user_table.id"],
            name="fk_shared_account_member_member_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["shared_account_id"],
            ["user_table.id"],
            name="fk_shared_account_member_shared_account_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("shared_account_id", "member_id"),
    )
    op.create_index(
        op.f("ix_shared_account_member_table_member_id"),
        "shared_account_member_table",
        ["member_id"],
        unique=False,
    )
    op.create_table(
        "source_item_demand_bucket_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("color", sa.String(), nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["creator_id"], ["user_table.id"], name="fk_source_item_demand_bucket_creator_id"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_source_item_demand_bucket_name"),
    )
    op.create_index(
        op.f("ix_source_item_demand_bucket_table_creator_id"),
        "source_item_demand_bucket_table",
        ["creator_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_item_demand_bucket_table_public_id"),
        "source_item_demand_bucket_table",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "source_item_type_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "changes",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column("archived", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("name", sa.JSON(), nullable=False),
        sa.Column("label_color", sa.String(), nullable=False),
        sa.Column("label_font_color", sa.String(), nullable=False),
        sa.Column("description", sa.JSON(), nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["changed_by_id"], ["user_table.id"], name="fk_source_item_type_table_changed_by_id"
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"], ["user_table.id"], name="fk_source_item_type_creator_id"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_source_item_type_table_changed_by_id"),
        "source_item_type_table",
        ["changed_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_item_type_table_creator_id"),
        "source_item_type_table",
        ["creator_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_item_type_table_public_id"),
        "source_item_type_table",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "supplier_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "changes",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column("archived", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("legal_name", sa.String(), nullable=True),
        sa.Column("vat_id", sa.String(), nullable=True),
        sa.Column("level", sa.String(), nullable=False),
        sa.Column("external_lead_time_days", sa.Integer(), nullable=True),
        sa.Column("edp_code", sa.String(length=16), nullable=True),
        sa.Column(
            "edp_type_number_first", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("street", sa.String(), nullable=True),
        sa.Column("city", sa.String(), nullable=True),
        sa.Column("country", sa.String(), nullable=True),
        sa.Column("postal_code", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("weblink", sa.String(), nullable=True),
        sa.Column("order_email", sa.String(), nullable=True),
        sa.Column("order_language", sa.String(), nullable=True),
        sa.Column("order_template", sa.String(), nullable=True),
        sa.Column("request_email", sa.String(), nullable=True),
        sa.Column("request_language", sa.String(), nullable=True),
        sa.Column("request_template", sa.String(), nullable=True),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("edit_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["changed_by_id"], ["user_table.id"], name="fk_supplier_table_changed_by_id"
        ),
        sa.ForeignKeyConstraint(["creator_id"], ["user_table.id"], name="fk_supplier_creator_id"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_supplier_table_changed_by_id"), "supplier_table", ["changed_by_id"], unique=False
    )
    op.create_index(
        op.f("ix_supplier_table_creator_id"), "supplier_table", ["creator_id"], unique=False
    )
    op.create_index(op.f("ix_supplier_table_name"), "supplier_table", ["name"], unique=False)
    op.create_index(
        op.f("ix_supplier_table_public_id"), "supplier_table", ["public_id"], unique=True
    )
    op.create_index(
        "uq_supplier_edp_code_active",
        "supplier_table",
        ["edp_code"],
        unique=True,
        postgresql_where=sa.text("archived IS false"),
        sqlite_where=sa.text("archived = 0"),
    )
    op.create_index(
        "uq_supplier_vat_id_active",
        "supplier_table",
        ["vat_id"],
        unique=True,
        postgresql_where=sa.text("archived IS false"),
        sqlite_where=sa.text("archived = 0"),
    )
    op.create_table(
        "tenant_holiday_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "changes",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("end_date >= start_date", name="ck_tenant_holiday_dates_ordered"),
        sa.ForeignKeyConstraint(
            ["changed_by_id"], ["user_table.id"], name="fk_tenant_holiday_table_changed_by_id"
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"], ["user_table.id"], name="fk_tenant_holiday_creator_id"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_tenant_holiday_table_changed_by_id"),
        "tenant_holiday_table",
        ["changed_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tenant_holiday_table_creator_id"),
        "tenant_holiday_table",
        ["creator_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tenant_holiday_table_public_id"),
        "tenant_holiday_table",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_tenant_holiday_table_start_date"),
        "tenant_holiday_table",
        ["start_date"],
        unique=False,
    )
    op.create_table(
        "terminal_broadcast_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed", sa.DateTime(timezone=True), nullable=True),
        sa.Column("text", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("style", sa.String(), nullable=False),
        sa.Column("show_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("all_terminals", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["user_table.id"], name="fk_terminal_broadcast_created_by_id"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_terminal_broadcast_table_created_by_id"),
        "terminal_broadcast_table",
        ["created_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_terminal_broadcast_table_public_id"),
        "terminal_broadcast_table",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_terminal_broadcast_table_show_until"),
        "terminal_broadcast_table",
        ["show_until"],
        unique=False,
    )
    op.create_table(
        "user_agent_consent",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("consent_version", sa.Integer(), nullable=False),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user_table.id"],
            name="fk_user_agent_consent_user_id_user_table",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_user_agent_consent_user_id"),
    )
    op.create_index(
        op.f("ix_user_agent_consent_public_id"), "user_agent_consent", ["public_id"], unique=True
    )
    op.create_table(
        "user_group_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "changes",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), server_default="", nullable=False),
        sa.Column("permissions", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["changed_by_id"], ["user_table.id"], name="fk_user_group_table_changed_by_id"
        ),
        sa.ForeignKeyConstraint(["creator_id"], ["user_table.id"], name="fk_user_group_creator_id"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_user_group_table_changed_by_id"),
        "user_group_table",
        ["changed_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_group_table_creator_id"), "user_group_table", ["creator_id"], unique=False
    )
    op.create_index(
        op.f("ix_user_group_table_public_id"), "user_group_table", ["public_id"], unique=True
    )
    op.create_index(
        "uq_user_group_name_ci", "user_group_table", [sa.literal_column("lower(name)")], unique=True
    )
    op.create_table(
        "user_passkey_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("credential_id", sa.LargeBinary(), nullable=False),
        sa.Column("public_key", sa.LargeBinary(), nullable=False),
        sa.Column("sign_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("transports", sa.JSON(), nullable=False),
        sa.Column("backed_up", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user_table.id"],
            name="fk_user_passkey_table_user_id_user_table",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_user_passkey_table_credential_id"),
        "user_passkey_table",
        ["credential_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_user_passkey_table_public_id"), "user_passkey_table", ["public_id"], unique=True
    )
    op.create_index(
        op.f("ix_user_passkey_table_user_id"), "user_passkey_table", ["user_id"], unique=False
    )
    op.create_table(
        "user_pdm_link_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("pdm_user_id", sa.Integer(), nullable=False),
        sa.Column("pdm_username", sa.String(), nullable=False),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user_table.id"],
            name="fk_user_pdm_link_table_user_id_user_table",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pdm_user_id", name="uq_user_pdm_link_table_pdm_user_id"),
    )
    op.create_index(
        op.f("ix_user_pdm_link_table_public_id"), "user_pdm_link_table", ["public_id"], unique=True
    )
    op.create_index(
        op.f("ix_user_pdm_link_table_user_id"), "user_pdm_link_table", ["user_id"], unique=False
    )
    op.create_table(
        "user_session_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.Column("ip", sa.String(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user_table.id"],
            name="fk_user_session_table_user_id_user_table",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_user_session_table_public_id"), "user_session_table", ["public_id"], unique=True
    )
    op.create_index(
        op.f("ix_user_session_table_user_id"), "user_session_table", ["user_id"], unique=False
    )
    op.create_table(
        "user_time_tracking_credentials",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "time_tracking_user",
            sa.String(),
            nullable=False,
        ),
        sa.Column("time_tracking_sealed_credentials", sa.Text(), nullable=True),
        sa.Column("time_tracking_binding", sa.String(length=64), server_default="", nullable=False),
        sa.Column(
            "time_tracking_credential_key_id",
            sa.String(length=64),
            server_default="",
            nullable=False,
        ),
        sa.Column("time_tracking_user_fingerprint", sa.String(length=64), nullable=False),
        sa.Column(
            "time_tracking_user_fingerprint_key_id",
            sa.String(length=8),
            server_default="",
            nullable=False,
        ),
        sa.Column("time_tracking_auth_failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "time_tracking_consent_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "time_tracking_consent_version", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user_table.id"],
            name="fk_user_time_tracking_credentials_user_id_user_table",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "time_tracking_user_fingerprint", name="uq_user_time_tracking_credentials_fingerprint"
        ),
        sa.UniqueConstraint("user_id", name="uq_user_time_tracking_credentials_user_id"),
    )
    op.create_index(
        op.f("ix_user_time_tracking_credentials_public_id"),
        "user_time_tracking_credentials",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "user_trusted_device_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user_table.id"],
            name="fk_user_trusted_device_table_user_id_user_table",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_user_trusted_device_table_public_id"),
        "user_trusted_device_table",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_user_trusted_device_table_token_hash"),
        "user_trusted_device_table",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        op.f("ix_user_trusted_device_table_user_id"),
        "user_trusted_device_table",
        ["user_id"],
        unique=False,
    )
    op.create_table(
        "webhook_subscription_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column(
            "secret",
            sa.String(),
            nullable=False,
        ),
        sa.Column("event_types", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["creator_id"],
            ["user_table.id"],
            name="fk_webhook_subscription_table_creator_id_user_table",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_webhook_subscription_table_creator_id"),
        "webhook_subscription_table",
        ["creator_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_webhook_subscription_table_public_id"),
        "webhook_subscription_table",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "acknowledgement_recipients",
        sa.Column("acknowledgement_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["acknowledgement_id"],
            ["acknowledgements.id"],
            name="fk_acknowledgement_recipients_acknowledgement_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user_table.id"],
            name="fk_acknowledgement_recipients_user_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("acknowledgement_id", "user_id"),
    )
    op.create_index(
        op.f("ix_acknowledgement_recipients_public_id"),
        "acknowledgement_recipients",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_acknowledgement_recipients_user_id"),
        "acknowledgement_recipients",
        ["user_id"],
        unique=False,
    )
    op.create_table(
        "api_key_usage_log_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key_id", sa.Integer(), nullable=False),
        sa.Column("called_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("path", sa.String(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["key_id"], ["api_key_table.id"], name="fk_api_key_usage_log_table_key_id_api_key_table"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_api_key_usage_log_table_called_at"),
        "api_key_usage_log_table",
        ["called_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_api_key_usage_log_table_key_id"),
        "api_key_usage_log_table",
        ["key_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_api_key_usage_log_table_public_id"),
        "api_key_usage_log_table",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "bought_item_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "changes",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column("archived", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("order_code_1", sa.String(), nullable=False),
        sa.Column("order_code_2", sa.String(), nullable=True),
        sa.Column("gtin", sa.String(), nullable=True),
        sa.Column("ean", sa.String(), nullable=True),
        sa.Column("tariff_number", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("article_name", sa.String(), nullable=False),
        sa.Column("data_source", sa.String(), nullable=False),
        sa.Column("part_number", sa.String(), nullable=True),
        sa.Column("revision", sa.String(), nullable=True),
        sa.Column("mass", sa.Integer(), nullable=True),
        sa.Column("successor_item_id", sa.Integer(), nullable=True),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("weblink", sa.String(), nullable=True),
        sa.Column("vault_id", sa.String(), nullable=True),
        sa.Column("pdm_file_id", sa.Integer(), nullable=True),
        sa.Column("pdm_file_version", sa.Integer(), nullable=True),
        sa.Column("pdm_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pdm_sync_state", sa.String(), nullable=True),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("approver_id", sa.Integer(), nullable=True),
        sa.Column("manufacturer_id", sa.Integer(), nullable=False),
        sa.Column("product_family_id", sa.Integer(), nullable=True),
        sa.Column("edp_part_id", sa.Integer(), nullable=True),
        sa.Column("edp_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pdm_edp_part_id", sa.Integer(), nullable=True),
        sa.Column(
            "over_delivery_tolerance_percent",
            sa.Numeric(precision=7, scale=3, asdecimal=False),
            nullable=True,
        ),
        sa.Column(
            "under_delivery_tolerance_percent",
            sa.Numeric(precision=7, scale=3, asdecimal=False),
            nullable=True,
        ),
        sa.Column("edit_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["approver_id"], ["user_table.id"], name="fk_bought_item_approver_id"
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_id"], ["user_table.id"], name="fk_bought_item_table_changed_by_id"
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"], ["user_table.id"], name="fk_bought_item_creator_id"
        ),
        sa.ForeignKeyConstraint(
            ["manufacturer_id"], ["supplier_table.id"], name="fk_bought_item_manufacturer_id"
        ),
        sa.ForeignKeyConstraint(
            ["product_family_id"],
            ["product_family_table.id"],
            name="fk_bought_item_product_family_id",
        ),
        sa.ForeignKeyConstraint(
            ["successor_item_id"], ["bought_item_table.id"], name="fk_bought_item_successor_id"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_bought_item_table_approver_id"), "bought_item_table", ["approver_id"], unique=False
    )
    op.create_index(
        op.f("ix_bought_item_table_changed_by_id"),
        "bought_item_table",
        ["changed_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_bought_item_table_creator_id"), "bought_item_table", ["creator_id"], unique=False
    )
    op.create_index(
        op.f("ix_bought_item_table_edp_part_id"), "bought_item_table", ["edp_part_id"], unique=False
    )
    op.create_index(
        op.f("ix_bought_item_table_manufacturer_id"),
        "bought_item_table",
        ["manufacturer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_bought_item_table_order_code_1"),
        "bought_item_table",
        ["order_code_1"],
        unique=False,
    )
    op.create_index(
        op.f("ix_bought_item_table_part_number"), "bought_item_table", ["part_number"], unique=False
    )
    op.create_index(
        op.f("ix_bought_item_table_product_family_id"),
        "bought_item_table",
        ["product_family_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_bought_item_table_public_id"), "bought_item_table", ["public_id"], unique=True
    )
    op.create_index(
        op.f("ix_bought_item_table_successor_item_id"),
        "bought_item_table",
        ["successor_item_id"],
        unique=False,
    )
    op.create_index(
        "uq_bought_item_gtin_active",
        "bought_item_table",
        ["gtin"],
        unique=True,
        postgresql_where=sa.text("archived IS false"),
        sqlite_where=sa.text("archived = 0"),
    )
    op.create_index(
        "uq_bought_item_part_number",
        "bought_item_table",
        ["part_number"],
        unique=True,
        postgresql_where=sa.text("part_number IS NOT NULL"),
        sqlite_where=sa.text("part_number IS NOT NULL"),
    )
    op.create_index(
        "uq_bought_item_pdm_file",
        "bought_item_table",
        ["vault_id", "pdm_file_id"],
        unique=True,
        postgresql_where=sa.text("pdm_file_id IS NOT NULL"),
        sqlite_where=sa.text("pdm_file_id IS NOT NULL"),
    )
    op.create_table(
        "contact_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("anonymised_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("mobile", sa.String(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("customer_id", sa.Integer(), nullable=True),
        sa.Column("supplier_id", sa.Integer(), nullable=True),
        sa.Column(
            "receives_request_mails", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column(
            "receives_order_mails", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("edit_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "customer_id IS NULL OR supplier_id IS NULL", name="ck_contact_table_one_organisation"
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_id"], ["user_table.id"], name="fk_contact_table_changed_by_id"
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"], ["user_table.id"], name="fk_contact_table_creator_id_user_table"
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customer_table.id"],
            name="fk_contact_table_customer_id_customer_table",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["supplier_table.id"],
            name="fk_contact_table_supplier_id_supplier_table",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_contact_table_changed_by_id"), "contact_table", ["changed_by_id"], unique=False
    )
    op.create_index(
        op.f("ix_contact_table_creator_id"), "contact_table", ["creator_id"], unique=False
    )
    op.create_index(
        op.f("ix_contact_table_customer_id"), "contact_table", ["customer_id"], unique=False
    )
    op.create_index(op.f("ix_contact_table_name"), "contact_table", ["name"], unique=False)
    op.create_index(op.f("ix_contact_table_public_id"), "contact_table", ["public_id"], unique=True)
    op.create_index(
        op.f("ix_contact_table_supplier_id"), "contact_table", ["supplier_id"], unique=False
    )
    op.create_table(
        "fabrication_method_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "changes",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column("name", sa.JSON(), nullable=False),
        sa.Column("label_color", sa.String(), nullable=False),
        sa.Column("label_font_color", sa.String(), nullable=False),
        sa.Column("description", sa.JSON(), nullable=False),
        sa.Column("requires_machine", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "required_external", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("default_supplier_id", sa.Integer(), nullable=True),
        sa.Column("lead_time_days", sa.Integer(), nullable=True),
        sa.Column(
            "default_for_assemblies", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("archived", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["changed_by_id"], ["user_table.id"], name="fk_fabrication_method_table_changed_by_id"
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"], ["user_table.id"], name="fk_fabrication_method_creator_id"
        ),
        sa.ForeignKeyConstraint(
            ["default_supplier_id"],
            ["supplier_table.id"],
            name="fk_fabrication_method_default_supplier_id",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_fabrication_method_table_changed_by_id"),
        "fabrication_method_table",
        ["changed_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_fabrication_method_table_creator_id"),
        "fabrication_method_table",
        ["creator_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_fabrication_method_table_default_supplier_id"),
        "fabrication_method_table",
        ["default_supplier_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_fabrication_method_table_public_id"),
        "fabrication_method_table",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        "uq_fabrication_method_default_for_assemblies",
        "fabrication_method_table",
        ["default_for_assemblies"],
        unique=True,
        postgresql_where=sa.text("default_for_assemblies IS true"),
        sqlite_where=sa.text("default_for_assemblies = 1"),
    )
    op.create_table(
        "inspection_method_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "changes",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column("name", sa.JSON(), nullable=False),
        sa.Column("label_color", sa.String(), nullable=False),
        sa.Column("label_font_color", sa.String(), nullable=False),
        sa.Column("description", sa.JSON(), nullable=False),
        sa.Column("default_setup_minutes", sa.Integer(), nullable=True),
        sa.Column("default_minutes_per_piece", sa.Float(), nullable=True),
        sa.Column(
            "requires_evidence", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("archived", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("default_machine_id", sa.Integer(), nullable=True),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["changed_by_id"], ["user_table.id"], name="fk_inspection_method_table_changed_by_id"
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"], ["user_table.id"], name="fk_inspection_method_creator_id"
        ),
        sa.ForeignKeyConstraint(
            ["default_machine_id"],
            ["production_machine_table.id"],
            name="fk_inspection_method_default_machine_id",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_inspection_method_table_changed_by_id"),
        "inspection_method_table",
        ["changed_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_inspection_method_table_creator_id"),
        "inspection_method_table",
        ["creator_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_inspection_method_table_default_machine_id"),
        "inspection_method_table",
        ["default_machine_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_inspection_method_table_public_id"),
        "inspection_method_table",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "machine_calendar_exception_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "changes",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column("exception_date", sa.Date(), nullable=False),
        sa.Column("available_minutes", sa.Integer(), nullable=False),
        sa.Column("start_minute", sa.Integer(), server_default="480", nullable=False),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("machine_id", sa.Integer(), nullable=False),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["changed_by_id"],
            ["user_table.id"],
            name="fk_machine_calendar_exception_table_changed_by_id",
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"], ["user_table.id"], name="fk_machine_calendar_exception_creator_id"
        ),
        sa.ForeignKeyConstraint(
            ["machine_id"],
            ["production_machine_table.id"],
            name="fk_machine_calendar_exception_machine_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "machine_id", "exception_date", name="uq_machine_calendar_exception_machine_date"
        ),
    )
    op.create_index(
        op.f("ix_machine_calendar_exception_table_changed_by_id"),
        "machine_calendar_exception_table",
        ["changed_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_machine_calendar_exception_table_creator_id"),
        "machine_calendar_exception_table",
        ["creator_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_machine_calendar_exception_table_exception_date"),
        "machine_calendar_exception_table",
        ["exception_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_machine_calendar_exception_table_machine_id"),
        "machine_calendar_exception_table",
        ["machine_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_machine_calendar_exception_table_public_id"),
        "machine_calendar_exception_table",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "machine_downtime_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "changes",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column("machine_id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("reported_by_id", sa.Integer(), nullable=False),
        sa.Column("ended_by_id", sa.Integer(), nullable=True),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["changed_by_id"], ["user_table.id"], name="fk_machine_downtime_table_changed_by_id"
        ),
        sa.ForeignKeyConstraint(
            ["ended_by_id"], ["user_table.id"], name="fk_machine_downtime_ended_by_id"
        ),
        sa.ForeignKeyConstraint(
            ["machine_id"],
            ["production_machine_table.id"],
            name="fk_machine_downtime_machine_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reported_by_id"], ["user_table.id"], name="fk_machine_downtime_reported_by_id"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_machine_downtime_table_changed_by_id"),
        "machine_downtime_table",
        ["changed_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_machine_downtime_table_ended_by_id"),
        "machine_downtime_table",
        ["ended_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_machine_downtime_table_machine_id"),
        "machine_downtime_table",
        ["machine_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_machine_downtime_table_public_id"),
        "machine_downtime_table",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_machine_downtime_table_reported_by_id"),
        "machine_downtime_table",
        ["reported_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_machine_downtime_table_started_at"),
        "machine_downtime_table",
        ["started_at"],
        unique=False,
    )
    op.create_index(
        "uq_machine_downtime_open_per_machine",
        "machine_downtime_table",
        ["machine_id"],
        unique=True,
        postgresql_where=sa.text("ended_at IS NULL"),
        sqlite_where=sa.text("ended_at IS NULL"),
    )
    op.create_table(
        "machine_pool_machine_table",
        sa.Column("pool_id", sa.Integer(), nullable=False),
        sa.Column("machine_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["machine_id"],
            ["production_machine_table.id"],
            name="fk_machine_pool_machine_machine_id",
        ),
        sa.ForeignKeyConstraint(
            ["pool_id"],
            ["machine_pool_table.id"],
            name="fk_machine_pool_machine_pool_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("pool_id", "machine_id"),
    )
    op.create_index(
        op.f("ix_machine_pool_machine_table_machine_id"),
        "machine_pool_machine_table",
        ["machine_id"],
        unique=False,
    )
    op.create_table(
        "machine_working_hours_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "changes",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column("weekly_hours", sa.JSON(), nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("machine_id", sa.Integer(), nullable=False),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["changed_by_id"],
            ["user_table.id"],
            name="fk_machine_working_hours_table_changed_by_id",
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"], ["user_table.id"], name="fk_machine_working_hours_creator_id"
        ),
        sa.ForeignKeyConstraint(
            ["machine_id"],
            ["production_machine_table.id"],
            name="fk_machine_working_hours_machine_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("machine_id"),
    )
    op.create_index(
        op.f("ix_machine_working_hours_table_changed_by_id"),
        "machine_working_hours_table",
        ["changed_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_machine_working_hours_table_creator_id"),
        "machine_working_hours_table",
        ["creator_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_machine_working_hours_table_public_id"),
        "machine_working_hours_table",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "order_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_number", sa.String(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "changes",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("ordered_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expected_delivery_date", sa.Date(), nullable=True),
        sa.Column("delivery_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("storage_place", sa.String(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("edit_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("supplier_id", sa.Integer(), nullable=False),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["changed_by_id"], ["user_table.id"], name="fk_order_table_changed_by_id"
        ),
        sa.ForeignKeyConstraint(["creator_id"], ["user_table.id"], name="fk_order_creator_id"),
        sa.ForeignKeyConstraint(
            ["supplier_id"], ["supplier_table.id"], name="fk_order_supplier_id"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_order_table_changed_by_id"), "order_table", ["changed_by_id"], unique=False
    )
    op.create_index(op.f("ix_order_table_creator_id"), "order_table", ["creator_id"], unique=False)
    op.create_index(
        op.f("ix_order_table_order_number"), "order_table", ["order_number"], unique=True
    )
    op.create_index(op.f("ix_order_table_public_id"), "order_table", ["public_id"], unique=True)
    op.create_index(
        op.f("ix_order_table_supplier_id"), "order_table", ["supplier_id"], unique=False
    )
    op.create_table(
        "pat_usage_log_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pat_id", sa.Integer(), nullable=False),
        sa.Column("called_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("path", sa.String(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["pat_id"], ["pat_table.id"], name="fk_pat_usage_log_table_pat_id_pat_table"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_pat_usage_log_table_called_at"), "pat_usage_log_table", ["called_at"], unique=False
    )
    op.create_index(
        op.f("ix_pat_usage_log_table_pat_id"), "pat_usage_log_table", ["pat_id"], unique=False
    )
    op.create_index(
        op.f("ix_pat_usage_log_table_public_id"), "pat_usage_log_table", ["public_id"], unique=True
    )
    op.create_table(
        "print_template_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "changes",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column("classifier", sa.String(), nullable=False),
        sa.Column("trigger", sa.String(), nullable=True),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("field_map", sa.JSON(), nullable=False),
        sa.Column("printer_id", sa.Integer(), nullable=True),
        sa.Column("auto_print", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("copies_rule", sa.String(), server_default="fixed", nullable=False),
        sa.Column("copies_fixed", sa.Integer(), server_default="1", nullable=False),
        sa.Column("max_copies", sa.Integer(), server_default="50", nullable=False),
        sa.Column("design_dpi", sa.Integer(), nullable=True),
        sa.Column("label_width_mm", sa.Float(), nullable=True),
        sa.Column("label_height_mm", sa.Float(), nullable=True),
        sa.Column("paper", sa.String(), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("creator_id", sa.Integer(), nullable=True),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["changed_by_id"], ["user_table.id"], name="fk_print_template_table_changed_by_id"
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"], ["user_table.id"], name="fk_print_template_creator_id"
        ),
        sa.ForeignKeyConstraint(
            ["printer_id"], ["printer_table.id"], name="fk_print_template_printer_id"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_print_template_table_changed_by_id"),
        "print_template_table",
        ["changed_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_print_template_table_creator_id"),
        "print_template_table",
        ["creator_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_print_template_table_printer_id"),
        "print_template_table",
        ["printer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_print_template_table_public_id"),
        "print_template_table",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        "uq_print_template_classifier", "print_template_table", ["classifier"], unique=True
    )
    op.create_table(
        "product_device_kind_parameter_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kind_id", sa.Integer(), nullable=False),
        sa.Column("label", sa.JSON(), nullable=False),
        sa.Column("unit", sa.String(), nullable=True),
        sa.Column("value_type", sa.String(), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("archived", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["kind_id"],
            ["product_device_kind_table.id"],
            name="fk_product_device_kind_parameter_kind_id",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_product_device_kind_parameter_table_kind_id"),
        "product_device_kind_parameter_table",
        ["kind_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_device_kind_parameter_table_public_id"),
        "product_device_kind_parameter_table",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "product_device_kind_position_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kind_id", sa.Integer(), nullable=False),
        sa.Column("label", sa.JSON(), nullable=False),
        sa.Column("takes_value", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("unit", sa.String(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("archived", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("plc_state_name", sa.String(), nullable=True),
        sa.Column("plc_command_name", sa.String(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["kind_id"],
            ["product_device_kind_table.id"],
            name="fk_product_device_kind_position_kind_id",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_product_device_kind_position_table_kind_id"),
        "product_device_kind_position_table",
        ["kind_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_device_kind_position_table_public_id"),
        "product_device_kind_position_table",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "product_device_kind_signal_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kind_id", sa.Integer(), nullable=False),
        sa.Column("label", sa.JSON(), nullable=False),
        sa.Column("signal_type", sa.String(), nullable=False),
        sa.Column("plc_name", sa.String(), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("archived", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["kind_id"],
            ["product_device_kind_table.id"],
            name="fk_product_device_kind_signal_kind_id",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_product_device_kind_signal_table_kind_id"),
        "product_device_kind_signal_table",
        ["kind_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_device_kind_signal_table_public_id"),
        "product_device_kind_signal_table",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "product_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("product_number", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("designation", sa.String(length=200), nullable=True),
        sa.Column("machine_type", sa.String(length=200), nullable=True),
        sa.Column("installation_site", sa.String(length=200), nullable=True),
        sa.Column("installation_location", sa.String(length=200), nullable=True),
        sa.Column("planned_placing_on_market", sa.Date(), nullable=True),
        sa.Column("legal_basis", sa.String(length=16), nullable=True),
        sa.Column(
            "contains_pneumatics", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column(
            "contains_hydraulics", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column(
            "contains_electrics", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column(
            "contains_robotics", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("plc_environment_id", sa.Integer(), nullable=True),
        sa.Column("customer_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("archived", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("designated_user_id", sa.Integer(), nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=True),
        sa.Column("edit_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["creator_id"], ["user_table.id"], name="fk_product_table_creator_id_user_table"
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customer_table.id"],
            name="fk_product_table_customer_id_customer_table",
        ),
        sa.ForeignKeyConstraint(
            ["designated_user_id"],
            ["user_table.id"],
            name="fk_product_table_designated_user_id_user_table",
        ),
        sa.ForeignKeyConstraint(
            ["plc_environment_id"],
            ["plc_environment_table.id"],
            name="fk_product_plc_environment_id",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_product_table_creator_id"), "product_table", ["creator_id"], unique=False
    )
    op.create_index(
        op.f("ix_product_table_customer_id"), "product_table", ["customer_id"], unique=False
    )
    op.create_index(
        op.f("ix_product_table_designated_user_id"),
        "product_table",
        ["designated_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_table_plc_environment_id"),
        "product_table",
        ["plc_environment_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_table_product_number"), "product_table", ["product_number"], unique=False
    )
    op.create_index(op.f("ix_product_table_public_id"), "product_table", ["public_id"], unique=True)
    op.create_index(
        "uq_product_product_number_active",
        "product_table",
        ["product_number"],
        unique=True,
        postgresql_where=sa.text("archived IS false"),
        sqlite_where=sa.text("archived = 0"),
    )
    op.create_table(
        "quote_request_supplier_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("quote_request_id", sa.Integer(), nullable=False),
        sa.Column("supplier_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("declined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["quote_request_id"],
            ["quote_request_table.id"],
            name="fk_quote_request_supplier_request_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"], ["supplier_table.id"], name="fk_quote_request_supplier_supplier_id"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "quote_request_id", "supplier_id", name="uq_quote_request_supplier_request_supplier"
        ),
    )
    op.create_index(
        op.f("ix_quote_request_supplier_table_public_id"),
        "quote_request_supplier_table",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_quote_request_supplier_table_quote_request_id"),
        "quote_request_supplier_table",
        ["quote_request_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_quote_request_supplier_table_supplier_id"),
        "quote_request_supplier_table",
        ["supplier_id"],
        unique=False,
    )
    op.create_table(
        "source_item_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "changes",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column("archived", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("type_id", sa.Integer(), nullable=False),
        sa.Column("dimension", sa.String(), nullable=True),
        sa.Column("material", sa.String(), nullable=False),
        sa.Column("mass", sa.Integer(), nullable=True),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("order_code_1", sa.String(), nullable=True),
        sa.Column("order_code_2", sa.String(), nullable=True),
        sa.Column(
            "over_delivery_tolerance_percent",
            sa.Numeric(precision=7, scale=3, asdecimal=False),
            nullable=True,
        ),
        sa.Column(
            "under_delivery_tolerance_percent",
            sa.Numeric(precision=7, scale=3, asdecimal=False),
            nullable=True,
        ),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("successor_item_id", sa.Integer(), nullable=True),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("approver_id", sa.Integer(), nullable=True),
        sa.Column("manufacturer_id", sa.Integer(), nullable=True),
        sa.Column("edit_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["approver_id"], ["user_table.id"], name="fk_source_item_approver_id"
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_id"], ["user_table.id"], name="fk_source_item_table_changed_by_id"
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"], ["user_table.id"], name="fk_source_item_creator_id"
        ),
        sa.ForeignKeyConstraint(
            ["manufacturer_id"], ["supplier_table.id"], name="fk_source_item_manufacturer_id"
        ),
        sa.ForeignKeyConstraint(
            ["successor_item_id"], ["source_item_table.id"], name="fk_source_item_successor_id"
        ),
        sa.ForeignKeyConstraint(
            ["type_id"], ["source_item_type_table.id"], name="fk_source_item_type_id"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_source_item_table_approver_id"), "source_item_table", ["approver_id"], unique=False
    )
    op.create_index(
        op.f("ix_source_item_table_changed_by_id"),
        "source_item_table",
        ["changed_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_item_table_creator_id"), "source_item_table", ["creator_id"], unique=False
    )
    op.create_index(
        op.f("ix_source_item_table_manufacturer_id"),
        "source_item_table",
        ["manufacturer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_item_table_public_id"), "source_item_table", ["public_id"], unique=True
    )
    op.create_index(
        op.f("ix_source_item_table_successor_item_id"),
        "source_item_table",
        ["successor_item_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_item_table_type_id"), "source_item_table", ["type_id"], unique=False
    )
    op.create_index(
        "uq_source_item_spec_with_manufacturer",
        "source_item_table",
        ["dimension", "type_id", "material", "manufacturer_id"],
        unique=True,
        postgresql_where=sa.text("manufacturer_id IS NOT NULL AND archived IS FALSE"),
        sqlite_where=sa.text("manufacturer_id IS NOT NULL AND archived = 0"),
    )
    op.create_index(
        "uq_source_item_spec_without_manufacturer",
        "source_item_table",
        ["dimension", "type_id", "material"],
        unique=True,
        postgresql_where=sa.text("manufacturer_id IS NULL AND archived IS FALSE"),
        sqlite_where=sa.text("manufacturer_id IS NULL AND archived = 0"),
    )
    op.create_table(
        "supplier_article_group_table",
        sa.Column("supplier_id", sa.Integer(), nullable=False),
        sa.Column("article_group_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["article_group_id"],
            ["article_group_table.id"],
            name="fk_supplier_article_group_article_group_id",
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"], ["supplier_table.id"], name="fk_supplier_article_group_supplier_id"
        ),
        sa.PrimaryKeyConstraint("supplier_id", "article_group_id"),
    )
    op.create_index(
        op.f("ix_supplier_article_group_table_article_group_id"),
        "supplier_article_group_table",
        ["article_group_id"],
        unique=False,
    )
    op.create_table(
        "terminal_broadcast_infoscreen_table",
        sa.Column("broadcast_id", sa.Integer(), nullable=False),
        sa.Column("infoscreen_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["broadcast_id"],
            ["terminal_broadcast_table.id"],
            name="fk_terminal_broadcast_infoscreen_broadcast_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["infoscreen_id"],
            ["infoscreen_table.id"],
            name="fk_terminal_broadcast_infoscreen_infoscreen_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("broadcast_id", "infoscreen_id"),
    )
    op.create_index(
        op.f("ix_terminal_broadcast_infoscreen_table_infoscreen_id"),
        "terminal_broadcast_infoscreen_table",
        ["infoscreen_id"],
        unique=False,
    )
    op.create_table(
        "terminal_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed", sa.DateTime(timezone=True), nullable=True),
        sa.Column("public_key", sa.String(), nullable=False),
        sa.Column("public_key_fingerprint", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("mode", sa.String(), server_default="infoscreen", nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("pairing_code", sa.String(), nullable=True),
        sa.Column("pairing_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("infoscreen_id", sa.Integer(), nullable=True),
        sa.Column("api_key_id", sa.Integer(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_ip", sa.String(), nullable=True),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.Column("screen_width", sa.Integer(), nullable=True),
        sa.Column("screen_height", sa.Integer(), nullable=True),
        sa.Column("frontend_version", sa.String(), nullable=True),
        sa.Column("bridge_version", sa.String(), nullable=True),
        sa.Column("device_computer_model", sa.String(), nullable=True),
        sa.Column("device_ram_mb", sa.Integer(), nullable=True),
        sa.Column("device_os_name", sa.String(), nullable=True),
        sa.Column("device_display_make", sa.String(), nullable=True),
        sa.Column("device_display_model", sa.String(), nullable=True),
        sa.Column("device_display_width_px", sa.Integer(), nullable=True),
        sa.Column("device_display_height_px", sa.Integer(), nullable=True),
        sa.Column("device_details", sa.JSON(), nullable=True),
        sa.Column("device_reported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("location", sa.String(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_id", sa.Integer(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reload_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("identify_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("display_override", sa.String(), nullable=True),
        sa.Column("display_override_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_session_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_session_ip", sa.String(), nullable=True),
        sa.Column("duplicate_detected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["api_key_id"], ["api_key_table.id"], name="fk_terminal_api_key_id", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["approved_by_id"], ["user_table.id"], name="fk_terminal_approved_by_id"
        ),
        sa.ForeignKeyConstraint(
            ["infoscreen_id"],
            ["infoscreen_table.id"],
            name="fk_terminal_infoscreen_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_terminal_table_api_key_id"), "terminal_table", ["api_key_id"], unique=False
    )
    op.create_index(
        op.f("ix_terminal_table_approved_by_id"), "terminal_table", ["approved_by_id"], unique=False
    )
    op.create_index(
        op.f("ix_terminal_table_infoscreen_id"), "terminal_table", ["infoscreen_id"], unique=False
    )
    op.create_index(
        op.f("ix_terminal_table_public_id"), "terminal_table", ["public_id"], unique=True
    )
    op.create_index(op.f("ix_terminal_table_status"), "terminal_table", ["status"], unique=False)
    op.create_index(
        "uq_terminal_pairing_code_pending",
        "terminal_table",
        ["pairing_code"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
        sqlite_where=sa.text("status = 'pending'"),
    )
    op.create_index("uq_terminal_public_key", "terminal_table", ["public_key"], unique=True)
    op.create_table(
        "user_group_member_table",
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["user_group_table.id"],
            name="fk_user_group_member_group_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user_table.id"], name="fk_user_group_member_user_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("group_id", "user_id"),
    )
    op.create_index(
        op.f("ix_user_group_member_table_user_id"),
        "user_group_member_table",
        ["user_id"],
        unique=False,
    )
    op.create_table(
        "webhook_delivery_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("subscription_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("source_event_id", sa.String(), nullable=False),
        sa.Column("payload", sa.String(), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["webhook_subscription_table.id"],
            name="fk_webhook_delivery_table_subscription_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_webhook_delivery_table_public_id"),
        "webhook_delivery_table",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_webhook_delivery_table_source_event_id"),
        "webhook_delivery_table",
        ["source_event_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_webhook_delivery_table_subscription_id"),
        "webhook_delivery_table",
        ["subscription_id"],
        unique=False,
    )
    op.create_table(
        "admin_production_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "production_order_number_format",
            sa.String(),
            server_default="PON-{yy}-{seq:05d}",
            nullable=False,
        ),
        sa.Column(
            "default_weekly_hours",
            sa.JSON(),
            server_default=(
                '{"0":[{"start_minute":480,"minutes":480}],"1":[{"start_minute":480,"minutes":480}],"2":[{"start_minute":480,"minutes":480}],"3":[{"start_minute":480,"minutes":480}],"4":[{"start_minute":480,"minutes":480}],"5":[],"6":[]}'
            ),
            nullable=False,
        ),
        sa.Column("default_external_lead_days", sa.Integer(), server_default="0", nullable=False),
        sa.Column("response_time_days", sa.Integer(), server_default="1", nullable=False),
        sa.Column("require_qa", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("frozen_window_hours", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "require_source_item_approval", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column(
            "assign_approved_material_to_item", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column(
            "overwrite_item_material_on_approval",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column("default_inspection_method_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["default_inspection_method_id"],
            ["inspection_method_table.id"],
            name="fk_admin_production_settings_inspection_method_id",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_admin_production_settings_default_inspection_method_id"),
        "admin_production_settings",
        ["default_inspection_method_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_admin_production_settings_public_id"),
        "admin_production_settings",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "bought_item_article_group_table",
        sa.Column("bought_item_id", sa.Integer(), nullable=False),
        sa.Column("article_group_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["article_group_id"],
            ["article_group_table.id"],
            name="fk_bought_item_article_group_article_group_id",
        ),
        sa.ForeignKeyConstraint(
            ["bought_item_id"],
            ["bought_item_table.id"],
            name="fk_bought_item_article_group_bought_item_id",
        ),
        sa.PrimaryKeyConstraint("bought_item_id", "article_group_id"),
    )
    op.create_index(
        op.f("ix_bought_item_article_group_table_article_group_id"),
        "bought_item_article_group_table",
        ["article_group_id"],
        unique=False,
    )
    op.create_table(
        "bought_item_file_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bought_item_id", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(), nullable=False),
        sa.Column("stored_name", sa.String(), nullable=False),
        sa.Column("mime_type", sa.String(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(), nullable=False),
        sa.Column("sha256", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["bought_item_id"], ["bought_item_table.id"], name="fk_bought_item_file_bought_item_id"
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_user_id"], ["user_table.id"], name="fk_bought_item_file_uploader_id"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stored_name"),
    )
    op.create_index(
        op.f("ix_bought_item_file_table_bought_item_id"),
        "bought_item_file_table",
        ["bought_item_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_bought_item_file_table_public_id"),
        "bought_item_file_table",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_bought_item_file_table_uploaded_by_user_id"),
        "bought_item_file_table",
        ["uploaded_by_user_id"],
        unique=False,
    )
    op.create_table(
        "machine_fabrication_method_table",
        sa.Column("machine_id", sa.Integer(), nullable=False),
        sa.Column("fabrication_method_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["fabrication_method_id"],
            ["fabrication_method_table.id"],
            name="fk_machine_fabrication_method_fabrication_method_id",
        ),
        sa.ForeignKeyConstraint(
            ["machine_id"],
            ["production_machine_table.id"],
            name="fk_machine_fabrication_method_machine_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("machine_id", "fabrication_method_id"),
    )
    op.create_index(
        op.f("ix_machine_fabrication_method_table_fabrication_method_id"),
        "machine_fabrication_method_table",
        ["fabrication_method_id"],
        unique=False,
    )
    op.create_table(
        "made_item_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "changes",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column("archived", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("revision", sa.String(), nullable=False),
        sa.Column("revision_date", sa.Date(), nullable=True),
        sa.Column("revision_note", sa.String(), nullable=True),
        sa.Column("article_name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("data_source", sa.String(), nullable=False),
        sa.Column("part_number", sa.String(), nullable=True),
        sa.Column("material", sa.String(), nullable=True),
        sa.Column("mass", sa.Integer(), nullable=True),
        sa.Column("base_size", sa.String(), nullable=True),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("weblink", sa.String(), nullable=True),
        sa.Column("customer_part_number", sa.String(), nullable=True),
        sa.Column("customer_revision", sa.String(), nullable=True),
        sa.Column("successor_item_id", sa.Integer(), nullable=True),
        sa.Column("vault_id", sa.String(), nullable=True),
        sa.Column("pdm_file_id", sa.Integer(), nullable=True),
        sa.Column("pdm_file_version", sa.Integer(), nullable=True),
        sa.Column("pdm_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pdm_sync_state", sa.String(), nullable=True),
        sa.Column("pdm_source_item_id", sa.Integer(), nullable=True),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("approver_id", sa.Integer(), nullable=True),
        sa.Column("bought_item_id", sa.Integer(), nullable=True),
        sa.Column("source_item_id", sa.Integer(), nullable=True),
        sa.Column("customer_id", sa.Integer(), nullable=True),
        sa.Column("edit_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["approver_id"], ["user_table.id"], name="fk_made_item_approver_id"
        ),
        sa.ForeignKeyConstraint(
            ["bought_item_id"], ["bought_item_table.id"], name="fk_made_item_bought_item_id"
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_id"], ["user_table.id"], name="fk_made_item_changed_by_id"
        ),
        sa.ForeignKeyConstraint(["creator_id"], ["user_table.id"], name="fk_made_item_creator_id"),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["customer_table.id"], name="fk_made_item_customer_id"
        ),
        sa.ForeignKeyConstraint(
            ["source_item_id"], ["source_item_table.id"], name="fk_made_item_source_item_id"
        ),
        sa.ForeignKeyConstraint(
            ["successor_item_id"], ["made_item_table.id"], name="fk_made_item_successor_id"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_made_item_table_approver_id"), "made_item_table", ["approver_id"], unique=False
    )
    op.create_index(
        op.f("ix_made_item_table_bought_item_id"),
        "made_item_table",
        ["bought_item_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_made_item_table_changed_by_id"), "made_item_table", ["changed_by_id"], unique=False
    )
    op.create_index(
        op.f("ix_made_item_table_creator_id"), "made_item_table", ["creator_id"], unique=False
    )
    op.create_index(
        op.f("ix_made_item_table_customer_id"), "made_item_table", ["customer_id"], unique=False
    )
    op.create_index(
        op.f("ix_made_item_table_part_number"), "made_item_table", ["part_number"], unique=False
    )
    op.create_index(
        op.f("ix_made_item_table_public_id"), "made_item_table", ["public_id"], unique=True
    )
    op.create_index(
        op.f("ix_made_item_table_source_item_id"),
        "made_item_table",
        ["source_item_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_made_item_table_successor_item_id"),
        "made_item_table",
        ["successor_item_id"],
        unique=False,
    )
    op.create_index(
        "uq_made_item_part_number_revision",
        "made_item_table",
        ["part_number", "revision"],
        unique=True,
        postgresql_where=sa.text("part_number IS NOT NULL"),
        sqlite_where=sa.text("part_number IS NOT NULL"),
    )
    op.create_index(
        "uq_made_item_pdm_file_revision",
        "made_item_table",
        ["vault_id", "pdm_file_id", "revision"],
        unique=True,
        postgresql_where=sa.text("pdm_file_id IS NOT NULL"),
        sqlite_where=sa.text("pdm_file_id IS NOT NULL"),
    )
    op.create_table(
        "plc_manual_tag_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed", sa.DateTime(timezone=True), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("signal_type", sa.String(), nullable=False),
        sa.Column("safety", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("address", sa.String(), nullable=True),
        sa.Column("comment", sa.String(), server_default="", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["changed_by_id"], ["user_table.id"], name="fk_plc_manual_tag_table_changed_by_id"
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"], ["user_table.id"], name="fk_plc_manual_tag_creator_id"
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["product_table.id"], name="fk_plc_manual_tag_product_id"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_plc_manual_tag_table_changed_by_id"),
        "plc_manual_tag_table",
        ["changed_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_plc_manual_tag_table_creator_id"),
        "plc_manual_tag_table",
        ["creator_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_plc_manual_tag_table_product_id"),
        "plc_manual_tag_table",
        ["product_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_plc_manual_tag_table_public_id"),
        "plc_manual_tag_table",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "print_job_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=True),
        sa.Column("printer_id", sa.Integer(), nullable=True),
        sa.Column("classifier", sa.String(), nullable=False),
        sa.Column("root_type", sa.String(), nullable=False),
        sa.Column("root_id", sa.Integer(), nullable=False),
        sa.Column("copies", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("rendered_zpl", sa.Text(), nullable=True),
        sa.Column("document_bytes", sa.Integer(), nullable=True),
        sa.Column("trigger", sa.String(), nullable=False),
        sa.Column("source_event_id", sa.String(), nullable=True),
        sa.Column("actor_id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["user_table.id"], name="fk_print_job_actor_id"),
        sa.ForeignKeyConstraint(
            ["printer_id"],
            ["printer_table.id"],
            name="fk_print_job_printer_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["print_template_table.id"],
            name="fk_print_job_template_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_print_job_table_actor_id"), "print_job_table", ["actor_id"], unique=False
    )
    op.create_index("ix_print_job_table_created", "print_job_table", ["created"], unique=False)
    op.create_index(
        op.f("ix_print_job_table_printer_id"), "print_job_table", ["printer_id"], unique=False
    )
    op.create_index(
        op.f("ix_print_job_table_public_id"), "print_job_table", ["public_id"], unique=True
    )
    op.create_index(
        op.f("ix_print_job_table_template_id"), "print_job_table", ["template_id"], unique=False
    )
    op.create_index(
        "uq_print_job_classifier_source_event",
        "print_job_table",
        ["classifier", "source_event_id"],
        unique=True,
        postgresql_where=sa.text("source_event_id IS NOT NULL"),
        sqlite_where=sa.text("source_event_id IS NOT NULL"),
    )
    op.create_table(
        "printer_bought_item_table",
        sa.Column("printer_id", sa.Integer(), nullable=False),
        sa.Column("bought_item_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["bought_item_id"],
            ["bought_item_table.id"],
            name="fk_printer_bought_item_bought_item_id",
        ),
        sa.ForeignKeyConstraint(
            ["printer_id"],
            ["printer_table.id"],
            name="fk_printer_bought_item_printer_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("printer_id", "bought_item_id"),
    )
    op.create_index(
        op.f("ix_printer_bought_item_table_bought_item_id"),
        "printer_bought_item_table",
        ["bought_item_id"],
        unique=False,
    )
    op.create_table(
        "product_contact_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("contact_id", sa.Integer(), nullable=False),
        sa.Column(
            "receives_meeting_notes", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["contact_id"],
            ["contact_table.id"],
            name="fk_product_contact_contact_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"], ["user_table.id"], name="fk_product_contact_creator_id"
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["product_table.id"],
            name="fk_product_contact_product_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id", "contact_id", name="uq_product_contact_product_contact"),
    )
    op.create_index(
        op.f("ix_product_contact_table_contact_id"),
        "product_contact_table",
        ["contact_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_contact_table_creator_id"),
        "product_contact_table",
        ["creator_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_contact_table_public_id"),
        "product_contact_table",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "product_file_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(), nullable=False),
        sa.Column("stored_name", sa.String(), nullable=False),
        sa.Column("mime_type", sa.String(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(), nullable=False),
        sa.Column("sha256", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["product_id"], ["product_table.id"], name="fk_product_file_product_id"
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_user_id"], ["user_table.id"], name="fk_product_file_uploader_id"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stored_name"),
    )
    op.create_index(
        op.f("ix_product_file_table_product_id"), "product_file_table", ["product_id"], unique=False
    )
    op.create_index(
        op.f("ix_product_file_table_public_id"), "product_file_table", ["public_id"], unique=True
    )
    op.create_index(
        op.f("ix_product_file_table_uploaded_by_user_id"),
        "product_file_table",
        ["uploaded_by_user_id"],
        unique=False,
    )
    op.create_table(
        "product_variant_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("archived", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["product_id"], ["product_table.id"], name="fk_product_variant_product_id"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_product_variant_table_product_id"),
        "product_variant_table",
        ["product_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_variant_table_public_id"),
        "product_variant_table",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        "uq_product_variant_name_active",
        "product_variant_table",
        ["product_id", "name"],
        unique=True,
        postgresql_where=sa.text("archived IS false"),
        sqlite_where=sa.text("archived = 0"),
    )
    op.create_table(
        "project_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "changes",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column("project_number", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("customer_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(), server_default="active", nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("designated_user_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("creator_id", sa.Integer(), nullable=True),
        sa.Column("production_time_budget", sa.Integer(), nullable=True),
        sa.Column("required_delivery_date_made", sa.Date(), nullable=True),
        sa.Column("required_delivery_date_bought", sa.Date(), nullable=True),
        sa.Column("edit_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["changed_by_id"], ["user_table.id"], name="fk_project_table_changed_by_id"
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"], ["user_table.id"], name="fk_project_table_creator_id_user_table"
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customer_table.id"],
            name="fk_project_table_customer_id_customer_table",
        ),
        sa.ForeignKeyConstraint(
            ["designated_user_id"],
            ["user_table.id"],
            name="fk_project_table_designated_user_id_user_table",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["product_table.id"], name="fk_project_table_product_id_product_table"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_project_table_changed_by_id"), "project_table", ["changed_by_id"], unique=False
    )
    op.create_index(
        op.f("ix_project_table_creator_id"), "project_table", ["creator_id"], unique=False
    )
    op.create_index(
        op.f("ix_project_table_customer_id"), "project_table", ["customer_id"], unique=False
    )
    op.create_index(
        op.f("ix_project_table_designated_user_id"),
        "project_table",
        ["designated_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_project_table_product_id"), "project_table", ["product_id"], unique=False
    )
    op.create_index(
        op.f("ix_project_table_project_number"), "project_table", ["project_number"], unique=False
    )
    op.create_index(op.f("ix_project_table_public_id"), "project_table", ["public_id"], unique=True)
    op.create_index(op.f("ix_project_table_status"), "project_table", ["status"], unique=False)
    op.create_index(
        "uq_project_project_number_active",
        "project_table",
        ["project_number"],
        unique=True,
        postgresql_where=sa.text("deleted IS false"),
        sqlite_where=sa.text("deleted = 0"),
    )
    op.create_table(
        "quote_request_file_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("supplier_row_id", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(), nullable=False),
        sa.Column("stored_name", sa.String(), nullable=False),
        sa.Column("mime_type", sa.String(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(), nullable=False),
        sa.Column("sha256", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["supplier_row_id"],
            ["quote_request_supplier_table.id"],
            name="fk_quote_request_file_supplier_row_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_user_id"], ["user_table.id"], name="fk_quote_request_file_uploader_id"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stored_name"),
    )
    op.create_index(
        op.f("ix_quote_request_file_table_public_id"),
        "quote_request_file_table",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_quote_request_file_table_supplier_row_id"),
        "quote_request_file_table",
        ["supplier_row_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_quote_request_file_table_uploaded_by_user_id"),
        "quote_request_file_table",
        ["uploaded_by_user_id"],
        unique=False,
    )
    op.create_table(
        "sequence_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("steps", sa.JSON(), nullable=False),
        sa.Column("frozen", sa.JSON(), nullable=True),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "changes",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column("document_number", sa.String(length=32), nullable=False),
        sa.Column("lineage", sa.Uuid(), nullable=False),
        sa.Column("revision", sa.String(length=16), nullable=False),
        sa.Column("revision_reason", sa.String(), nullable=True),
        sa.Column("is_latest", sa.Boolean(), nullable=False),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalid_reason", sa.String(), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("editor_ids", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("lock_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("released_by_id", sa.Integer(), nullable=True),
        sa.Column("invalid_by_id", sa.Integer(), nullable=True),
        sa.Column("locked_by_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["changed_by_id"], ["user_table.id"], name="fk_sequence_changed_by_id"
        ),
        sa.ForeignKeyConstraint(["creator_id"], ["user_table.id"], name="fk_sequence_creator_id"),
        sa.ForeignKeyConstraint(
            ["invalid_by_id"], ["user_table.id"], name="fk_sequence_invalid_by_id"
        ),
        sa.ForeignKeyConstraint(
            ["locked_by_id"], ["user_table.id"], name="fk_sequence_locked_by_id"
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["product_table.id"], name="fk_sequence_product_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["released_by_id"], ["user_table.id"], name="fk_sequence_released_by_id"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("lineage", "revision", name="uq_sequence_lineage_revision"),
    )
    op.create_index(
        op.f("ix_sequence_table_changed_by_id"), "sequence_table", ["changed_by_id"], unique=False
    )
    op.create_index(
        op.f("ix_sequence_table_creator_id"), "sequence_table", ["creator_id"], unique=False
    )
    op.create_index(
        op.f("ix_sequence_table_document_number"),
        "sequence_table",
        ["document_number"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sequence_table_invalid_by_id"), "sequence_table", ["invalid_by_id"], unique=False
    )
    op.create_index(op.f("ix_sequence_table_lineage"), "sequence_table", ["lineage"], unique=False)
    op.create_index(
        op.f("ix_sequence_table_locked_by_id"), "sequence_table", ["locked_by_id"], unique=False
    )
    op.create_index(
        op.f("ix_sequence_table_product_id"), "sequence_table", ["product_id"], unique=False
    )
    op.create_index(
        op.f("ix_sequence_table_public_id"), "sequence_table", ["public_id"], unique=True
    )
    op.create_index(
        op.f("ix_sequence_table_released_by_id"), "sequence_table", ["released_by_id"], unique=False
    )
    op.create_index(
        "uq_sequence_document_number_latest",
        "sequence_table",
        ["document_number"],
        unique=True,
        postgresql_where=sa.text("is_latest IS true"),
        sqlite_where=sa.text("is_latest = 1"),
    )
    op.create_index(
        "uq_sequence_lineage_latest",
        "sequence_table",
        ["lineage"],
        unique=True,
        postgresql_where=sa.text("is_latest IS true"),
        sqlite_where=sa.text("is_latest = 1"),
    )
    op.create_table(
        "source_item_file_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_item_id", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(), nullable=False),
        sa.Column("stored_name", sa.String(), nullable=False),
        sa.Column("mime_type", sa.String(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(), nullable=False),
        sa.Column("sha256", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_item_id"], ["source_item_table.id"], name="fk_source_item_file_source_item_id"
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_user_id"], ["user_table.id"], name="fk_source_item_file_uploader_id"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stored_name"),
    )
    op.create_index(
        op.f("ix_source_item_file_table_public_id"),
        "source_item_file_table",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_source_item_file_table_source_item_id"),
        "source_item_file_table",
        ["source_item_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_item_file_table_uploaded_by_user_id"),
        "source_item_file_table",
        ["uploaded_by_user_id"],
        unique=False,
    )
    op.create_table(
        "supplier_fabrication_method_table",
        sa.Column("supplier_id", sa.Integer(), nullable=False),
        sa.Column("fabrication_method_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["fabrication_method_id"],
            ["fabrication_method_table.id"],
            name="fk_supplier_fabrication_method_fabrication_method_id",
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["supplier_table.id"],
            name="fk_supplier_fabrication_method_supplier_id",
        ),
        sa.PrimaryKeyConstraint("supplier_id", "fabrication_method_id"),
    )
    op.create_index(
        op.f("ix_supplier_fabrication_method_table_fabrication_method_id"),
        "supplier_fabrication_method_table",
        ["fabrication_method_id"],
        unique=False,
    )
    op.create_table(
        "terminal_broadcast_terminal_table",
        sa.Column("broadcast_id", sa.Integer(), nullable=False),
        sa.Column("terminal_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["broadcast_id"],
            ["terminal_broadcast_table.id"],
            name="fk_terminal_broadcast_terminal_broadcast_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["terminal_id"],
            ["terminal_table.id"],
            name="fk_terminal_broadcast_terminal_terminal_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("broadcast_id", "terminal_id"),
    )
    op.create_index(
        op.f("ix_terminal_broadcast_terminal_table_terminal_id"),
        "terminal_broadcast_terminal_table",
        ["terminal_id"],
        unique=False,
    )
    op.create_table(
        "production_lot_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "changes",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column("lot_number", sa.String(), nullable=False),
        sa.Column(
            "quantity",
            sa.Numeric(precision=18, scale=6, asdecimal=False),
            nullable=False,
        ),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("priority", sa.String(), nullable=False),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("required_delivery_date", sa.Date(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "quantity_scrapped",
            sa.Numeric(precision=18, scale=6, asdecimal=False),
            server_default="0",
            nullable=False,
        ),
        sa.Column("held_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("force_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("edit_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("made_item_id", sa.Integer(), nullable=False),
        sa.Column("source_bought_item_id", sa.Integer(), nullable=True),
        sa.Column("source_item_id", sa.Integer(), nullable=True),
        sa.Column("source_made_item_id", sa.Integer(), nullable=True),
        sa.Column("origin_lot_id", sa.Integer(), nullable=True),
        sa.Column("origin_disposition", sa.String(), nullable=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("input_demand_id", sa.Integer(), nullable=True),
        sa.Column(
            "source_approval_status", sa.String(), server_default="not_required", nullable=False
        ),
        sa.Column("source_approved_by_id", sa.Integer(), nullable=True),
        sa.Column("source_approved_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_rejected_by_id", sa.Integer(), nullable=True),
        sa.Column("source_rejected_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_rejection_reason", sa.String(), nullable=True),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            (
                "(origin_lot_id IS NULL AND origin_disposition IS NULL) OR (origin_lot_id IS NOT "
                "NULL AND origin_disposition IS NOT NULL)"
            ),
            name="ck_production_lot_origin",
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_id"], ["user_table.id"], name="fk_production_lot_table_changed_by_id"
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"], ["user_table.id"], name="fk_production_lot_creator_id"
        ),
        sa.ForeignKeyConstraint(
            ["made_item_id"], ["made_item_table.id"], name="fk_production_lot_made_item_id"
        ),
        sa.ForeignKeyConstraint(
            ["origin_lot_id"], ["production_lot_table.id"], name="fk_production_lot_origin_lot_id"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project_table.id"], name="fk_production_lot_project_id"
        ),
        sa.ForeignKeyConstraint(
            ["source_approved_by_id"],
            ["user_table.id"],
            name="fk_production_lot_source_approved_by_id",
        ),
        sa.ForeignKeyConstraint(
            ["source_bought_item_id"],
            ["bought_item_table.id"],
            name="fk_production_lot_source_bought_item_id",
        ),
        sa.ForeignKeyConstraint(
            ["source_item_id"], ["source_item_table.id"], name="fk_production_lot_source_item_id"
        ),
        sa.ForeignKeyConstraint(
            ["source_made_item_id"],
            ["made_item_table.id"],
            name="fk_production_lot_source_made_item_id",
        ),
        sa.ForeignKeyConstraint(
            ["source_rejected_by_id"],
            ["user_table.id"],
            name="fk_production_lot_source_rejected_by_id",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_production_lot_table_changed_by_id"),
        "production_lot_table",
        ["changed_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_lot_table_creator_id"),
        "production_lot_table",
        ["creator_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_lot_table_input_demand_id"),
        "production_lot_table",
        ["input_demand_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_lot_table_lot_number"),
        "production_lot_table",
        ["lot_number"],
        unique=True,
    )
    op.create_index(
        op.f("ix_production_lot_table_made_item_id"),
        "production_lot_table",
        ["made_item_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_lot_table_origin_lot_id"),
        "production_lot_table",
        ["origin_lot_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_lot_table_project_id"),
        "production_lot_table",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_lot_table_public_id"),
        "production_lot_table",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_production_lot_table_source_approval_status"),
        "production_lot_table",
        ["source_approval_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_lot_table_source_approved_by_id"),
        "production_lot_table",
        ["source_approved_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_lot_table_source_bought_item_id"),
        "production_lot_table",
        ["source_bought_item_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_lot_table_source_item_id"),
        "production_lot_table",
        ["source_item_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_lot_table_source_made_item_id"),
        "production_lot_table",
        ["source_made_item_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_lot_table_source_rejected_by_id"),
        "production_lot_table",
        ["source_rejected_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_lot_table_status"), "production_lot_table", ["status"], unique=False
    )
    op.create_table(
        "bought_item_demand_item_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "changes",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column(
            "quantity",
            sa.Numeric(precision=18, scale=6, asdecimal=False),
            nullable=False,
        ),
        sa.Column("unit", sa.String(), nullable=False),
        sa.Column(
            "items_per_unit",
            sa.Numeric(precision=18, scale=6, asdecimal=False),
            nullable=False,
        ),
        sa.Column("high_priority", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "notify_on_delivery", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("desired_delivery_date", sa.Date(), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fulfilled_manually_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("bucket_id", sa.Integer(), nullable=True),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["bucket_id"],
            ["bought_item_demand_bucket_table.id"],
            name="fk_demand_item_bucket_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_id"],
            ["user_table.id"],
            name="fk_bought_item_demand_item_table_changed_by_id",
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"], ["user_table.id"], name="fk_demand_item_creator_id"
        ),
        sa.ForeignKeyConstraint(
            ["item_id"], ["bought_item_table.id"], name="fk_demand_item_item_id"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project_table.id"], name="fk_demand_item_project_id"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_bought_item_demand_item_table_bucket_id"),
        "bought_item_demand_item_table",
        ["bucket_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_bought_item_demand_item_table_changed_by_id"),
        "bought_item_demand_item_table",
        ["changed_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_bought_item_demand_item_table_creator_id"),
        "bought_item_demand_item_table",
        ["creator_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_bought_item_demand_item_table_item_id"),
        "bought_item_demand_item_table",
        ["item_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_bought_item_demand_item_table_project_id"),
        "bought_item_demand_item_table",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_bought_item_demand_item_table_public_id"),
        "bought_item_demand_item_table",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "checklist_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("header", sa.JSON(), nullable=False),
        sa.Column("answers", sa.JSON(), nullable=False),
        sa.Column("remarks", sa.JSON(), nullable=False),
        sa.Column("definition_version", sa.Integer(), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("answered_count", sa.Integer(), nullable=False),
        sa.Column("finding_count", sa.Integer(), nullable=False),
        sa.Column("verdict", sa.String(length=16), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "changes",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column("document_number", sa.String(length=32), nullable=False),
        sa.Column("lineage", sa.Uuid(), nullable=False),
        sa.Column("revision", sa.String(length=16), nullable=False),
        sa.Column("revision_reason", sa.String(), nullable=True),
        sa.Column("is_latest", sa.Boolean(), nullable=False),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalid_reason", sa.String(), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("editor_ids", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("lock_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("released_by_id", sa.Integer(), nullable=True),
        sa.Column("invalid_by_id", sa.Integer(), nullable=True),
        sa.Column("locked_by_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "project_id IS NULL OR product_id IS NULL", name="ck_checklist_single_owner"
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_id"], ["user_table.id"], name="fk_checklist_changed_by_id"
        ),
        sa.ForeignKeyConstraint(["creator_id"], ["user_table.id"], name="fk_checklist_creator_id"),
        sa.ForeignKeyConstraint(
            ["invalid_by_id"], ["user_table.id"], name="fk_checklist_invalid_by_id"
        ),
        sa.ForeignKeyConstraint(
            ["locked_by_id"], ["user_table.id"], name="fk_checklist_locked_by_id"
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["product_table.id"],
            name="fk_checklist_product_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["project_table.id"],
            name="fk_checklist_project_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["released_by_id"], ["user_table.id"], name="fk_checklist_released_by_id"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("lineage", "revision", name="uq_checklist_lineage_revision"),
    )
    op.create_index(
        op.f("ix_checklist_table_changed_by_id"), "checklist_table", ["changed_by_id"], unique=False
    )
    op.create_index(
        op.f("ix_checklist_table_creator_id"), "checklist_table", ["creator_id"], unique=False
    )
    op.create_index(
        op.f("ix_checklist_table_document_number"),
        "checklist_table",
        ["document_number"],
        unique=False,
    )
    op.create_index(
        op.f("ix_checklist_table_invalid_by_id"), "checklist_table", ["invalid_by_id"], unique=False
    )
    op.create_index(
        op.f("ix_checklist_table_lineage"), "checklist_table", ["lineage"], unique=False
    )
    op.create_index(
        op.f("ix_checklist_table_locked_by_id"), "checklist_table", ["locked_by_id"], unique=False
    )
    op.create_index(
        op.f("ix_checklist_table_product_id"), "checklist_table", ["product_id"], unique=False
    )
    op.create_index(
        op.f("ix_checklist_table_project_id"), "checklist_table", ["project_id"], unique=False
    )
    op.create_index(
        op.f("ix_checklist_table_public_id"), "checklist_table", ["public_id"], unique=True
    )
    op.create_index(
        op.f("ix_checklist_table_released_by_id"),
        "checklist_table",
        ["released_by_id"],
        unique=False,
    )
    op.create_index(op.f("ix_checklist_table_type"), "checklist_table", ["type"], unique=False)
    op.create_index(
        op.f("ix_checklist_table_verdict"), "checklist_table", ["verdict"], unique=False
    )
    op.create_index(
        "uq_checklist_document_number_latest",
        "checklist_table",
        ["document_number"],
        unique=True,
        postgresql_where=sa.text("is_latest IS true"),
        sqlite_where=sa.text("is_latest = 1"),
    )
    op.create_index(
        "uq_checklist_lineage_latest",
        "checklist_table",
        ["lineage"],
        unique=True,
        postgresql_where=sa.text("is_latest IS true"),
        sqlite_where=sa.text("is_latest = 1"),
    )
    op.create_table(
        "item_picture_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("made_item_id", sa.Integer(), nullable=True),
        sa.Column("bought_item_id", sa.Integer(), nullable=True),
        sa.Column("source_item_id", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("file_name", sa.String(), nullable=False),
        sa.Column("image_path", sa.String(), nullable=True),
        sa.Column("image_mime_type", sa.String(), nullable=True),
        sa.Column("image_size_bytes", sa.Integer(), nullable=True),
        sa.Column("thumbnail_path", sa.String(), nullable=True),
        sa.Column("thumbnail_mime_type", sa.String(), nullable=True),
        sa.Column("thumbnail_size_bytes", sa.Integer(), nullable=True),
        sa.Column("sha256", sa.String(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            (
                "(CASE WHEN made_item_id IS NULL THEN 0 ELSE 1 END) + (CASE WHEN bought_item_id "
                "IS NULL THEN 0 ELSE 1 END) + (CASE WHEN source_item_id IS NULL THEN 0 ELSE 1 "
                "END) = 1"
            ),
            name="ck_item_picture_one_item",
        ),
        sa.ForeignKeyConstraint(
            ["bought_item_id"], ["bought_item_table.id"], name="fk_item_picture_bought_item_id"
        ),
        sa.ForeignKeyConstraint(
            ["made_item_id"], ["made_item_table.id"], name="fk_item_picture_made_item_id"
        ),
        sa.ForeignKeyConstraint(
            ["source_item_id"], ["source_item_table.id"], name="fk_item_picture_source_item_id"
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_user_id"], ["user_table.id"], name="fk_item_picture_uploader_id"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bought_item_id", "source", name="uq_item_picture_bought_item_source"),
        sa.UniqueConstraint("made_item_id", "source", name="uq_item_picture_made_item_source"),
        sa.UniqueConstraint("source_item_id", "source", name="uq_item_picture_source_item_source"),
    )
    op.create_index(
        op.f("ix_item_picture_table_public_id"), "item_picture_table", ["public_id"], unique=True
    )
    op.create_index(
        op.f("ix_item_picture_table_uploaded_by_user_id"),
        "item_picture_table",
        ["uploaded_by_user_id"],
        unique=False,
    )
    op.create_table(
        "made_item_article_group_table",
        sa.Column("made_item_id", sa.Integer(), nullable=False),
        sa.Column("article_group_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["article_group_id"],
            ["article_group_table.id"],
            name="fk_made_item_article_group_article_group_id",
        ),
        sa.ForeignKeyConstraint(
            ["made_item_id"], ["made_item_table.id"], name="fk_made_item_article_group_made_item_id"
        ),
        sa.PrimaryKeyConstraint("made_item_id", "article_group_id"),
    )
    op.create_index(
        op.f("ix_made_item_article_group_table_article_group_id"),
        "made_item_article_group_table",
        ["article_group_id"],
        unique=False,
    )
    op.create_table(
        "made_item_demand_item_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "changes",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column(
            "quantity",
            sa.Numeric(precision=18, scale=6, asdecimal=False),
            nullable=False,
        ),
        sa.Column("unit", sa.String(), nullable=False),
        sa.Column(
            "items_per_unit",
            sa.Numeric(precision=18, scale=6, asdecimal=False),
            nullable=False,
        ),
        sa.Column("high_priority", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "notify_on_delivery", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("desired_delivery_date", sa.Date(), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fulfilled_manually_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("is_alteration", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("made_item_id", sa.Integer(), nullable=False),
        sa.Column("alteration_of_made_item_id", sa.Integer(), nullable=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("bucket_id", sa.Integer(), nullable=True),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["alteration_of_made_item_id"],
            ["made_item_table.id"],
            name="fk_made_item_demand_item_alteration_of_made_item_id",
        ),
        sa.ForeignKeyConstraint(
            ["bucket_id"],
            ["made_item_demand_bucket_table.id"],
            name="fk_made_item_demand_item_bucket_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_id"],
            ["user_table.id"],
            name="fk_made_item_demand_item_table_changed_by_id",
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"], ["user_table.id"], name="fk_made_item_demand_item_creator_id"
        ),
        sa.ForeignKeyConstraint(
            ["made_item_id"], ["made_item_table.id"], name="fk_made_item_demand_item_made_item_id"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project_table.id"], name="fk_made_item_demand_item_project_id"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_made_item_demand_item_table_alteration_of_made_item_id"),
        "made_item_demand_item_table",
        ["alteration_of_made_item_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_made_item_demand_item_table_bucket_id"),
        "made_item_demand_item_table",
        ["bucket_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_made_item_demand_item_table_changed_by_id"),
        "made_item_demand_item_table",
        ["changed_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_made_item_demand_item_table_creator_id"),
        "made_item_demand_item_table",
        ["creator_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_made_item_demand_item_table_made_item_id"),
        "made_item_demand_item_table",
        ["made_item_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_made_item_demand_item_table_project_id"),
        "made_item_demand_item_table",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_made_item_demand_item_table_public_id"),
        "made_item_demand_item_table",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_made_item_demand_item_table_status"),
        "made_item_demand_item_table",
        ["status"],
        unique=False,
    )
    op.create_table(
        "made_item_file_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("made_item_id", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(), nullable=False),
        sa.Column("stored_name", sa.String(), nullable=False),
        sa.Column("mime_type", sa.String(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(), nullable=False),
        sa.Column("sha256", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["made_item_id"], ["made_item_table.id"], name="fk_made_item_file_made_item_id"
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_user_id"], ["user_table.id"], name="fk_made_item_file_uploader_id"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stored_name"),
    )
    op.create_index(
        op.f("ix_made_item_file_table_made_item_id"),
        "made_item_file_table",
        ["made_item_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_made_item_file_table_public_id"),
        "made_item_file_table",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_made_item_file_table_uploaded_by_user_id"),
        "made_item_file_table",
        ["uploaded_by_user_id"],
        unique=False,
    )
    op.create_table(
        "made_item_process_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("estimated_setup_minutes", sa.Integer(), nullable=True),
        sa.Column("estimated_minutes_per_piece", sa.Float(), nullable=True),
        sa.Column("made_item_id", sa.Integer(), nullable=False),
        sa.Column("fabrication_method_id", sa.Integer(), nullable=True),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("inspection_method_id", sa.Integer(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("group_index", sa.Integer(), nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            (
                "(role = 'fabrication' AND fabrication_method_id IS NOT NULL) OR (role = "
                "'inspection' AND fabrication_method_id IS NULL)"
            ),
            name="ck_made_item_process_role_method",
        ),
        sa.CheckConstraint(
            (
                "(role = 'inspection' AND inspection_method_id IS NOT NULL) OR (role = "
                "'fabrication' AND inspection_method_id IS NULL)"
            ),
            name="ck_made_item_process_inspection_method",
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"], ["user_table.id"], name="fk_made_item_process_creator_id"
        ),
        sa.ForeignKeyConstraint(
            ["fabrication_method_id"],
            ["fabrication_method_table.id"],
            name="fk_made_item_process_fabrication_method_id",
        ),
        sa.ForeignKeyConstraint(
            ["inspection_method_id"],
            ["inspection_method_table.id"],
            name="fk_made_item_process_inspection_method_id",
        ),
        sa.ForeignKeyConstraint(
            ["made_item_id"],
            ["made_item_table.id"],
            name="fk_made_item_process_made_item_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_made_item_process_table_creator_id"),
        "made_item_process_table",
        ["creator_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_made_item_process_table_fabrication_method_id"),
        "made_item_process_table",
        ["fabrication_method_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_made_item_process_table_inspection_method_id"),
        "made_item_process_table",
        ["inspection_method_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_made_item_process_table_made_item_id"),
        "made_item_process_table",
        ["made_item_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_made_item_process_table_public_id"),
        "made_item_process_table",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "meeting_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("meeting_number", sa.String(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("location", sa.String(), nullable=True),
        sa.Column("next_meeting_date", sa.Date(), nullable=True),
        sa.Column("next_meeting_time", sa.Time(), nullable=True),
        sa.Column("next_meeting_location", sa.String(), nullable=True),
        sa.Column("follow_up_of_id", sa.Integer(), nullable=True),
        sa.Column("invalid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalid_by_id", sa.Integer(), nullable=True),
        sa.Column("invalid_reason", sa.Text(), nullable=True),
        sa.Column("issue_number", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_printed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("changed", sa.DateTime(timezone=True), nullable=True),
        sa.Column("edit_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "(project_id IS NULL) <> (product_id IS NULL)", name="ck_meeting_table_one_owner"
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_id"], ["user_table.id"], name="fk_meeting_table_changed_by_id"
        ),
        sa.ForeignKeyConstraint(["creator_id"], ["user_table.id"], name="fk_meeting_creator_id"),
        sa.ForeignKeyConstraint(
            ["follow_up_of_id"],
            ["meeting_table.id"],
            name="fk_meeting_follow_up_of_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["invalid_by_id"], ["user_table.id"], name="fk_meeting_invalid_by_id"
        ),
        sa.ForeignKeyConstraint(["product_id"], ["product_table.id"], name="fk_meeting_product_id"),
        sa.ForeignKeyConstraint(["project_id"], ["project_table.id"], name="fk_meeting_project_id"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_meeting_table_changed_by_id"), "meeting_table", ["changed_by_id"], unique=False
    )
    op.create_index(
        op.f("ix_meeting_table_creator_id"), "meeting_table", ["creator_id"], unique=False
    )
    op.create_index(
        op.f("ix_meeting_table_follow_up_of_id"), "meeting_table", ["follow_up_of_id"], unique=False
    )
    op.create_index(
        op.f("ix_meeting_table_invalid_by_id"), "meeting_table", ["invalid_by_id"], unique=False
    )
    op.create_index(
        op.f("ix_meeting_table_meeting_number"), "meeting_table", ["meeting_number"], unique=True
    )
    op.create_index(
        op.f("ix_meeting_table_product_id"), "meeting_table", ["product_id"], unique=False
    )
    op.create_index(
        op.f("ix_meeting_table_project_id"), "meeting_table", ["project_id"], unique=False
    )
    op.create_index(op.f("ix_meeting_table_public_id"), "meeting_table", ["public_id"], unique=True)
    op.create_index(
        op.f("ix_meeting_table_starts_at"), "meeting_table", ["starts_at"], unique=False
    )
    op.create_table(
        "product_device_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "changes",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column("archived", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("location", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("driving_medium_id", sa.Integer(), nullable=True),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("name_utf8", sa.String(), nullable=False),
        sa.Column("name_ascii", sa.String(), nullable=False),
        sa.Column("name_ascii_key", sa.String(), nullable=False),
        sa.Column("group_key", sa.String(), nullable=False),
        sa.Column("kind_id", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("initial_position_id", sa.Integer(), nullable=True),
        sa.Column("initial_position_value", sa.Float(), nullable=True),
        sa.Column("energy_loss_behaviour_id", sa.Integer(), nullable=True),
        sa.Column("energy_restoration_behaviour_id", sa.Integer(), nullable=True),
        sa.Column("monitoring_time_ms", sa.Integer(), nullable=True),
        sa.Column("driven_by_id", sa.Integer(), nullable=True),
        sa.Column("driven_position_map", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("safety_relevant", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("position_labels", sa.JSON(), nullable=False),
        sa.Column("travel_times_ms", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("rendering_file_id", sa.Integer(), nullable=True),
        sa.Column("assembly_file_id", sa.Integer(), nullable=True),
        sa.Column("marker_x", sa.Float(), nullable=True),
        sa.Column("marker_y", sa.Float(), nullable=True),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("edit_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["assembly_file_id"],
            ["product_file_table.id"],
            name="fk_product_device_assembly_file_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_id"], ["user_table.id"], name="fk_product_device_table_changed_by_id"
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"], ["user_table.id"], name="fk_product_device_creator_id"
        ),
        sa.ForeignKeyConstraint(
            ["driven_by_id"], ["product_device_table.id"], name="fk_product_device_driven_by_id"
        ),
        sa.ForeignKeyConstraint(
            ["driving_medium_id"],
            ["product_device_option_table.id"],
            name="fk_product_device_driving_medium_id",
        ),
        sa.ForeignKeyConstraint(
            ["energy_loss_behaviour_id"],
            ["product_device_option_table.id"],
            name="fk_product_device_energy_loss_behaviour_id",
        ),
        sa.ForeignKeyConstraint(
            ["energy_restoration_behaviour_id"],
            ["product_device_option_table.id"],
            name="fk_product_device_energy_restoration_behaviour_id",
        ),
        sa.ForeignKeyConstraint(
            ["initial_position_id"],
            ["product_device_kind_position_table.id"],
            name="fk_product_device_initial_position_id",
        ),
        sa.ForeignKeyConstraint(
            ["kind_id"], ["product_device_kind_table.id"], name="fk_product_device_kind_id"
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["product_table.id"], name="fk_product_device_product_id"
        ),
        sa.ForeignKeyConstraint(
            ["rendering_file_id"],
            ["product_file_table.id"],
            name="fk_product_device_rendering_file_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "product_id", "name_ascii_key", name="uq_product_device_name_ascii_key"
        ),
        sa.UniqueConstraint("product_id", "name_utf8", name="uq_product_device_name_utf8"),
    )
    op.create_index(
        "ix_product_device_group_key",
        "product_device_table",
        ["product_id", "group_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_device_table_assembly_file_id"),
        "product_device_table",
        ["assembly_file_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_device_table_changed_by_id"),
        "product_device_table",
        ["changed_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_device_table_creator_id"),
        "product_device_table",
        ["creator_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_device_table_driven_by_id"),
        "product_device_table",
        ["driven_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_device_table_driving_medium_id"),
        "product_device_table",
        ["driving_medium_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_device_table_energy_loss_behaviour_id"),
        "product_device_table",
        ["energy_loss_behaviour_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_device_table_energy_restoration_behaviour_id"),
        "product_device_table",
        ["energy_restoration_behaviour_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_device_table_initial_position_id"),
        "product_device_table",
        ["initial_position_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_device_table_kind_id"), "product_device_table", ["kind_id"], unique=False
    )
    op.create_index(
        op.f("ix_product_device_table_product_id"),
        "product_device_table",
        ["product_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_device_table_public_id"),
        "product_device_table",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_product_device_table_rendering_file_id"),
        "product_device_table",
        ["rendering_file_id"],
        unique=False,
    )
    op.create_table(
        "project_contact_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("contact_id", sa.Integer(), nullable=False),
        sa.Column(
            "receives_meeting_notes", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["contact_id"],
            ["contact_table.id"],
            name="fk_project_contact_contact_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"], ["user_table.id"], name="fk_project_contact_creator_id"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["project_table.id"],
            name="fk_project_contact_project_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "contact_id", name="uq_project_contact_project_contact"),
    )
    op.create_index(
        op.f("ix_project_contact_table_contact_id"),
        "project_contact_table",
        ["contact_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_project_contact_table_creator_id"),
        "project_contact_table",
        ["creator_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_project_contact_table_public_id"),
        "project_contact_table",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "report_journal_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("document", sa.String(length=64), nullable=False),
        sa.Column("root_type", sa.String(length=32), nullable=False),
        sa.Column("root_id", sa.Integer(), nullable=False),
        sa.Column("lineage", sa.Uuid(), nullable=False),
        sa.Column("revision", sa.String(length=16), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("report_version", sa.String(length=64), nullable=False),
        sa.Column("engine_version", sa.Integer(), nullable=True),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("print_job_id", sa.Integer(), nullable=True),
        sa.Column("copies", sa.Integer(), nullable=True),
        sa.Column("recipients", sa.JSON(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["user_table.id"], name="fk_report_journal_actor_id"),
        sa.ForeignKeyConstraint(
            ["print_job_id"],
            ["print_job_table.id"],
            name="fk_report_journal_print_job_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_report_journal_table_actor_id"), "report_journal_table", ["actor_id"], unique=False
    )
    op.create_index(
        op.f("ix_report_journal_table_print_job_id"),
        "report_journal_table",
        ["print_job_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_report_journal_table_public_id"),
        "report_journal_table",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        "ix_report_journal_table_root_lineage",
        "report_journal_table",
        ["root_type", "lineage"],
        unique=False,
    )
    op.create_table(
        "source_item_demand_item_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "changes",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column("status", sa.String(), server_default="open", nullable=False),
        sa.Column(
            "quantity",
            sa.Numeric(precision=18, scale=6, asdecimal=False),
            nullable=False,
        ),
        sa.Column("unit", sa.String(), nullable=False),
        sa.Column(
            "items_per_unit",
            sa.Numeric(precision=18, scale=6, asdecimal=False),
            nullable=False,
        ),
        sa.Column("high_priority", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "notify_on_delivery", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("desired_delivery_date", sa.Date(), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fulfilled_manually_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("bought_item_id", sa.Integer(), nullable=True),
        sa.Column("source_item_id", sa.Integer(), nullable=True),
        sa.Column("lot_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("bucket_id", sa.Integer(), nullable=True),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["bought_item_id"],
            ["bought_item_table.id"],
            name="fk_source_item_demand_bought_item_id",
        ),
        sa.ForeignKeyConstraint(
            ["bucket_id"],
            ["source_item_demand_bucket_table.id"],
            name="fk_source_item_demand_item_bucket_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_id"],
            ["user_table.id"],
            name="fk_source_item_demand_item_table_changed_by_id",
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"], ["user_table.id"], name="fk_source_item_demand_creator_id"
        ),
        sa.ForeignKeyConstraint(
            ["lot_id"], ["production_lot_table.id"], name="fk_source_item_demand_lot_id"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project_table.id"], name="fk_source_item_demand_project_id"
        ),
        sa.ForeignKeyConstraint(
            ["source_item_id"],
            ["source_item_table.id"],
            name="fk_source_item_demand_source_item_id",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_source_item_demand_item_table_bought_item_id"),
        "source_item_demand_item_table",
        ["bought_item_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_item_demand_item_table_bucket_id"),
        "source_item_demand_item_table",
        ["bucket_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_item_demand_item_table_changed_by_id"),
        "source_item_demand_item_table",
        ["changed_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_item_demand_item_table_creator_id"),
        "source_item_demand_item_table",
        ["creator_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_item_demand_item_table_project_id"),
        "source_item_demand_item_table",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_item_demand_item_table_public_id"),
        "source_item_demand_item_table",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_source_item_demand_item_table_source_item_id"),
        "source_item_demand_item_table",
        ["source_item_id"],
        unique=False,
    )
    op.create_index(
        "uq_source_item_demand_lot_id_active",
        "source_item_demand_item_table",
        ["lot_id"],
        unique=True,
        postgresql_where=sa.text("canceled_at IS NULL"),
        sqlite_where=sa.text("canceled_at IS NULL"),
    )
    op.create_table(
        "lot_event_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lot_id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("actor_username", sa.String(), nullable=True),
        sa.Column("actor_full_name", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("entity", sa.String(), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("summary", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["lot_id"], ["production_lot_table.id"], name="fk_lot_event_lot_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_lot_event_table_event_type"), "lot_event_table", ["event_type"], unique=False
    )
    op.create_index(op.f("ix_lot_event_table_lot_id"), "lot_event_table", ["lot_id"], unique=False)
    op.create_index(
        op.f("ix_lot_event_table_occurred_at"), "lot_event_table", ["occurred_at"], unique=False
    )
    op.create_index(
        op.f("ix_lot_event_table_public_id"), "lot_event_table", ["public_id"], unique=True
    )
    op.create_table(
        "lot_position_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "changes",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column(
            "quantity",
            sa.Numeric(precision=18, scale=6, asdecimal=False),
            nullable=False,
        ),
        sa.Column(
            "quantity_completed",
            sa.Numeric(precision=18, scale=6, asdecimal=False),
            nullable=False,
        ),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("planned_pickup_date", sa.Date(), nullable=True),
        sa.Column("planned_delivery_date", sa.Date(), nullable=True),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("lot_id", sa.Integer(), nullable=False),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "quantity_completed <= quantity", name="ck_lot_position_quantity_completed_le_quantity"
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_id"], ["user_table.id"], name="fk_lot_position_table_changed_by_id"
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"], ["user_table.id"], name="fk_lot_position_creator_id"
        ),
        sa.ForeignKeyConstraint(
            ["lot_id"],
            ["production_lot_table.id"],
            name="fk_lot_position_lot_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("lot_id", "sequence", name="uq_lot_position_lot_id_sequence"),
    )
    op.create_index(
        op.f("ix_lot_position_table_changed_by_id"),
        "lot_position_table",
        ["changed_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_lot_position_table_creator_id"), "lot_position_table", ["creator_id"], unique=False
    )
    op.create_index(
        op.f("ix_lot_position_table_lot_id"), "lot_position_table", ["lot_id"], unique=False
    )
    op.create_index(
        op.f("ix_lot_position_table_public_id"), "lot_position_table", ["public_id"], unique=True
    )
    op.create_table(
        "calculation_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tool", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("inputs", sa.JSON(), nullable=False),
        sa.Column("results", sa.JSON(), nullable=False),
        sa.Column("input_version", sa.Integer(), nullable=False),
        sa.Column("engine_version", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("product_device_id", sa.Integer(), nullable=True),
        sa.Column("product_device_name", sa.String(), nullable=True),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "changes",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column("document_number", sa.String(length=32), nullable=False),
        sa.Column("lineage", sa.Uuid(), nullable=False),
        sa.Column("revision", sa.String(length=16), nullable=False),
        sa.Column("revision_reason", sa.String(), nullable=True),
        sa.Column("is_latest", sa.Boolean(), nullable=False),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalid_reason", sa.String(), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("editor_ids", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("lock_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("released_by_id", sa.Integer(), nullable=True),
        sa.Column("invalid_by_id", sa.Integer(), nullable=True),
        sa.Column("locked_by_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "project_id IS NULL OR product_id IS NULL", name="ck_calculation_single_owner"
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_id"], ["user_table.id"], name="fk_calculation_changed_by_id"
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"], ["user_table.id"], name="fk_calculation_creator_id"
        ),
        sa.ForeignKeyConstraint(
            ["invalid_by_id"], ["user_table.id"], name="fk_calculation_invalid_by_id"
        ),
        sa.ForeignKeyConstraint(
            ["locked_by_id"], ["user_table.id"], name="fk_calculation_locked_by_id"
        ),
        sa.ForeignKeyConstraint(
            ["product_device_id"],
            ["product_device_table.id"],
            name="fk_calculation_product_device_id",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["product_table.id"],
            name="fk_calculation_product_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["project_table.id"],
            name="fk_calculation_project_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["released_by_id"], ["user_table.id"], name="fk_calculation_released_by_id"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("lineage", "revision", name="uq_calculation_lineage_revision"),
    )
    op.create_index(
        op.f("ix_calculation_table_changed_by_id"),
        "calculation_table",
        ["changed_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_calculation_table_creator_id"), "calculation_table", ["creator_id"], unique=False
    )
    op.create_index(
        op.f("ix_calculation_table_document_number"),
        "calculation_table",
        ["document_number"],
        unique=False,
    )
    op.create_index(
        op.f("ix_calculation_table_invalid_by_id"),
        "calculation_table",
        ["invalid_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_calculation_table_lineage"), "calculation_table", ["lineage"], unique=False
    )
    op.create_index(
        op.f("ix_calculation_table_locked_by_id"),
        "calculation_table",
        ["locked_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_calculation_table_product_device_id"),
        "calculation_table",
        ["product_device_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_calculation_table_product_id"), "calculation_table", ["product_id"], unique=False
    )
    op.create_index(
        op.f("ix_calculation_table_project_id"), "calculation_table", ["project_id"], unique=False
    )
    op.create_index(
        op.f("ix_calculation_table_public_id"), "calculation_table", ["public_id"], unique=True
    )
    op.create_index(
        op.f("ix_calculation_table_released_by_id"),
        "calculation_table",
        ["released_by_id"],
        unique=False,
    )
    op.create_index(op.f("ix_calculation_table_tool"), "calculation_table", ["tool"], unique=False)
    op.create_index(
        "uq_calculation_document_number_latest",
        "calculation_table",
        ["document_number"],
        unique=True,
        postgresql_where=sa.text("is_latest IS true"),
        sqlite_where=sa.text("is_latest = 1"),
    )
    op.create_index(
        "uq_calculation_lineage_latest",
        "calculation_table",
        ["lineage"],
        unique=True,
        postgresql_where=sa.text("is_latest IS true"),
        sqlite_where=sa.text("is_latest = 1"),
    )
    op.create_table(
        "made_item_allocation_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("demand_item_id", sa.Integer(), nullable=False),
        sa.Column("lot_id", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column(
            "quantity",
            sa.Numeric(precision=18, scale=6, asdecimal=False),
            nullable=False,
        ),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["user_table.id"], name="fk_made_item_allocation_created_by_id"
        ),
        sa.ForeignKeyConstraint(
            ["demand_item_id"],
            ["made_item_demand_item_table.id"],
            name="fk_made_item_allocation_demand_item_id",
        ),
        sa.ForeignKeyConstraint(
            ["lot_id"], ["production_lot_table.id"], name="fk_made_item_allocation_lot_id"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("demand_item_id", "lot_id", name="uq_made_item_allocation_demand_lot"),
    )
    op.create_index(
        op.f("ix_made_item_allocation_table_created_by_id"),
        "made_item_allocation_table",
        ["created_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_made_item_allocation_table_demand_item_id"),
        "made_item_allocation_table",
        ["demand_item_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_made_item_allocation_table_lot_id"),
        "made_item_allocation_table",
        ["lot_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_made_item_allocation_table_public_id"),
        "made_item_allocation_table",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        "uq_made_item_allocation_demand_stock",
        "made_item_allocation_table",
        ["demand_item_id"],
        unique=True,
        postgresql_where=sa.text("source = 'stock'"),
        sqlite_where=sa.text("source = 'stock'"),
    )
    op.create_table(
        "meeting_attendee_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("meeting_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("contact_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("status", sa.String(), server_default="present", nullable=False),
        sa.Column("anonymised_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            (
                "(kind = 'user' AND user_id IS NOT NULL AND contact_id IS NULL) OR (kind = "
                "'contact' AND contact_id IS NOT NULL AND user_id IS NULL) OR (kind = 'guest' "
                "AND user_id IS NULL AND contact_id IS NULL)"
            ),
            name="ck_meeting_attendee_table_kind",
        ),
        sa.ForeignKeyConstraint(
            ["contact_id"], ["contact_table.id"], name="fk_meeting_attendee_contact_id"
        ),
        sa.ForeignKeyConstraint(
            ["meeting_id"],
            ["meeting_table.id"],
            name="fk_meeting_attendee_meeting_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user_table.id"], name="fk_meeting_attendee_user_id"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("meeting_id", "contact_id", name="uq_meeting_attendee_contact"),
        sa.UniqueConstraint("meeting_id", "user_id", name="uq_meeting_attendee_user"),
    )
    op.create_index(
        op.f("ix_meeting_attendee_table_contact_id"),
        "meeting_attendee_table",
        ["contact_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_meeting_attendee_table_meeting_id"),
        "meeting_attendee_table",
        ["meeting_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_meeting_attendee_table_public_id"),
        "meeting_attendee_table",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_meeting_attendee_table_user_id"),
        "meeting_attendee_table",
        ["user_id"],
        unique=False,
    )
    op.create_table(
        "meeting_card_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("meeting_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        sa.Column("scope", sa.String(), nullable=True),
        sa.Column("scope_icon", sa.String(), nullable=True),
        sa.Column("body", sa.Text(), server_default="", nullable=False),
        sa.Column("internal", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("changed", sa.DateTime(timezone=True), nullable=True),
        sa.Column("edit_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["changed_by_id"], ["user_table.id"], name="fk_meeting_card_table_changed_by_id"
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"], ["user_table.id"], name="fk_meeting_card_creator_id"
        ),
        sa.ForeignKeyConstraint(
            ["meeting_id"],
            ["meeting_table.id"],
            name="fk_meeting_card_meeting_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_meeting_card_table_changed_by_id"),
        "meeting_card_table",
        ["changed_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_meeting_card_table_creator_id"), "meeting_card_table", ["creator_id"], unique=False
    )
    op.create_index(
        op.f("ix_meeting_card_table_meeting_id"), "meeting_card_table", ["meeting_id"], unique=False
    )
    op.create_index(
        op.f("ix_meeting_card_table_public_id"), "meeting_card_table", ["public_id"], unique=True
    )
    op.create_table(
        "meeting_event_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("meeting_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("card_id", sa.Integer(), nullable=True),
        sa.Column("todo_id", sa.Integer(), nullable=True),
        sa.Column("file_id", sa.Integer(), nullable=True),
        sa.Column("summary", sa.String(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["user_table.id"], name="fk_meeting_event_actor_id"),
        sa.ForeignKeyConstraint(
            ["meeting_id"],
            ["meeting_table.id"],
            name="fk_meeting_event_meeting_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_meeting_event_table_actor_id"), "meeting_event_table", ["actor_id"], unique=False
    )
    op.create_index(
        op.f("ix_meeting_event_table_meeting_id"),
        "meeting_event_table",
        ["meeting_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_meeting_event_table_public_id"), "meeting_event_table", ["public_id"], unique=True
    )
    op.create_table(
        "meeting_notes_draft_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("meeting_id", sa.Integer(), nullable=True),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("token_name", sa.String(), nullable=True),
        sa.Column("new_meeting", sa.JSON(), nullable=True),
        sa.Column("next_meeting", sa.JSON(), nullable=True),
        sa.Column("attendees", sa.JSON(), nullable=False),
        sa.Column("cards", sa.JSON(), nullable=False),
        sa.Column("review_note", sa.String(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            (
                "(CASE WHEN meeting_id IS NULL THEN 0 ELSE 1 END) + (CASE WHEN project_id IS "
                "NULL THEN 0 ELSE 1 END) + (CASE WHEN product_id IS NULL THEN 0 ELSE 1 END) = 1"
            ),
            name="ck_meeting_notes_draft_table_one_target",
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"],
            ["user_table.id"],
            name="fk_meeting_notes_draft_creator_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["meeting_id"],
            ["meeting_table.id"],
            name="fk_meeting_notes_draft_meeting_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["product_table.id"],
            name="fk_meeting_notes_draft_product_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["project_table.id"],
            name="fk_meeting_notes_draft_project_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_meeting_notes_draft_table_created"),
        "meeting_notes_draft_table",
        ["created"],
        unique=False,
    )
    op.create_index(
        op.f("ix_meeting_notes_draft_table_creator_id"),
        "meeting_notes_draft_table",
        ["creator_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_meeting_notes_draft_table_meeting_id"),
        "meeting_notes_draft_table",
        ["meeting_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_meeting_notes_draft_table_product_id"),
        "meeting_notes_draft_table",
        ["product_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_meeting_notes_draft_table_project_id"),
        "meeting_notes_draft_table",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_meeting_notes_draft_table_public_id"),
        "meeting_notes_draft_table",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "meeting_notification_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("meeting_id", sa.Integer(), nullable=False),
        sa.Column("recipient_id", sa.Integer(), nullable=False),
        sa.Column("actor_ids", sa.JSON(), nullable=False),
        sa.Column("mention_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("todo_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("first_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["meeting_id"],
            ["meeting_table.id"],
            name="fk_meeting_notification_meeting_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["recipient_id"], ["user_table.id"], name="fk_meeting_notification_recipient_id"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "meeting_id", "recipient_id", name="uq_meeting_notification_meeting_recipient"
        ),
    )
    op.create_index(
        op.f("ix_meeting_notification_table_first_at"),
        "meeting_notification_table",
        ["first_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_meeting_notification_table_meeting_id"),
        "meeting_notification_table",
        ["meeting_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_meeting_notification_table_public_id"),
        "meeting_notification_table",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_meeting_notification_table_recipient_id"),
        "meeting_notification_table",
        ["recipient_id"],
        unique=False,
    )
    op.create_table(
        "meeting_snapshot_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("meeting_id", sa.Integer(), nullable=False),
        sa.Column("journal_entry_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=False),
        sa.Column("issue_number", sa.Integer(), server_default="0", nullable=False),
        sa.Column("issue_draft", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("language", sa.String(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("meeting", sa.JSON(), nullable=False),
        sa.Column("cards", sa.JSON(), nullable=False),
        sa.Column("attendees", sa.JSON(), nullable=False),
        sa.Column("files", sa.JSON(), nullable=False),
        sa.Column("attachments", sa.JSON(), nullable=False),
        sa.Column("recipients", sa.JSON(), nullable=False),
        sa.Column("cc", sa.JSON(), nullable=False),
        sa.Column("subject", sa.String(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["user_table.id"], name="fk_meeting_snapshot_actor_id"
        ),
        sa.ForeignKeyConstraint(
            ["meeting_id"],
            ["meeting_table.id"],
            name="fk_meeting_snapshot_meeting_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_meeting_snapshot_table_actor_id"),
        "meeting_snapshot_table",
        ["actor_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_meeting_snapshot_table_journal_entry_id"),
        "meeting_snapshot_table",
        ["journal_entry_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_meeting_snapshot_table_meeting_id"),
        "meeting_snapshot_table",
        ["meeting_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_meeting_snapshot_table_public_id"),
        "meeting_snapshot_table",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "meeting_tag_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("meeting_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["meeting_id"],
            ["meeting_table.id"],
            name="fk_meeting_tag_meeting_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("meeting_id", "name", name="uq_meeting_tag_meeting_name"),
    )
    op.create_index(
        op.f("ix_meeting_tag_table_meeting_id"), "meeting_tag_table", ["meeting_id"], unique=False
    )
    op.create_index(
        op.f("ix_meeting_tag_table_public_id"), "meeting_tag_table", ["public_id"], unique=True
    )
    op.create_table(
        "product_device_check_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("plan", sa.String(), nullable=False),
        sa.Column("checked_by_id", sa.Integer(), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["checked_by_id"], ["user_table.id"], name="fk_product_device_check_checked_by_id"
        ),
        sa.ForeignKeyConstraint(
            ["device_id"], ["product_device_table.id"], name="fk_product_device_check_device_id"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_id", "plan", name="uq_product_device_check_device_plan"),
    )
    op.create_index(
        op.f("ix_product_device_check_table_checked_by_id"),
        "product_device_check_table",
        ["checked_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_device_check_table_device_id"),
        "product_device_check_table",
        ["device_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_device_check_table_public_id"),
        "product_device_check_table",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "product_device_component_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("bought_item_id", sa.Integer(), nullable=True),
        sa.Column("eplan_tag", sa.String(), nullable=True),
        sa.Column("b10d_cycles", sa.Integer(), nullable=True),
        sa.Column("mttfd_years", sa.Float(), nullable=True),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("signals", sa.JSON(), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["bought_item_id"],
            ["bought_item_table.id"],
            name="fk_product_device_component_bought_item_id",
        ),
        sa.ForeignKeyConstraint(
            ["device_id"], ["product_device_table.id"], name="fk_product_device_component_device_id"
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["product_table.id"], name="fk_product_device_component_product_id"
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["product_device_option_table.id"],
            name="fk_product_device_component_role_id",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_product_device_component_table_bought_item_id"),
        "product_device_component_table",
        ["bought_item_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_device_component_table_device_id"),
        "product_device_component_table",
        ["device_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_device_component_table_product_id"),
        "product_device_component_table",
        ["product_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_device_component_table_public_id"),
        "product_device_component_table",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_product_device_component_table_role_id"),
        "product_device_component_table",
        ["role_id"],
        unique=False,
    )
    op.create_index(
        "uq_product_device_component_eplan_tag",
        "product_device_component_table",
        ["product_id", "eplan_tag"],
        unique=True,
        postgresql_where=sa.text("eplan_tag IS NOT NULL"),
        sqlite_where=sa.text("eplan_tag IS NOT NULL"),
    )
    op.create_table(
        "lot_position_provision_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lot_position_id", sa.Integer(), nullable=False),
        sa.Column(
            "quantity",
            sa.Numeric(precision=18, scale=6, asdecimal=False),
            nullable=False,
        ),
        sa.Column("provision_date", sa.Date(), nullable=False),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["creator_id"], ["user_table.id"], name="fk_lot_position_provision_creator_id"
        ),
        sa.ForeignKeyConstraint(
            ["lot_position_id"],
            ["lot_position_table.id"],
            name="fk_lot_position_provision_lot_position_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_lot_position_provision_table_creator_id"),
        "lot_position_provision_table",
        ["creator_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_lot_position_provision_table_lot_position_id"),
        "lot_position_provision_table",
        ["lot_position_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_lot_position_provision_table_public_id"),
        "lot_position_provision_table",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "production_order_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "changes",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column("production_order_number", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("priority", sa.String(), nullable=False),
        sa.Column("pinned", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("queue_sequence", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "quantity",
            sa.Numeric(precision=18, scale=6, asdecimal=False),
            nullable=False,
        ),
        sa.Column(
            "quantity_completed",
            sa.Numeric(precision=18, scale=6, asdecimal=False),
            server_default="0",
            nullable=False,
        ),
        sa.Column("estimated_duration_minutes", sa.Integer(), server_default="0", nullable=False),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("planned_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("planned_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("not_before", sa.Date(), nullable=True),
        sa.Column("actual_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("edit_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("planned_by_id", sa.Integer(), nullable=True),
        sa.Column("started_operator_id", sa.Integer(), nullable=True),
        sa.Column("planned_end_at_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("machine_id", sa.Integer(), nullable=True),
        sa.Column("machine_pool_id", sa.Integer(), nullable=True),
        sa.Column("lot_position_id", sa.Integer(), nullable=False),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "quantity_completed <= quantity",
            name="ck_production_order_quantity_completed_le_quantity",
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_id"], ["user_table.id"], name="fk_production_order_table_changed_by_id"
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"], ["user_table.id"], name="fk_production_order_creator_id"
        ),
        sa.ForeignKeyConstraint(
            ["lot_position_id"],
            ["lot_position_table.id"],
            name="fk_production_order_lot_position_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["machine_id"], ["production_machine_table.id"], name="fk_production_order_machine_id"
        ),
        sa.ForeignKeyConstraint(
            ["machine_pool_id"],
            ["machine_pool_table.id"],
            name="fk_production_order_machine_pool_id",
        ),
        sa.ForeignKeyConstraint(
            ["planned_by_id"], ["user_table.id"], name="fk_production_order_planned_by_id"
        ),
        sa.ForeignKeyConstraint(
            ["started_operator_id"],
            ["user_table.id"],
            name="fk_production_order_started_operator_id",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_production_order_table_changed_by_id"),
        "production_order_table",
        ["changed_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_order_table_creator_id"),
        "production_order_table",
        ["creator_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_order_table_lot_position_id"),
        "production_order_table",
        ["lot_position_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_order_table_machine_id"),
        "production_order_table",
        ["machine_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_order_table_machine_pool_id"),
        "production_order_table",
        ["machine_pool_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_order_table_planned_by_id"),
        "production_order_table",
        ["planned_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_order_table_production_order_number"),
        "production_order_table",
        ["production_order_number"],
        unique=True,
    )
    op.create_index(
        op.f("ix_production_order_table_public_id"),
        "production_order_table",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_production_order_table_started_operator_id"),
        "production_order_table",
        ["started_operator_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_order_table_status"), "production_order_table", ["status"], unique=False
    )
    op.create_index(
        "uq_production_order_queue_sequence_machine",
        "production_order_table",
        ["machine_id", "queue_sequence"],
        unique=True,
        postgresql_where=sa.text(
            "machine_id IS NOT NULL AND status <> 'completed' AND status <> 'canceled'"
        ),
        sqlite_where=sa.text(
            "machine_id IS NOT NULL AND status <> 'completed' AND status <> 'canceled'"
        ),
    )
    op.create_index(
        "uq_production_order_queue_sequence_pool",
        "production_order_table",
        ["machine_pool_id", "queue_sequence"],
        unique=True,
        postgresql_where=sa.text(
            "machine_id IS NULL AND machine_pool_id IS NOT NULL AND status <> 'completed' "
            "AND status <> 'canceled'"
        ),
        sqlite_where=sa.text(
            "machine_id IS NULL AND machine_pool_id IS NOT NULL AND status <> 'completed' "
            "AND status <> 'canceled'"
        ),
    )
    op.create_index(
        "uq_production_order_queue_sequence_unassigned",
        "production_order_table",
        ["queue_sequence"],
        unique=True,
        postgresql_where=sa.text(
            "machine_id IS NULL AND machine_pool_id IS NULL AND status <> 'completed' AND "
            "status <> 'canceled'"
        ),
        sqlite_where=sa.text(
            "machine_id IS NULL AND machine_pool_id IS NULL AND status <> 'completed' AND "
            "status <> 'canceled'"
        ),
    )
    op.create_table(
        "quote_request_line_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("quote_request_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("line_type", sa.String(), nullable=False),
        sa.Column(
            "quantity",
            sa.Numeric(precision=18, scale=6, asdecimal=False),
            nullable=False,
        ),
        sa.Column("unit", sa.String(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("virtual_name", sa.String(), nullable=True),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("bought_item_id", sa.Integer(), nullable=True),
        sa.Column("source_item_id", sa.Integer(), nullable=True),
        sa.Column("lot_position_id", sa.Integer(), nullable=True),
        sa.Column("awarded_supplier_id", sa.Integer(), nullable=True),
        sa.Column("awarded_price", sa.Integer(), nullable=True),
        sa.Column("awarded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("awarded_by_id", sa.Integer(), nullable=True),
        sa.Column("dropped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("substitute_reason", sa.String(), nullable=True),
        sa.Column("substituted_by_line_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            (
                "(line_type = 'BOUGHT' AND bought_item_id IS NOT NULL AND source_item_id IS NULL "
                "AND lot_position_id IS NULL AND virtual_name IS NULL) OR (line_type = 'SOURCE' "
                "AND source_item_id IS NOT NULL AND bought_item_id IS NULL AND lot_position_id "
                "IS NULL AND virtual_name IS NULL) OR (line_type = 'MADE' AND lot_position_id IS "
                "NOT NULL AND bought_item_id IS NULL AND source_item_id IS NULL AND virtual_name "
                "IS NULL) OR (line_type = 'VIRTUAL' AND virtual_name IS NOT NULL AND "
                "bought_item_id IS NULL AND source_item_id IS NULL AND lot_position_id IS NULL)"
            ),
            name="ck_quote_request_line_line_type",
        ),
        sa.ForeignKeyConstraint(
            ["awarded_by_id"], ["user_table.id"], name="fk_quote_request_line_awarded_by_id"
        ),
        sa.ForeignKeyConstraint(
            ["awarded_supplier_id"],
            ["quote_request_supplier_table.id"],
            name="fk_quote_request_line_awarded_supplier_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["bought_item_id"],
            ["bought_item_table.id"],
            name="fk_quote_request_line_bought_item_id",
        ),
        sa.ForeignKeyConstraint(
            ["lot_position_id"],
            ["lot_position_table.id"],
            name="fk_quote_request_line_lot_position_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project_table.id"], name="fk_quote_request_line_project_id"
        ),
        sa.ForeignKeyConstraint(
            ["quote_request_id"],
            ["quote_request_table.id"],
            name="fk_quote_request_line_request_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_item_id"],
            ["source_item_table.id"],
            name="fk_quote_request_line_source_item_id",
        ),
        sa.ForeignKeyConstraint(
            ["substituted_by_line_id"],
            ["quote_request_line_table.id"],
            name="fk_quote_request_line_substituted_by_line_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_quote_request_line_table_awarded_by_id"),
        "quote_request_line_table",
        ["awarded_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_quote_request_line_table_awarded_supplier_id"),
        "quote_request_line_table",
        ["awarded_supplier_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_quote_request_line_table_bought_item_id"),
        "quote_request_line_table",
        ["bought_item_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_quote_request_line_table_lot_position_id"),
        "quote_request_line_table",
        ["lot_position_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_quote_request_line_table_project_id"),
        "quote_request_line_table",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_quote_request_line_table_public_id"),
        "quote_request_line_table",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_quote_request_line_table_quote_request_id"),
        "quote_request_line_table",
        ["quote_request_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_quote_request_line_table_source_item_id"),
        "quote_request_line_table",
        ["source_item_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_quote_request_line_table_substituted_by_line_id"),
        "quote_request_line_table",
        ["substituted_by_line_id"],
        unique=False,
    )
    op.create_table(
        "lot_step_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("estimated_setup_minutes", sa.Integer(), nullable=True),
        sa.Column("estimated_minutes_per_piece", sa.Float(), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("time_budget_per_piece", sa.Float(), nullable=True),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("fabrication_method_id", sa.Integer(), nullable=True),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("inspection_method_id", sa.Integer(), nullable=True),
        sa.Column("lot_id", sa.Integer(), nullable=False),
        sa.Column("position_id", sa.Integer(), nullable=False),
        sa.Column("source_process_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            (
                "(role = 'fabrication' AND fabrication_method_id IS NOT NULL) OR (role = "
                "'inspection' AND fabrication_method_id IS NULL)"
            ),
            name="ck_lot_step_role_method",
        ),
        sa.CheckConstraint(
            (
                "(role = 'inspection' AND inspection_method_id IS NOT NULL) OR (role = "
                "'fabrication' AND inspection_method_id IS NULL)"
            ),
            name="ck_lot_step_inspection_method",
        ),
        sa.ForeignKeyConstraint(["creator_id"], ["user_table.id"], name="fk_lot_step_creator_id"),
        sa.ForeignKeyConstraint(
            ["fabrication_method_id"],
            ["fabrication_method_table.id"],
            name="fk_lot_step_fabrication_method_id",
        ),
        sa.ForeignKeyConstraint(
            ["inspection_method_id"],
            ["inspection_method_table.id"],
            name="fk_lot_step_inspection_method_id",
        ),
        sa.ForeignKeyConstraint(
            ["lot_id"], ["production_lot_table.id"], name="fk_lot_step_lot_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["position_id"],
            ["lot_position_table.id"],
            name="fk_lot_step_position_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_process_id"],
            ["made_item_process_table.id"],
            name="fk_lot_step_source_process_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("lot_id", "sequence", name="uq_lot_step_lot_id_sequence"),
    )
    op.create_index(
        op.f("ix_lot_step_table_creator_id"), "lot_step_table", ["creator_id"], unique=False
    )
    op.create_index(
        op.f("ix_lot_step_table_fabrication_method_id"),
        "lot_step_table",
        ["fabrication_method_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_lot_step_table_inspection_method_id"),
        "lot_step_table",
        ["inspection_method_id"],
        unique=False,
    )
    op.create_index(op.f("ix_lot_step_table_lot_id"), "lot_step_table", ["lot_id"], unique=False)
    op.create_index(
        op.f("ix_lot_step_table_position_id"), "lot_step_table", ["position_id"], unique=False
    )
    op.create_index(
        op.f("ix_lot_step_table_public_id"), "lot_step_table", ["public_id"], unique=True
    )
    op.create_index(
        op.f("ix_lot_step_table_source_process_id"),
        "lot_step_table",
        ["source_process_id"],
        unique=False,
    )
    op.create_table(
        "meeting_card_mention_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("card_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("present", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["card_id"],
            ["meeting_card_table.id"],
            name="fk_meeting_card_mention_card_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user_table.id"], name="fk_meeting_card_mention_user_id"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("card_id", "user_id", name="uq_meeting_card_mention_card_user"),
    )
    op.create_index(
        op.f("ix_meeting_card_mention_table_card_id"),
        "meeting_card_mention_table",
        ["card_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_meeting_card_mention_table_public_id"),
        "meeting_card_mention_table",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_meeting_card_mention_table_user_id"),
        "meeting_card_mention_table",
        ["user_id"],
        unique=False,
    )
    op.create_table(
        "meeting_card_revision_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("card_id", sa.Integer(), nullable=False),
        sa.Column("scope", sa.String(), nullable=True),
        sa.Column("scope_icon", sa.String(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("internal", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("saved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["author_id"], ["user_table.id"], name="fk_meeting_card_revision_author_id"
        ),
        sa.ForeignKeyConstraint(
            ["card_id"],
            ["meeting_card_table.id"],
            name="fk_meeting_card_revision_card_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_meeting_card_revision_table_author_id"),
        "meeting_card_revision_table",
        ["author_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_meeting_card_revision_table_card_id"),
        "meeting_card_revision_table",
        ["card_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_meeting_card_revision_table_public_id"),
        "meeting_card_revision_table",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "meeting_decision_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("meeting_id", sa.Integer(), nullable=False),
        sa.Column("card_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["card_id"],
            ["meeting_card_table.id"],
            name="fk_meeting_decision_card_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"], ["user_table.id"], name="fk_meeting_decision_creator_id"
        ),
        sa.ForeignKeyConstraint(
            ["meeting_id"],
            ["meeting_table.id"],
            name="fk_meeting_decision_meeting_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_meeting_decision_table_card_id"),
        "meeting_decision_table",
        ["card_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_meeting_decision_table_creator_id"),
        "meeting_decision_table",
        ["creator_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_meeting_decision_table_meeting_id"),
        "meeting_decision_table",
        ["meeting_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_meeting_decision_table_public_id"),
        "meeting_decision_table",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "meeting_file_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("meeting_id", sa.Integer(), nullable=False),
        sa.Column("card_id", sa.Integer(), nullable=True),
        sa.Column("file_name", sa.String(), nullable=False),
        sa.Column("stored_name", sa.String(), nullable=False),
        sa.Column("mime_type", sa.String(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(), nullable=False),
        sa.Column("sha256", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["card_id"],
            ["meeting_card_table.id"],
            name="fk_meeting_file_card_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["meeting_id"],
            ["meeting_table.id"],
            name="fk_meeting_file_meeting_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_user_id"], ["user_table.id"], name="fk_meeting_file_uploader_id"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stored_name", name="uq_meeting_file_stored_name"),
    )
    op.create_index(
        op.f("ix_meeting_file_table_card_id"), "meeting_file_table", ["card_id"], unique=False
    )
    op.create_index(
        op.f("ix_meeting_file_table_meeting_id"), "meeting_file_table", ["meeting_id"], unique=False
    )
    op.create_index(
        op.f("ix_meeting_file_table_public_id"), "meeting_file_table", ["public_id"], unique=True
    )
    op.create_index(
        op.f("ix_meeting_file_table_uploaded_by_user_id"),
        "meeting_file_table",
        ["uploaded_by_user_id"],
        unique=False,
    )
    op.create_table(
        "meeting_snapshot_contact_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("contact_id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["meeting_snapshot_table.id"],
            name="fk_meeting_snapshot_contact_snapshot_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "snapshot_id", "contact_id", name="uq_meeting_snapshot_contact_snapshot_contact"
        ),
    )
    op.create_index(
        op.f("ix_meeting_snapshot_contact_table_contact_id"),
        "meeting_snapshot_contact_table",
        ["contact_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_meeting_snapshot_contact_table_public_id"),
        "meeting_snapshot_contact_table",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_meeting_snapshot_contact_table_snapshot_id"),
        "meeting_snapshot_contact_table",
        ["snapshot_id"],
        unique=False,
    )
    op.create_table(
        "meeting_todo_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("meeting_id", sa.Integer(), nullable=False),
        sa.Column("card_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("done_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("done_by_id", sa.Integer(), nullable=True),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("changed", sa.DateTime(timezone=True), nullable=True),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["card_id"],
            ["meeting_card_table.id"],
            name="fk_meeting_todo_card_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_id"], ["user_table.id"], name="fk_meeting_todo_table_changed_by_id"
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"], ["user_table.id"], name="fk_meeting_todo_creator_id"
        ),
        sa.ForeignKeyConstraint(
            ["done_by_id"], ["user_table.id"], name="fk_meeting_todo_done_by_id"
        ),
        sa.ForeignKeyConstraint(
            ["meeting_id"],
            ["meeting_table.id"],
            name="fk_meeting_todo_meeting_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_meeting_todo_table_card_id"), "meeting_todo_table", ["card_id"], unique=False
    )
    op.create_index(
        op.f("ix_meeting_todo_table_changed_by_id"),
        "meeting_todo_table",
        ["changed_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_meeting_todo_table_creator_id"), "meeting_todo_table", ["creator_id"], unique=False
    )
    op.create_index(
        op.f("ix_meeting_todo_table_done_by_id"), "meeting_todo_table", ["done_by_id"], unique=False
    )
    op.create_index(
        op.f("ix_meeting_todo_table_meeting_id"), "meeting_todo_table", ["meeting_id"], unique=False
    )
    op.create_index(
        op.f("ix_meeting_todo_table_public_id"), "meeting_todo_table", ["public_id"], unique=True
    )
    op.create_table(
        "manufacturing_assessment_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("production_order_id", sa.Integer(), nullable=False),
        sa.Column("operator_id", sa.Integer(), nullable=False),
        sa.Column("actual_minutes_per_piece", sa.Integer(), nullable=False),
        sa.Column("actual_setup_minutes", sa.Integer(), nullable=True),
        sa.Column("complexity", sa.String(), nullable=False),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["operator_id"], ["user_table.id"], name="fk_manufacturing_assessment_operator_id"
        ),
        sa.ForeignKeyConstraint(
            ["production_order_id"],
            ["production_order_table.id"],
            name="fk_manufacturing_assessment_production_order_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_manufacturing_assessment_table_operator_id"),
        "manufacturing_assessment_table",
        ["operator_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_manufacturing_assessment_table_production_order_id"),
        "manufacturing_assessment_table",
        ["production_order_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_manufacturing_assessment_table_public_id"),
        "manufacturing_assessment_table",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "production_order_completion_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("production_order_id", sa.Integer(), nullable=False),
        sa.Column(
            "quantity",
            sa.Numeric(precision=18, scale=6, asdecimal=False),
            nullable=False,
        ),
        sa.Column(
            "quantity_accepted",
            sa.Numeric(precision=18, scale=6, asdecimal=False),
            nullable=False,
        ),
        sa.Column(
            "quantity_rejected",
            sa.Numeric(precision=18, scale=6, asdecimal=False),
            nullable=False,
        ),
        sa.Column(
            "quantity_rework",
            sa.Numeric(precision=18, scale=6, asdecimal=False),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "quantity_scrap",
            sa.Numeric(precision=18, scale=6, asdecimal=False),
            server_default="0",
            nullable=False,
        ),
        sa.Column("scrap_reason", sa.String(), nullable=True),
        sa.Column("reject_reason", sa.String(), nullable=True),
        sa.Column("completion_date", sa.Date(), nullable=False),
        sa.Column("reverses_completion_id", sa.Integer(), nullable=True),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("machine_id", sa.Integer(), nullable=True),
        sa.Column("operator_id", sa.Integer(), nullable=False),
        sa.Column("recorded_by_id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "ABS((quantity_accepted + quantity_rejected) - quantity) < 0.000001",
            name="ck_production_order_completion_split",
        ),
        sa.CheckConstraint(
            "quantity_accepted >= 0 OR reverses_completion_id IS NOT NULL",
            name="ck_production_order_completion_accepted_nonneg",
        ),
        sa.CheckConstraint(
            "quantity_rejected >= 0", name="ck_production_order_completion_rejected_nonneg"
        ),
        sa.ForeignKeyConstraint(
            ["machine_id"],
            ["production_machine_table.id"],
            name="fk_production_order_completion_machine_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["operator_id"], ["user_table.id"], name="fk_production_order_completion_operator_id"
        ),
        sa.ForeignKeyConstraint(
            ["production_order_id"],
            ["production_order_table.id"],
            name="fk_production_order_completion_production_order_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["recorded_by_id"],
            ["user_table.id"],
            name="fk_production_order_completion_recorded_by_id",
        ),
        sa.ForeignKeyConstraint(
            ["reverses_completion_id"],
            ["production_order_completion_table.id"],
            name="fk_production_order_completion_reverses_completion_id",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_production_order_completion_table_machine_id"),
        "production_order_completion_table",
        ["machine_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_order_completion_table_operator_id"),
        "production_order_completion_table",
        ["operator_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_order_completion_table_production_order_id"),
        "production_order_completion_table",
        ["production_order_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_order_completion_table_public_id"),
        "production_order_completion_table",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_production_order_completion_table_recorded_by_id"),
        "production_order_completion_table",
        ["recorded_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_order_completion_table_reverses_completion_id"),
        "production_order_completion_table",
        ["reverses_completion_id"],
        unique=True,
    )
    op.create_table(
        "production_order_file_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("production_order_id", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(), nullable=False),
        sa.Column("stored_name", sa.String(), nullable=False),
        sa.Column("mime_type", sa.String(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(), nullable=False),
        sa.Column("sha256", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["production_order_id"],
            ["production_order_table.id"],
            name="fk_production_order_file_production_order_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_user_id"], ["user_table.id"], name="fk_production_order_file_uploader_id"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stored_name"),
    )
    op.create_index(
        op.f("ix_production_order_file_table_production_order_id"),
        "production_order_file_table",
        ["production_order_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_order_file_table_public_id"),
        "production_order_file_table",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_production_order_file_table_uploaded_by_user_id"),
        "production_order_file_table",
        ["uploaded_by_user_id"],
        unique=False,
    )
    op.create_table(
        "production_order_interruption_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("production_order_id", sa.Integer(), nullable=False),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paused_by_id", sa.Integer(), nullable=False),
        sa.Column("resumed_by_id", sa.Integer(), nullable=True),
        sa.Column("paused_operator_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(), server_default="manual", nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["paused_by_id"],
            ["user_table.id"],
            name="fk_production_order_interruption_paused_by_id",
        ),
        sa.ForeignKeyConstraint(
            ["paused_operator_id"],
            ["user_table.id"],
            name="fk_production_order_interruption_paused_operator_id",
        ),
        sa.ForeignKeyConstraint(
            ["production_order_id"],
            ["production_order_table.id"],
            name="fk_production_order_interruption_production_order_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["resumed_by_id"],
            ["user_table.id"],
            name="fk_production_order_interruption_resumed_by_id",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_production_order_interruption_production_order_id",
        "production_order_interruption_table",
        ["production_order_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_order_interruption_table_paused_by_id"),
        "production_order_interruption_table",
        ["paused_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_order_interruption_table_paused_operator_id"),
        "production_order_interruption_table",
        ["paused_operator_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_order_interruption_table_public_id"),
        "production_order_interruption_table",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_production_order_interruption_table_resumed_by_id"),
        "production_order_interruption_table",
        ["resumed_by_id"],
        unique=False,
    )
    op.create_index(
        "uq_production_order_interruption_open",
        "production_order_interruption_table",
        ["production_order_id"],
        unique=True,
        postgresql_where=sa.text("resumed_at IS NULL"),
        sqlite_where=sa.text("resumed_at IS NULL"),
    )
    op.create_table(
        "order_item_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "changes",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column(
            "quantity",
            sa.Numeric(precision=18, scale=6, asdecimal=False),
            nullable=False,
        ),
        sa.Column(
            "quantity_delivered",
            sa.Numeric(precision=18, scale=6, asdecimal=False),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "quantity_rejected",
            sa.Numeric(precision=18, scale=6, asdecimal=False),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "quantity_rejected_lost",
            sa.Numeric(precision=18, scale=6, asdecimal=False),
            server_default="0",
            nullable=False,
        ),
        sa.Column("unit", sa.String(), nullable=False),
        sa.Column(
            "items_per_unit",
            sa.Numeric(precision=18, scale=6, asdecimal=False),
            nullable=False,
        ),
        sa.Column("price", sa.Integer(), nullable=True),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("ordered_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expected_delivery_date", sa.Date(), nullable=True),
        sa.Column("delivery_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("storage_place", sa.String(), nullable=True),
        sa.Column("expected_pickup_date", sa.Date(), nullable=True),
        sa.Column("ready_for_pickup_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_short_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "closed_short_from",
            sa.Numeric(precision=18, scale=6, asdecimal=False),
            nullable=True,
        ),
        sa.Column("edit_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("orderer_id", sa.Integer(), nullable=True),
        sa.Column("receiver_id", sa.Integer(), nullable=True),
        sa.Column("position", sa.Integer(), server_default="1", nullable=False),
        sa.Column("virtual_name", sa.String(), nullable=True),
        sa.Column("bought_item_id", sa.Integer(), nullable=True),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("supplier_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("line_type", sa.String(), server_default="BOUGHT", nullable=False),
        sa.Column("lot_position_id", sa.Integer(), nullable=True),
        sa.Column("source_item_id", sa.Integer(), nullable=True),
        sa.Column("quote_request_line_id", sa.Integer(), nullable=True),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            (
                "(line_type = 'BOUGHT' AND bought_item_id IS NOT NULL AND source_item_id IS NULL "
                "AND lot_position_id IS NULL AND virtual_name IS NULL) OR (line_type = 'SOURCE' "
                "AND source_item_id IS NOT NULL AND bought_item_id IS NULL AND lot_position_id "
                "IS NULL AND virtual_name IS NULL) OR (line_type = 'MADE' AND lot_position_id IS "
                "NOT NULL AND bought_item_id IS NULL AND source_item_id IS NULL AND virtual_name "
                "IS NULL) OR (line_type = 'VIRTUAL' AND virtual_name IS NOT NULL AND "
                "bought_item_id IS NULL AND source_item_id IS NULL AND lot_position_id IS NULL)"
            ),
            name="ck_order_item_line_type",
        ),
        sa.ForeignKeyConstraint(
            ["bought_item_id"], ["bought_item_table.id"], name="fk_order_item_bought_item_id"
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_id"], ["user_table.id"], name="fk_order_item_table_changed_by_id"
        ),
        sa.ForeignKeyConstraint(["creator_id"], ["user_table.id"], name="fk_order_item_creator_id"),
        sa.ForeignKeyConstraint(
            ["lot_position_id"], ["lot_position_table.id"], name="fk_order_item_lot_position_id"
        ),
        sa.ForeignKeyConstraint(["order_id"], ["order_table.id"], name="fk_order_item_order_id"),
        sa.ForeignKeyConstraint(["orderer_id"], ["user_table.id"], name="fk_order_item_orderer_id"),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project_table.id"], name="fk_order_item_project_id"
        ),
        sa.ForeignKeyConstraint(
            ["quote_request_line_id"],
            ["quote_request_line_table.id"],
            name="fk_order_item_quote_request_line_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["receiver_id"], ["user_table.id"], name="fk_order_item_receiver_id"
        ),
        sa.ForeignKeyConstraint(
            ["source_item_id"], ["source_item_table.id"], name="fk_order_item_source_item_id"
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"], ["supplier_table.id"], name="fk_order_item_supplier_id"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_order_item_table_bought_item_id"),
        "order_item_table",
        ["bought_item_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_order_item_table_changed_by_id"),
        "order_item_table",
        ["changed_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_order_item_table_creator_id"), "order_item_table", ["creator_id"], unique=False
    )
    op.create_index(
        op.f("ix_order_item_table_lot_position_id"),
        "order_item_table",
        ["lot_position_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_order_item_table_order_id"), "order_item_table", ["order_id"], unique=False
    )
    op.create_index(
        op.f("ix_order_item_table_orderer_id"), "order_item_table", ["orderer_id"], unique=False
    )
    op.create_index(
        op.f("ix_order_item_table_project_id"), "order_item_table", ["project_id"], unique=False
    )
    op.create_index(
        op.f("ix_order_item_table_public_id"), "order_item_table", ["public_id"], unique=True
    )
    op.create_index(
        op.f("ix_order_item_table_quote_request_line_id"),
        "order_item_table",
        ["quote_request_line_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_order_item_table_receiver_id"), "order_item_table", ["receiver_id"], unique=False
    )
    op.create_index(
        op.f("ix_order_item_table_source_item_id"),
        "order_item_table",
        ["source_item_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_order_item_table_supplier_id"), "order_item_table", ["supplier_id"], unique=False
    )
    op.create_index(
        "uq_order_item_open_lot_position_id",
        "order_item_table",
        ["lot_position_id"],
        unique=True,
        postgresql_where=sa.text("canceled_at IS NULL AND closed_short_at IS NULL"),
        sqlite_where=sa.text("canceled_at IS NULL AND closed_short_at IS NULL"),
    )
    op.create_table(
        "quote_extra_cost_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("supplier_row_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=True),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("line_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["line_id"],
            ["quote_request_line_table.id"],
            name="fk_quote_extra_cost_line_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["supplier_row_id"],
            ["quote_request_supplier_table.id"],
            name="fk_quote_extra_cost_supplier_row_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_quote_extra_cost_table_line_id"),
        "quote_extra_cost_table",
        ["line_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_quote_extra_cost_table_public_id"),
        "quote_extra_cost_table",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_quote_extra_cost_table_supplier_row_id"),
        "quote_extra_cost_table",
        ["supplier_row_id"],
        unique=False,
    )
    op.create_table(
        "quote_request_line_demand_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("line_id", sa.Integer(), nullable=False),
        sa.Column("bought_demand_item_id", sa.Integer(), nullable=True),
        sa.Column("source_demand_item_id", sa.Integer(), nullable=True),
        sa.Column(
            "quantity",
            sa.Numeric(precision=18, scale=6, asdecimal=False),
            nullable=False,
        ),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            (
                "(bought_demand_item_id IS NOT NULL AND source_demand_item_id IS NULL) OR "
                "(source_demand_item_id IS NOT NULL AND bought_demand_item_id IS NULL)"
            ),
            name="ck_quote_request_line_demand_one_family",
        ),
        sa.ForeignKeyConstraint(
            ["bought_demand_item_id"],
            ["bought_item_demand_item_table.id"],
            name="fk_quote_request_line_demand_bought_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["line_id"],
            ["quote_request_line_table.id"],
            name="fk_quote_request_line_demand_line_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_demand_item_id"],
            ["source_item_demand_item_table.id"],
            name="fk_quote_request_line_demand_source_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "line_id", "bought_demand_item_id", name="uq_quote_request_line_demand_bought"
        ),
        sa.UniqueConstraint(
            "line_id", "source_demand_item_id", name="uq_quote_request_line_demand_source"
        ),
    )
    op.create_index(
        op.f("ix_quote_request_line_demand_table_bought_demand_item_id"),
        "quote_request_line_demand_table",
        ["bought_demand_item_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_quote_request_line_demand_table_line_id"),
        "quote_request_line_demand_table",
        ["line_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_quote_request_line_demand_table_public_id"),
        "quote_request_line_demand_table",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_quote_request_line_demand_table_source_demand_item_id"),
        "quote_request_line_demand_table",
        ["source_demand_item_id"],
        unique=False,
    )
    op.create_table(
        "quote_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("supplier_row_id", sa.Integer(), nullable=False),
        sa.Column("line_id", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Integer(), nullable=True),
        sa.Column("no_offer", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("lead_time_days", sa.Integer(), nullable=True),
        sa.Column(
            "min_quantity",
            sa.Numeric(precision=18, scale=6, asdecimal=False),
            nullable=True,
        ),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("substitute_bought_item_id", sa.Integer(), nullable=True),
        sa.Column("substitute_source_item_id", sa.Integer(), nullable=True),
        sa.Column("substitute_reason", sa.String(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["line_id"],
            ["quote_request_line_table.id"],
            name="fk_quote_line_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["substitute_bought_item_id"],
            ["bought_item_table.id"],
            name="fk_quote_substitute_bought_item_id",
        ),
        sa.ForeignKeyConstraint(
            ["substitute_source_item_id"],
            ["source_item_table.id"],
            name="fk_quote_substitute_source_item_id",
        ),
        sa.ForeignKeyConstraint(
            ["supplier_row_id"],
            ["quote_request_supplier_table.id"],
            name="fk_quote_supplier_row_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("supplier_row_id", "line_id", name="uq_quote_supplier_row_line"),
    )
    op.create_index(op.f("ix_quote_table_line_id"), "quote_table", ["line_id"], unique=False)
    op.create_index(op.f("ix_quote_table_public_id"), "quote_table", ["public_id"], unique=True)
    op.create_index(
        op.f("ix_quote_table_substitute_bought_item_id"),
        "quote_table",
        ["substitute_bought_item_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_quote_table_substitute_source_item_id"),
        "quote_table",
        ["substitute_source_item_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_quote_table_supplier_row_id"), "quote_table", ["supplier_row_id"], unique=False
    )
    op.create_table(
        "meeting_todo_owner_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("todo_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("contact_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "(user_id IS NULL) <> (contact_id IS NULL)",
            name="ck_meeting_todo_owner_table_one_owner",
        ),
        sa.ForeignKeyConstraint(
            ["contact_id"], ["contact_table.id"], name="fk_meeting_todo_owner_contact_id"
        ),
        sa.ForeignKeyConstraint(
            ["todo_id"],
            ["meeting_todo_table.id"],
            name="fk_meeting_todo_owner_todo_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user_table.id"], name="fk_meeting_todo_owner_user_id"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("todo_id", "contact_id", name="uq_meeting_todo_owner_contact"),
        sa.UniqueConstraint("todo_id", "user_id", name="uq_meeting_todo_owner_user"),
    )
    op.create_index(
        op.f("ix_meeting_todo_owner_table_contact_id"),
        "meeting_todo_owner_table",
        ["contact_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_meeting_todo_owner_table_public_id"),
        "meeting_todo_owner_table",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_meeting_todo_owner_table_todo_id"),
        "meeting_todo_owner_table",
        ["todo_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_meeting_todo_owner_table_user_id"),
        "meeting_todo_owner_table",
        ["user_id"],
        unique=False,
    )
    op.create_table(
        "bought_item_allocation_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("demand_item_id", sa.Integer(), nullable=False),
        sa.Column("order_item_id", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(), server_default="order", nullable=False),
        sa.Column(
            "quantity",
            sa.Numeric(precision=18, scale=6, asdecimal=False),
            nullable=False,
        ),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("substitute_item_id", sa.Integer(), nullable=True),
        sa.Column("substitute_reason", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["user_table.id"], name="fk_bought_item_allocation_created_by_id"
        ),
        sa.ForeignKeyConstraint(
            ["demand_item_id"],
            ["bought_item_demand_item_table.id"],
            name="fk_allocation_demand_item_id",
        ),
        sa.ForeignKeyConstraint(
            ["order_item_id"], ["order_item_table.id"], name="fk_allocation_order_item_id"
        ),
        sa.ForeignKeyConstraint(
            ["substitute_item_id"],
            ["bought_item_table.id"],
            name="fk_allocation_substitute_item_id",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "demand_item_id", "order_item_id", name="uq_allocation_demand_order_item"
        ),
    )
    op.create_index(
        op.f("ix_bought_item_allocation_table_created_by_id"),
        "bought_item_allocation_table",
        ["created_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_bought_item_allocation_table_order_item_id"),
        "bought_item_allocation_table",
        ["order_item_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_bought_item_allocation_table_public_id"),
        "bought_item_allocation_table",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_bought_item_allocation_table_substitute_item_id"),
        "bought_item_allocation_table",
        ["substitute_item_id"],
        unique=False,
    )
    op.create_index(
        "uq_allocation_demand_stock",
        "bought_item_allocation_table",
        ["demand_item_id"],
        unique=True,
        postgresql_where=sa.text("source = 'stock'"),
        sqlite_where=sa.text("source = 'stock'"),
    )
    op.create_table(
        "order_extra_cost_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=True),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("order_item_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["order_table.id"],
            name="fk_order_extra_cost_order_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["order_item_id"],
            ["order_item_table.id"],
            name="fk_order_extra_cost_order_item_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_order_extra_cost_table_order_id"),
        "order_extra_cost_table",
        ["order_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_order_extra_cost_table_order_item_id"),
        "order_extra_cost_table",
        ["order_item_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_order_extra_cost_table_public_id"),
        "order_extra_cost_table",
        ["public_id"],
        unique=True,
    )
    op.create_table(
        "order_item_delivery_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("order_item_id", sa.Integer(), nullable=False),
        sa.Column(
            "quantity",
            sa.Numeric(precision=18, scale=6, asdecimal=False),
            nullable=False,
        ),
        sa.Column("delivery_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("storage_place", sa.String(), nullable=True),
        sa.Column(
            "quantity_rejected",
            sa.Numeric(precision=18, scale=6, asdecimal=False),
            server_default="0",
            nullable=False,
        ),
        sa.Column("rejection_reason", sa.String(), nullable=True),
        sa.Column("rejection_note", sa.Text(), nullable=True),
        sa.Column("rejection_outcome", sa.String(), nullable=True),
        sa.Column("corrects_delivery_id", sa.Integer(), nullable=True),
        sa.Column("correction_reason", sa.Text(), nullable=True),
        sa.Column("supplier_batch", sa.String(), nullable=True),
        sa.Column("delivery_note_number", sa.String(), nullable=True),
        sa.Column("certificate_reference", sa.String(), nullable=True),
        sa.Column(
            "damage_noted_on_delivery_note",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("receiver_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["corrects_delivery_id"],
            ["order_item_delivery_table.id"],
            name="fk_order_item_delivery_corrects_delivery_id",
        ),
        sa.ForeignKeyConstraint(
            ["order_item_id"], ["order_item_table.id"], name="fk_order_item_delivery_order_item_id"
        ),
        sa.ForeignKeyConstraint(
            ["receiver_id"], ["user_table.id"], name="fk_order_item_delivery_receiver_id"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_order_item_delivery_table_corrects_delivery_id"),
        "order_item_delivery_table",
        ["corrects_delivery_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_order_item_delivery_table_order_item_id"),
        "order_item_delivery_table",
        ["order_item_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_order_item_delivery_table_public_id"),
        "order_item_delivery_table",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_order_item_delivery_table_receiver_id"),
        "order_item_delivery_table",
        ["receiver_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_order_item_delivery_table_supplier_batch"),
        "order_item_delivery_table",
        ["supplier_batch"],
        unique=False,
    )
    op.create_table(
        "source_item_allocation_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("demand_item_id", sa.Integer(), nullable=False),
        sa.Column("order_item_id", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column(
            "quantity",
            sa.Numeric(precision=18, scale=6, asdecimal=False),
            nullable=False,
        ),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("substitute_source_item_id", sa.Integer(), nullable=True),
        sa.Column("substitute_reason", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["user_table.id"], name="fk_source_item_allocation_created_by_id"
        ),
        sa.ForeignKeyConstraint(
            ["demand_item_id"],
            ["source_item_demand_item_table.id"],
            name="fk_source_item_allocation_demand_item_id",
        ),
        sa.ForeignKeyConstraint(
            ["order_item_id"],
            ["order_item_table.id"],
            name="fk_source_item_allocation_order_item_id",
        ),
        sa.ForeignKeyConstraint(
            ["substitute_source_item_id"],
            ["source_item_table.id"],
            name="fk_source_item_allocation_substitute_source_item_id",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "demand_item_id", "order_item_id", name="uq_source_item_allocation_demand_order_item"
        ),
    )
    op.create_index(
        op.f("ix_source_item_allocation_table_created_by_id"),
        "source_item_allocation_table",
        ["created_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_item_allocation_table_demand_item_id"),
        "source_item_allocation_table",
        ["demand_item_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_item_allocation_table_order_item_id"),
        "source_item_allocation_table",
        ["order_item_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_item_allocation_table_public_id"),
        "source_item_allocation_table",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_source_item_allocation_table_substitute_source_item_id"),
        "source_item_allocation_table",
        ["substitute_source_item_id"],
        unique=False,
    )
    op.create_index(
        "uq_source_item_allocation_demand_stock",
        "source_item_allocation_table",
        ["demand_item_id"],
        unique=True,
        postgresql_where=sa.text("source = 'stock'"),
        sqlite_where=sa.text("source = 'stock'"),
    )
    op.create_table(
        "order_file_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(), nullable=False),
        sa.Column("stored_name", sa.String(), nullable=False),
        sa.Column("mime_type", sa.String(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(), nullable=False),
        sa.Column("sha256", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Integer(), nullable=False),
        sa.Column("delivery_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["delivery_id"], ["order_item_delivery_table.id"], name="fk_order_file_delivery_id"
        ),
        sa.ForeignKeyConstraint(["order_id"], ["order_table.id"], name="fk_order_file_order_id"),
        sa.ForeignKeyConstraint(
            ["uploaded_by_user_id"], ["user_table.id"], name="fk_order_file_uploader_id"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stored_name"),
    )
    op.create_index(
        op.f("ix_order_file_table_delivery_id"), "order_file_table", ["delivery_id"], unique=False
    )
    op.create_index(
        op.f("ix_order_file_table_order_id"), "order_file_table", ["order_id"], unique=False
    )
    op.create_index(
        op.f("ix_order_file_table_public_id"), "order_file_table", ["public_id"], unique=True
    )
    op.create_index(
        op.f("ix_order_file_table_uploaded_by_user_id"),
        "order_file_table",
        ["uploaded_by_user_id"],
        unique=False,
    )
    with op.batch_alter_table("production_lot_table") as batch_op:
        batch_op.create_foreign_key(
            "fk_production_lot_input_demand_id",
            "source_item_demand_item_table",
            ["input_demand_id"],
            ["id"],
        )
    if op.get_bind().dialect.name == "postgresql":
        _create_trigram_indexes()


def downgrade() -> None:
    """Dropping the whole schema is never a downgrade; restore a backup
    instead."""
    raise NotImplementedError("The initial migration cannot be rolled back.")
