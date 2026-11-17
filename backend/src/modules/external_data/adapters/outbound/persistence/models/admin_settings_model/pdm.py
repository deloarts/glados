"""ORM model for the admin_pdm_settings singleton table, plus the datacard
variable map, feature-tree template and required-field defaults its
columns use as Python and server defaults.
"""

import json
from datetime import datetime

from sqlalchemy import JSON
from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.modules.platform.adapters.outbound.persistence.encrypted_type import EncryptedString
from src.modules.platform.adapters.outbound.persistence.models.base import Base

# Variable-name defaults per docs/FIELD_OWNERSHIP.md; "" means unmapped.
# Every mappable field has a key, and the settings update keeps it that way.
_MADE_ITEM_VARIABLE_MAP_DEFAULT: dict[str, str] = {
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
    # Label fields and the feature-tree field.
    "article_group_names": "Glados.ArticleGroupNames",
    "process_names": "Glados.ProcessNames",
    "source_item_name": "Glados.SourceItemName",
    "customer_name": "Glados.CustomerName",
    "feature_tree_representation": "Glados.FeatureTreeRepresentation",
    "kind": "Glados.Kind",
    "glados_ids": "Glados.Ids",
    "newest_revision_sync_state": "Glados.NewestRevisionSyncState",
    "newest_revision_synced_at": "Glados.NewestRevisionSyncedAt",
}


_BOUGHT_ITEM_VARIABLE_MAP_DEFAULT: dict[str, str] = {
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
    # Label fields and the feature-tree field.
    "manufacturer_name": "Glados.ManufacturerName",
    "article_group_names": "Glados.ArticleGroupNames",
    "feature_tree_representation": "Glados.FeatureTreeRepresentation",
    "kind": "Glados.Kind",
    "glados_ids": "Glados.Ids",
    "newest_revision_sync_state": "Glados.NewestRevisionSyncState",
    "newest_revision_synced_at": "Glados.NewestRevisionSyncedAt",
}


# Also the entity's dataclass defaults.
_MADE_FEATURE_TREE_TEMPLATE_DEFAULT = (
    '$PRP:"PDM.PartNumber" Rev$PRP:"PDM.Revision" ($PRP:"Glados.ArticleName")'
)


_BOUGHT_FEATURE_TREE_TEMPLATE_DEFAULT = (
    '$PRP:"Glados.ArticleName" - $PRP:"Glados.OrderCode1" - $PRP:"Glados.ManufacturerName"'
)


_MADE_ITEM_VARIABLE_MAP_SERVER_DEFAULT = json.dumps(_MADE_ITEM_VARIABLE_MAP_DEFAULT)


_BOUGHT_ITEM_VARIABLE_MAP_SERVER_DEFAULT = json.dumps(_BOUGHT_ITEM_VARIABLE_MAP_DEFAULT)


# The default admin selection on top of the locked set; a bought item's
# revision is required by default although it is not part of its identity.
_REQUIRED_FIELDS_DEFAULT: dict[str, list[str]] = {
    "made": ["material", "fabrication_step"],
    "bought": ["revision"],
}


_REQUIRED_FIELDS_SERVER_DEFAULT = json.dumps(_REQUIRED_FIELDS_DEFAULT)


