"""
HTTP request and response schemas for the PDM settings, the PDM connection
check and session state.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator
from pydantic import model_validator

from src.modules.external_data.domain.value_objects.pdm_document_category import (
    allowed_document_categories,
)
from src.modules.external_data.domain.value_objects.pdm_document_category import (
    normalize_document_excluded_kinds,
)
from src.modules.external_data.domain.value_objects.pdm_watched_folder import PdmWatchedFolder
from src.modules.external_data.domain.value_objects.pdm_watched_folder import normalize_path
from src.modules.external_data.domain.value_objects.pdm_watched_folder import (
    validate_watched_folder,
)
from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel
from src.modules.platform.domain.value_objects.language import Language


class PdmWatchedFolderRequest(BaseModel):
    path: str
    # "by_kind" defers to the file's own `kind` datacard variable rather
    # than the folder asserting one; see PdmWatchedFolder's docstring.
    kind: str = "by_kind"
    recursive: bool
    enabled: bool
    match_by: str | None = None
    filename_pattern: str | None = None
    # PDM folder id (see PdmWatchedFolder's docstring): the picker
    # (GET /admin/settings/pdm/folders) supplies one; a folder entered by
    # hand leaves it None.
    folder_id: int | None = None

    @field_validator("path")
    @classmethod
    def normalize(cls, v: str) -> str:
        return normalize_path(v)

    @field_validator("kind")
    @classmethod
    def validate_kind(cls, v: str) -> str:
        if v not in ("made", "bought", "by_kind", "documents"):
            raise ValueError('kind must be "made", "bought", "by_kind" or "documents".')
        return v

    @model_validator(mode="after")
    def validate_documents_shape(self) -> "PdmWatchedFolderRequest":
        validate_watched_folder(
            PdmWatchedFolder(
                path=self.path,
                kind=self.kind,
                recursive=self.recursive,
                enabled=self.enabled,
                match_by=self.match_by,
                filename_pattern=self.filename_pattern,
                folder_id=self.folder_id,
            )
        )
        return self


class UpdatePdmSettingsRequest(BaseModel):
    made_item_variable_map: dict[str, str] | None = None
    bought_item_variable_map: dict[str, str] | None = None
    enabled: bool | None = None
    base_url: str | None = None
    vault_name: str | None = None
    username: str | None = None
    # None means "keep existing password unchanged", mirrored on
    # UpdatePdmSettingsCommand per the package's docstring.
    password: str | None = None
    verify_certificate: bool | None = None
    timeout_seconds: int | None = Field(default=None, ge=1, le=300)
    watched_folders: list[PdmWatchedFolderRequest] | None = None
    # None = leave the stored list as-is, independently per kind; mirrors
    # UpdatePdmSettingsCommand per the package's docstring.
    made_released_state_ids: list[int] | None = None
    made_obsolete_state_ids: list[int] | None = None
    made_replaced_state_ids: list[int] | None = None
    bought_released_state_ids: list[int] | None = None
    bought_obsolete_state_ids: list[int] | None = None
    bought_replaced_state_ids: list[int] | None = None
    document_released_state_ids: list[int] | None = None
    poll_interval_minutes: int | None = Field(default=None, ge=1, le=1440)
    # Cold-folder poll cadence cap (see AdminPdmSettingsResponse.
    # cold_folder_max_multiplier's docstring). None = leave as-is, same
    # convention as every other optional field here.
    cold_folder_max_multiplier: int | None = Field(default=None, ge=1, le=64)
    # Changed files a poll run ingests at once. None = leave as-is.
    ingest_concurrency: int | None = Field(default=None, ge=1, le=16)
    cad_items_read_only: bool | None = None
    # None = leave as-is, "" = the tenant's default language.
    addin_language: Language | Literal[""] | None = None
    writeback_enabled: bool | None = None
    made_item_extensions: list[str] | None = None
    bought_item_extensions: list[str] | None = None
    document_categories: dict[str, str] | None = None
    document_excluded_kinds: dict[str, list[str]] | None = None
    thumbnails_enabled: bool | None = None
    stuck_after_days: int | None = Field(default=None, ge=1, le=365)
    # Required-field validation (see AdminPdmSettingsResponse.
    # required_fields' docstring). None = leave the stored selection
    # as-is, same convention as every other optional field here.
    required_fields: dict[str, list[str]] | None = None
    # PDM user matching (see AdminPdmSettingsResponse.
    # set_approver_from_pdm's docstring). None = leave as-is.
    set_approver_from_pdm: bool | None = None
    # Feature-tree templates (see AdminPdmSettingsResponse.
    # made_feature_tree_template/bought_feature_tree_template's docstring).
    # None = leave the stored value as-is; validated against the merged
    # settings server-side (AdminPdmSettings.
    # assert_feature_tree_templates_valid).
    made_feature_tree_template: str | None = None
    bought_feature_tree_template: str | None = None

    @field_validator("made_item_extensions", "bought_item_extensions")
    @classmethod
    def validate_extensions(cls, v: list[str] | None) -> list[str] | None:
        """Mirrors UpdatePdmSettingsCommand's own check per the package's
        docstring."""
        if v is None:
            return v
        if not v:
            raise ValueError("extensions list must not be empty.")
        normalised = [e.strip().lower().lstrip(".") for e in v]
        for ext in normalised:
            if not ext or not ext.isalnum():
                raise ValueError(f"invalid extension {ext!r}: must be lower-case alphanumeric.")
        return normalised

    @field_validator("document_categories")
    @classmethod
    def validate_document_categories(cls, v: dict[str, str] | None) -> dict[str, str] | None:
        """Mirrors UpdatePdmSettingsCommand's own check per the package's
        docstring."""
        if v is None:
            return v
        allowed = allowed_document_categories()
        normalised: dict[str, str] = {}
        for ext, category in v.items():
            key = ext.strip().lower().lstrip(".")
            if not key or not key.isalnum():
                raise ValueError(f"invalid extension {key!r}: must be lower-case alphanumeric.")
            if category not in allowed:
                raise ValueError(f"unknown item file category {category!r} for extension {key!r}.")
            normalised[key] = category
        return normalised

    @field_validator("document_excluded_kinds")
    @classmethod
    def validate_document_excluded_kinds(
        cls, v: dict[str, list[str]] | None
    ) -> dict[str, list[str]] | None:
        """Mirrors UpdatePdmSettingsCommand's own check per the package's
        docstring."""
        return None if v is None else normalize_document_excluded_kinds(v)

    @field_validator("base_url")
    @classmethod
    def validate_base_url_scheme(cls, v: str | None) -> str | None:
        """Requires an http(s) scheme and strips a trailing slash, mirrored
        on UpdatePdmSettingsCommand per the package's docstring. Raising
        ValueError here (inside a field_validator) becomes a 422 through
        Pydantic/FastAPI's own validation-error handling, unlike a bare
        `raise ValueError` inside a use case, which exception_handlers.py
        has no handler for and would fall through to an unhandled 500.
        Empty string is always allowed, it means "no connection configured".
        """
        if v is None:
            return v
        trimmed = v.strip()
        if not trimmed:
            return ""
        if not (trimmed.startswith("http://") or trimmed.startswith("https://")):
            raise ValueError("base_url must start with http:// or https://.")
        return trimmed.rstrip("/")

    @field_validator("watched_folders")
    @classmethod
    def validate_watched_folders_unique(
        cls, v: list[PdmWatchedFolderRequest] | None
    ) -> list[PdmWatchedFolderRequest] | None:
        """Mirrors UpdatePdmSettingsCommand's own check per the package's
        docstring: shape-only, the stored-state rules live in
        UpdatePdmSettings."""
        if v is None:
            return v
        paths = [f.path for f in v]
        if len(paths) != len(set(paths)):
            duplicates = sorted({p for p in paths if paths.count(p) > 1})
            raise ValueError(f"watched_folders paths must be unique, duplicate(s): {duplicates}.")
        return v


class VerifyPdmConnectionRequest(BaseModel):
    base_url: str
    vault_name: str
    username: str
    password: str | None = None
    verify_certificate: bool = True
    timeout_seconds: int = Field(default=15, ge=1, le=300)


class ItemFieldOwnershipResponse(ResponseModel):
    """One row of the fixed field ownership table, read-only."""

    field: str
    owner: Literal["addin", "pdm", "addin_web", "web", "server"]
    mappable: bool
    policy_applicable: bool
    # The field this one is a label of (item_field_ownership.
    # MADE_ITEM_LABEL_FIELDS/BOUGHT_ITEM_LABEL_FIELDS), None for every
    # other field.
    label_of: str | None


class ItemFieldsResponse(ResponseModel):
    made: list[ItemFieldOwnershipResponse]
    bought: list[ItemFieldOwnershipResponse]


class PdmSessionResponse(ResponseModel):
    active: bool
    obtained_at: datetime | None
    user_id: int | None


class PdmWatchedFolderResponse(ResponseModel):
    path: str
    kind: Literal["made", "bought", "by_kind", "documents"]
    recursive: bool
    enabled: bool
    match_by: str | None
    filename_pattern: str | None
    folder_id: int | None


class AdminPdmSettingsResponse(EntityResponse):
    made_item_variable_map: dict[str, str]
    bought_item_variable_map: dict[str, str]
    # See AdminPdmSettingsResult's docstring (admin_settings_dto/pdm.py): the
    # Item Fields admin tab reads the ownership table from here,
    # alongside the field mapping it edits on this same screen.
    item_fields: ItemFieldsResponse
    enabled: bool
    # PDM__ALLOW_MUTATING_OPERATIONS: whether the deployment lets the admin
    # API console run mutating operations at all. Read-only.
    mutating_operations_enabled: bool
    base_url: str
    vault_name: str
    username: str
    password_configured: bool
    verify_certificate: bool
    timeout_seconds: int
    configured: bool
    session: PdmSessionResponse
    watched_folders: list[PdmWatchedFolderResponse]
    made_released_state_ids: list[int]
    made_obsolete_state_ids: list[int]
    made_replaced_state_ids: list[int]
    bought_released_state_ids: list[int]
    bought_obsolete_state_ids: list[int]
    bought_replaced_state_ids: list[int]
    # Workflow states a `documents` folder's files are synced in; a file in
    # any other state is skipped.
    document_released_state_ids: list[int]
    poll_interval_minutes: int
    # Cold-folder poll cadence cap (domain.services.pdm_poll_cadence): a
    # watched folder unchanged across consecutive scheduled runs backs off
    # exponentially, capped at poll_interval_minutes times this multiplier.
    # 1 effectively disables backoff.
    cold_folder_max_multiplier: int
    # How many changed files a poll run ingests at once (1..16); 1 processes
    # them one after another.
    ingest_concurrency: int
    vault_id: str
    cad_items_read_only: bool
    # Language of the add-in's catalogue labels, "" = the tenant's default.
    addin_language: str
    last_poll_at: datetime | None
    last_poll_error: str | None
    last_poll_summary: str | None
    writeback_enabled: bool
    made_item_extensions: list[str]
    bought_item_extensions: list[str]
    document_categories: dict[str, str]
    # Extension to the item kinds that do not receive that document.
    document_excluded_kinds: dict[str, list[str]]
    thumbnails_enabled: bool
    stuck_after_days: int
    snapshot_counts: dict[str, int]
    # Required-field validation (docs/PDM_INTEGRATION.md's "required
    # fields" section). required_fields is the stored, configurable
    # selection this response's PUT accepts back; locked_required_fields
    # and required_field_rules are read-only, for the settings page's
    # checklist.
    required_fields: dict[str, list[str]]
    locked_required_fields: dict[str, list[str]]
    required_field_rules: dict[str, list[str]]
    # Whether ingest sets the resolved PDM releaser as approver_id; see
    # docs/PDM_INTEGRATION.md's user mapping section.
    set_approver_from_pdm: bool
    # Feature-tree templates (docs/FIELD_OWNERSHIP.md's "Label properties
    # and the feature-tree template" section): the text the SolidWorks
    # add-in writes verbatim into feature_tree_representation's custom
    # property, SolidWorks resolving each $PRP:"name" link in it.
    made_feature_tree_template: str
    bought_feature_tree_template: str


class PdmConnectionTestResponse(ResponseModel):
    product_name: str
    app_version: str
    user_id: int
