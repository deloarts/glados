"""
Commands and results for the PDM settings, the PDM connection check, session
state and field mapping. The field mapping results back the PAT surface's
field-mapping endpoint.
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
from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.domain.value_objects.language import Language


class PdmWatchedFolderCommand(BaseModel):
    """One entry of UpdatePdmSettingsCommand.watched_folders. `path` is
    normalised here (not left to the use case) so the whole-list
    uniqueness check below compares already-normalised values, and so
    whatever UpdatePdmSettings stores is exactly what the poller will
    later match watched folders against.

    `match_by`/`filename_pattern` matter only for kind "documents"
    (docs/reference/pdm-documents.md section 2); see
    PdmWatchedFolder's docstring and validate_watched_folder, which this
    model delegates to so the same rule applies regardless of caller."""

    path: str
    # "by_kind" defers to the file's own `kind` datacard variable rather
    # than the folder asserting one; see PdmWatchedFolder's docstring.
    kind: str = "by_kind"
    recursive: bool
    enabled: bool
    match_by: str | None = None
    filename_pattern: str | None = None
    # PDM folder id (see PdmWatchedFolder's docstring), optional, None
    # when not resolved through the picker.
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
    def validate_documents_shape(self) -> "PdmWatchedFolderCommand":
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


class UpdatePdmSettingsCommand(BaseModel):
    made_item_variable_map: dict[str, str] | None = None
    bought_item_variable_map: dict[str, str] | None = None
    enabled: bool | None = None
    # None = leave as-is, like every optional field here. "" clears the
    # connection back to unconfigured.
    base_url: str | None = None
    vault_name: str | None = None
    username: str | None = None
    # None means "keep existing password unchanged", same convention as
    # UpdateMailSettingsCommand.password (mail.py).
    password: str | None = None
    verify_certificate: bool | None = None
    timeout_seconds: int | None = Field(default=None, ge=1, le=300)
    # None = leave the stored list as-is; a supplied list wholesale
    # replaces it, same convention as the variable maps above.
    watched_folders: list[PdmWatchedFolderCommand] | None = None
    # None = leave the stored list as-is, independently per kind: a PUT
    # naming only one of the six never touches the other five.
    made_released_state_ids: list[int] | None = None
    made_obsolete_state_ids: list[int] | None = None
    made_replaced_state_ids: list[int] | None = None
    bought_released_state_ids: list[int] | None = None
    bought_obsolete_state_ids: list[int] | None = None
    bought_replaced_state_ids: list[int] | None = None
    document_released_state_ids: list[int] | None = None
    poll_interval_minutes: int | None = Field(default=None, ge=1, le=1440)
    # Cold-folder poll cadence cap (see AdminPdmSettings.
    # cold_folder_max_multiplier's docstring). None = leave as-is, same
    # convention as every other optional field here.
    cold_folder_max_multiplier: int | None = Field(default=None, ge=1, le=64)
    ingest_concurrency: int | None = Field(default=None, ge=1, le=16)
    cad_items_read_only: bool | None = None
    # None = leave as-is, "" = the tenant's default language.
    addin_language: Language | Literal[""] | None = None
    # Write-back to PDM (see AdminPdmSettings' docstring); validated
    # against the resolved variable maps in UpdatePdmSettings itself.
    writeback_enabled: bool | None = None
    # File type rule, documents and thumbnails (see AdminPdmSettings'
    # docstring). None = leave the stored value as-is, same convention as
    # every other optional field here.
    made_item_extensions: list[str] | None = None
    bought_item_extensions: list[str] | None = None
    document_categories: dict[str, str] | None = None
    document_excluded_kinds: dict[str, list[str]] | None = None
    thumbnails_enabled: bool | None = None
    # Reconciliation report threshold (see ReconcilePdmVault); the request
    # flag itself, reconcile_requested_deep, is never accepted here; see
    # UpdatePdmSettings' module docstring.
    stuck_after_days: int | None = Field(default=None, ge=1, le=365)
    # Required-field validation (see AdminPdmSettings.required_fields'
    # docstring). None = leave the stored selection as-is, same
    # convention as every other optional field here; shape/unknown-name
    # validation happens in UpdatePdmSettings via
    # AdminPdmSettings.normalized_required_fields.
    required_fields: dict[str, list[str]] | None = None
    # PDM user matching (see AdminPdmSettings.set_approver_from_pdm's
    # docstring). None = leave the stored value as-is.
    set_approver_from_pdm: bool | None = None
    # Feature-tree templates (see AdminPdmSettings.made_feature_tree_template/
    # bought_feature_tree_template's docstring); validated against the
    # merged settings in UpdatePdmSettings itself
    # (AdminPdmSettings.assert_feature_tree_templates_valid). None = leave
    # the stored value as-is, same convention as every other optional
    # field here.
    made_feature_tree_template: str | None = None
    bought_feature_tree_template: str | None = None

    @field_validator("made_item_extensions", "bought_item_extensions")
    @classmethod
    def validate_extensions(cls, v: list[str] | None) -> list[str] | None:
        """Lower-case alphanumeric extensions, no leading dot, non-empty
        list; see AdminPdmSettings.made_item_extensions' docstring."""
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
        """Extension keys normalised the same way as the two extension
        lists above; values must be one of the known made/bought item
        file categories (checked against the union of both, so either
        family's category name is accepted) or `image_and_thumbnail`."""
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
        """See normalize_document_excluded_kinds."""
        return None if v is None else normalize_document_excluded_kinds(v)

    @field_validator("base_url")
    @classmethod
    def validate_base_url_scheme(cls, v: str | None) -> str | None:
        """Requires an http(s) scheme and strips a trailing slash, mirrored
        on UpdatePdmSettingsRequest per the schema package's docstring. Raising
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
        cls, v: list[PdmWatchedFolderCommand] | None
    ) -> list[PdmWatchedFolderCommand] | None:
        """Shape-only check: the supplied list, on its own, must not name
        the same normalised path twice. Disjointness between each kind's
        released and obsolete state lists and the enabled-requires-
        configuration rule need the currently stored settings to resolve a
        field left as None, so those live in UpdatePdmSettings itself
        (PdmSettingsInvalidError), not here."""
        if v is None:
            return v
        paths = [f.path for f in v]
        if len(paths) != len(set(paths)):
            duplicates = sorted({p for p in paths if paths.count(p) > 1})
            raise ValueError(f"watched_folders paths must be unique, duplicate(s): {duplicates}.")
        return v


class VerifyPdmConnectionCommand(BaseModel):
    """The connection to probe, plus an optional password override.

    Mirrors VerifyLdapConnectionCommand's "unsaved form values" role, but
    PDM already stores a service-account password, so an empty password
    here means "use the one already stored" rather than requiring the
    admin to retype it on every test.
    """

    base_url: str
    vault_name: str
    username: str
    password: str | None = None
    verify_certificate: bool = True
    timeout_seconds: int = Field(default=15, ge=1, le=300)


class PdmConnectionTestResult(BaseModel):
    product_name: str
    app_version: str
    user_id: int


class PdmSessionResult(BaseModel):
    """Deliberately carries no token: `active` is all a caller needs to know
    to decide whether the console can be used without triggering a fresh
    login."""

    active: bool
    obtained_at: datetime | None
    user_id: int | None


class ItemFieldOwnershipResult(BaseModel):
    """One row of the static ownership table, generated from
    domain.services.item_field_ownership.item_fields(), never stored."""

    field: str
    owner: str
    mappable: bool
    policy_applicable: bool
    # The field this one is a label of (item_field_ownership.
    # MADE_ITEM_LABEL_FIELDS/BOUGHT_ITEM_LABEL_FIELDS), None for every
    # other field.
    label_of: str | None


class ItemFieldsResult(BaseModel):
    made: list[ItemFieldOwnershipResult]
    bought: list[ItemFieldOwnershipResult]


class FeatureTreeTemplatesResult(BaseModel):
    """AdminPdmSettings.made_feature_tree_template/
    bought_feature_tree_template, for the PAT field-mapping response. The
    web settings result serves the same two values as its own top-level
    made_feature_tree_template/bought_feature_tree_template fields."""

    made: str
    bought: str


class PdmWatchedFolderResult(BaseModel):
    path: str
    kind: str
    recursive: bool
    enabled: bool
    match_by: str | None
    filename_pattern: str | None
    folder_id: int | None


class AdminPdmSettingsResult(ResultBase):
    made_item_variable_map: dict[str, str]
    bought_item_variable_map: dict[str, str]
    # the static ownership table lives here (rather than a new
    # top-level key on AllAdminSettingsResponse) because the "Item Fields"
    # admin tab saves made-item settings (the revision policy) and PDM
    # settings (the field mapping) together and needs both the mapping and
    # the read-only owner/mappable/policy_applicable badges in one place;
    # this is the PUT /admin/settings/pdm response the tab's GET starts from.
    item_fields: ItemFieldsResult
    enabled: bool
    # PDM__ALLOW_MUTATING_OPERATIONS, the deployment's switch for the admin
    # API console's mutating operations. Read-only, set in the environment.
    mutating_operations_enabled: bool
    base_url: str
    vault_name: str
    username: str
    password_configured: bool
    verify_certificate: bool
    timeout_seconds: int
    # base_url + vault_name + username + password all present, see
    # AdminPdmSettings.is_configured. Gates the test button, the console
    # and whether a session can be obtained at all.
    configured: bool
    session: PdmSessionResult
    watched_folders: list[PdmWatchedFolderResult]
    made_released_state_ids: list[int]
    made_obsolete_state_ids: list[int]
    made_replaced_state_ids: list[int]
    bought_released_state_ids: list[int]
    bought_obsolete_state_ids: list[int]
    bought_replaced_state_ids: list[int]
    document_released_state_ids: list[int]
    poll_interval_minutes: int
    cold_folder_max_multiplier: int
    ingest_concurrency: int
    vault_id: str
    cad_items_read_only: bool
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
    # Only GetPdmSettings populates this from
    # IPdmFileSnapshotRepository.counts_by_state; UpdatePdmSettings and the
    # combined AllAdminSettingsResponse leave it {}, see pdm_to_result's
    # docstring.
    snapshot_counts: dict[str, int]
    # Required-field validation (docs/PDM_INTEGRATION.md's "required
    # fields" section). required_fields is the stored, configurable
    # selection (never holds a locked name); locked_required_fields and
    # required_field_rules are read-only, computed from
    # src.modules.external_data.domain.services.pdm_required_fields on every read, for the
    # settings page's checklist.
    required_fields: dict[str, list[str]]
    locked_required_fields: dict[str, list[str]]
    required_field_rules: dict[str, list[str]]
    # PDM user matching (see AdminPdmSettings.set_approver_from_pdm's
    # docstring).
    set_approver_from_pdm: bool
    # Feature-tree templates (see AdminPdmSettings.made_feature_tree_template/
    # bought_feature_tree_template's docstring).
    made_feature_tree_template: str
    bought_feature_tree_template: str


class FieldMappingEntryResult(BaseModel):
    """One field of the GET /pat/settings/field-mapping response; see
    use_cases.admin_settings.get_field_mapping for how the three sources
    (item_field_ownership.item_fields(), AdminPdmSettings' variable maps,
    AdminMadeItemSettings.revision_field_policy) combine into this row.
    Computed, never stored."""

    field: str
    owner: str  # "pdm" | "addin" | "addin_web" | "web" | "server"
    custom_property: str | None  # SW datacard variable name; None = unmapped
    update_in_place: bool | None  # made items' PDM revision policy; None = not policy-applicable
    # Whether ingest cannot create/revise/claim a row without this field:
    # true for a locked field, per-field for a configurable one, see
    # application.services.pdm_required_fields.
    required: bool
    # The field this one is a label of (item_field_ownership.
    # MADE_ITEM_LABEL_FIELDS/BOUGHT_ITEM_LABEL_FIELDS), None for every
    # other field.
    label_of: str | None


class RequiredFieldRuleResult(BaseModel):
    """One pseudo-rule required field (src.domain.services.
    pdm_required_fields.RequiredFieldRule) with its current configured
    state, for the GET /pat/settings/field-mapping response's `rules`."""

    name: str
    required: bool


class FieldMappingResult(BaseModel):
    made_items: list[FieldMappingEntryResult]
    bought_items: list[FieldMappingEntryResult]
    # AdminPdmSettings.made_feature_tree_template/bought_feature_tree_template,
    # computed on every read; see FeatureTreeTemplatesResult.
    templates: FeatureTreeTemplatesResult
    # Pseudo-rule required fields per kind (currently only made items'
    # fabrication_step), not part of made_items/bought_items above since
    # they are not columns on either item.
    rules: dict[str, list[RequiredFieldRuleResult]]