class AdminPdmSettingsOrmModel(Base):
    """The PDM settings singleton; see AdminPdmSettings."""

    __tablename__ = "admin_pdm_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    made_item_variable_map: Mapped[dict[str, str]] = mapped_column(
        JSON,
        nullable=False,
        default=lambda: dict(_MADE_ITEM_VARIABLE_MAP_DEFAULT),
        server_default=_MADE_ITEM_VARIABLE_MAP_SERVER_DEFAULT,
    )
    bought_item_variable_map: Mapped[dict[str, str]] = mapped_column(
        JSON,
        nullable=False,
        default=lambda: dict(_BOUGHT_ITEM_VARIABLE_MAP_DEFAULT),
        server_default=_BOUGHT_ITEM_VARIABLE_MAP_SERVER_DEFAULT,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    base_url: Mapped[str] = mapped_column(String, nullable=False, server_default="")
    vault_name: Mapped[str] = mapped_column(String, nullable=False, server_default="")
    username: Mapped[str] = mapped_column(String, nullable=False, server_default="")
    # Encrypted at rest, like AdminMailSettingsOrmModel.password (mail.py).
    password: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    verify_certificate: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, server_default="15")
    # Shared Web API token (see AdminPdmSettings); never returned by the API.
    session_token: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    session_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    session_obtained_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # A JSON list of watched folder objects.
    watched_folders: Mapped[list[dict[str, bool | str]]] = mapped_column(
        JSON, nullable=False, default=list, server_default="[]"
    )
    made_released_state_ids: Mapped[list[int]] = mapped_column(
        JSON, nullable=False, default=list, server_default="[]"
    )
    made_obsolete_state_ids: Mapped[list[int]] = mapped_column(
        JSON, nullable=False, default=list, server_default="[]"
    )
    bought_released_state_ids: Mapped[list[int]] = mapped_column(
        JSON, nullable=False, default=list, server_default="[]"
    )
    bought_obsolete_state_ids: Mapped[list[int]] = mapped_column(
        JSON, nullable=False, default=list, server_default="[]"
    )
    made_replaced_state_ids: Mapped[list[int]] = mapped_column(
        JSON, nullable=False, default=list, server_default="[]"
    )
    bought_replaced_state_ids: Mapped[list[int]] = mapped_column(
        JSON, nullable=False, default=list, server_default="[]"
    )
    document_released_state_ids: Mapped[list[int]] = mapped_column(
        JSON, nullable=False, default=list, server_default="[]"
    )
    poll_interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="15")
    cold_folder_max_multiplier: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="8"
    )
    ingest_concurrency: Mapped[int] = mapped_column(Integer, nullable=False, server_default="4")
    # Cached vault GUID, "" until first looked up.
    vault_id: Mapped[str] = mapped_column(String, nullable=False, server_default="")
    cad_items_read_only: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    # Language code of the add-in's catalogue labels, "" = tenant default.
    addin_language: Mapped[str] = mapped_column(String, nullable=False, server_default="")
    last_poll_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_poll_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_poll_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    writeback_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    made_item_extensions: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=lambda: ["sldprt"], server_default='["sldprt"]'
    )
    bought_item_extensions: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=lambda: ["sldprt", "sldasm"],
        server_default='["sldprt", "sldasm"]',
    )
    document_categories: Mapped[dict[str, str]] = mapped_column(
        JSON,
        nullable=False,
        default=lambda: {"pdf": "drawing", "dxf": "dxf", "step": "step", "stp": "step"},
        server_default='{"pdf": "drawing", "dxf": "dxf", "step": "step", "stp": "step"}',
    )
    # Extension to the item kinds that do not receive that document.
    document_excluded_kinds: Mapped[dict[str, list[str]]] = mapped_column(
        JSON, nullable=False, default=dict, server_default="{}"
    )
    thumbnails_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    stuck_after_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default="7")
    # NULL means no reconciliation is queued.
    reconcile_requested_deep: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    required_fields: Mapped[dict[str, list[str]]] = mapped_column(
        JSON,
        nullable=False,
        default=lambda: {k: list(v) for k, v in _REQUIRED_FIELDS_DEFAULT.items()},
        server_default=_REQUIRED_FIELDS_SERVER_DEFAULT,
    )
    set_approver_from_pdm: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    made_feature_tree_template: Mapped[str] = mapped_column(
        String, nullable=False, server_default=_MADE_FEATURE_TREE_TEMPLATE_DEFAULT
    )
    bought_feature_tree_template: Mapped[str] = mapped_column(
        String, nullable=False, server_default=_BOUGHT_FEATURE_TREE_TEMPLATE_DEFAULT
    )
