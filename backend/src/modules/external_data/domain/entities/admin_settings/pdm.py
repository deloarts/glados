"""Domain entity for the PDM settings singleton: datacard field mapping,
Web API connection, cached session and poller configuration, plus the
validation rules applied after merging a change. docs/PDM_INTEGRATION.md
describes every setting."""

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime

from src.modules.catalogue.domain.policies.item_field_ownership import FEATURE_TREE_MAPPABLE_FIELD
from src.modules.external_data.domain.errors import PdmSettingsInvalidError
from src.modules.external_data.domain.services.feature_tree_template import (
    validate_feature_tree_template,
)
from src.modules.external_data.domain.services.pdm_required_fields import (
    normalize_required_fields_selection,
)
from src.modules.external_data.domain.value_objects.pdm_watched_folder import PdmWatchedFolder
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class AdminPdmSettings(Entity):
    """PDM settings singleton. "" in a variable map means "not mapped", so
    ingest never writes that field.

    The session fields cache the Web API bearer token. A session likely
    holds a license seat and has no expiry claim, so every worker and the
    scheduler share this one token instead of logging in separately (see
    application/services/pdm_session.py).

    Workflow state lists exist per item kind, because the two catalogues
    need not share a workflow, and a kind's released, obsolete and replaced
    lists must be pairwise disjoint."""

    made_item_variable_map: dict[str, str]
    bought_item_variable_map: dict[str, str]
    enabled: bool
    base_url: str
    vault_name: str
    username: str
    # Plaintext at rest, same rationale as AdminMailSettings.password.
    password: str | None
    verify_certificate: bool
    timeout_seconds: int
    session_token: str | None
    session_user_id: int | None
    session_obtained_at: datetime | None
    watched_folders: list[PdmWatchedFolder]
    made_released_state_ids: list[int]
    made_obsolete_state_ids: list[int]
    bought_released_state_ids: list[int]
    bought_obsolete_state_ids: list[int]
    made_replaced_state_ids: list[int]
    bought_replaced_state_ids: list[int]
    poll_interval_minutes: int
    vault_id: str
    cad_items_read_only: bool
    last_poll_at: datetime | None
    last_poll_error: str | None
    last_poll_summary: str | None
    # Writes the three Glados.* datacard variables back after each ingest.
    # Glados never changes a file's workflow state.
    writeback_enabled: bool
    # Lower-case extensions without a dot that a watched folder snapshots.
    # A `by_kind` folder admits both sets until the kind is known.
    made_item_extensions: list[str]
    bought_item_extensions: list[str]
    # Extension to item file category for a `documents` folder; unmapped
    # extensions are never synced.
    document_categories: dict[str, str]
    # Opt-in, because most vaults have no task rendering thumbnails.
    thumbnails_enabled: bool
    # Days after which a pending or failed snapshot is a stuck_file finding.
    stuck_after_days: int
    # None when nothing is queued, False for a quick and True for a deep
    # reconciliation. The next scheduler tick consumes it regardless of the
    # poll interval and clears it on success and failure alike.
    reconcile_requested_deep: bool | None
    # Admin-selected required fields per kind on top of the locked set,
    # never holding a locked name.
    required_fields: dict[str, list[str]]

    # Sets the releasing PDM user as approver on ingest. Off by default, so
    # approval stays a manual action until an admin opts in.
    set_approver_from_pdm: bool = False
    # What the add-in writes verbatim into feature_tree_representation, with
    # SolidWorks resolving each $PRP link (see docs/FIELD_OWNERSHIP.md).
    # Defaults match the ORM server defaults.
    made_feature_tree_template: str = (
        '$PRP:"PDM.PartNumber" Rev$PRP:"PDM.Revision" ($PRP:"Glados.ArticleName")'
    )
    bought_feature_tree_template: str = (
        '$PRP:"Glados.ArticleName" - $PRP:"Glados.OrderCode1" - $PRP:"Glados.ManufacturerName"'
    )
    # Backoff cap for an unchanged folder, as a multiple of the poll
    # interval; 1 disables backoff.
    cold_folder_max_multiplier: int = 8
    # How many changed files a poll run ingests at once, each on its own
    # database session; 1 processes them one after another.
    ingest_concurrency: int = 4
    # Workflow states a `documents` folder's files are synced in. A document
    # in any other state is skipped, so an export still being worked on
    # never reaches an item; empty means no document is synced at all.
    document_released_state_ids: list[int] = field(default_factory=list)
    # The language the pat API gives catalogue labels in (article groups,
    # fabrication methods and so on), and with that the language the
    # SolidWorks add-in writes them into the vault in. "" means the tenant's
    # default language; a code no longer offered falls back to it as well.
    addin_language: str = ""
    # Extension to the item kinds ("made", "bought") whose matched items do
    # not receive that document, for example a bought item's STEP export.
    # A kind absent from an extension's list ingests it, so an empty map
    # syncs every mapped document for both kinds.
    document_excluded_kinds: dict[str, list[str]] = field(default_factory=dict)

    def assert_feature_tree_templates_valid(self) -> None:
        """Raises when a feature-tree template is not a single line, is too
        long, or links to the property it is written into."""
        for kind, template, variable_map in (
            ("made", self.made_feature_tree_template, self.made_item_variable_map),
            ("bought", self.bought_feature_tree_template, self.bought_item_variable_map),
        ):
            own_property = variable_map.get(FEATURE_TREE_MAPPABLE_FIELD, "")
            try:
                validate_feature_tree_template(kind, template, own_property)
            except ValueError as exc:
                raise PdmSettingsInvalidError(str(exc)) from exc

    @property
    def is_configured(self) -> bool:
        """Whether the connection has everything needed to authenticate."""
        return bool(self.base_url and self.vault_name and self.username and self.password)

    def connection_differs(self, other: "AdminPdmSettings") -> bool:
        """Whether the connection fields differ, which invalidates a cached
        session."""
        return (
            self.base_url != other.base_url
            or self.vault_name != other.vault_name
            or self.username != other.username
            or self.password != other.password
        )

    def sync_scope_differs(self, other: "AdminPdmSettings") -> bool:
        """Whether a field deciding which files are eligible to ingest
        differs. Files skipped for a settings reason are requeued only then."""
        return (
            self.made_item_variable_map != other.made_item_variable_map
            or self.bought_item_variable_map != other.bought_item_variable_map
            or self.made_released_state_ids != other.made_released_state_ids
            or self.made_obsolete_state_ids != other.made_obsolete_state_ids
            or self.made_replaced_state_ids != other.made_replaced_state_ids
            or self.bought_released_state_ids != other.bought_released_state_ids
            or self.bought_obsolete_state_ids != other.bought_obsolete_state_ids
            or self.bought_replaced_state_ids != other.bought_replaced_state_ids
            or self.watched_folders != other.watched_folders
            or self.made_item_extensions != other.made_item_extensions
            or self.bought_item_extensions != other.bought_item_extensions
            or self.document_categories != other.document_categories
            or self.document_excluded_kinds != other.document_excluded_kinds
            or self.document_released_state_ids != other.document_released_state_ids
        )

    def ingests_document_for(self, extension: str, kind: str) -> bool:
        """Whether a document with `extension` is stored on an item of
        `kind`; the category map decides what it is stored as."""
        return kind not in self.document_excluded_kinds.get(extension, [])

    def normalized_document_excluded_kinds(self) -> dict[str, list[str]]:
        """The exclusions limited to extensions the category map still
        holds, without empty lists, so a removed category row leaves no
        stale exclusion behind that would resurface when it is re-added."""
        return {
            ext: sorted(set(kinds))
            for ext, kinds in self.document_excluded_kinds.items()
            if ext in self.document_categories and kinds
        }

    def released_state_ids_for(self, kind: str) -> list[int]:
        """The released-state ids for `kind` ("made" or "bought")."""
        return self.made_released_state_ids if kind == "made" else self.bought_released_state_ids

    def obsolete_state_ids_for(self, kind: str) -> list[int]:
        """The obsolete-state ids for `kind`."""
        return self.made_obsolete_state_ids if kind == "made" else self.bought_obsolete_state_ids

    def replaced_state_ids_for(self, kind: str) -> list[int]:
        """The replaced-state ids for `kind`."""
        return self.made_replaced_state_ids if kind == "made" else self.bought_replaced_state_ids

    def assert_state_id_lists_disjoint(self) -> None:
        """Raises when a workflow state would drive two lifecycle statuses
        for the same kind."""
        for kind, released, obsolete, replaced in (
            (
                "made",
                self.made_released_state_ids,
                self.made_obsolete_state_ids,
                self.made_replaced_state_ids,
            ),
            (
                "bought",
                self.bought_released_state_ids,
                self.bought_obsolete_state_ids,
                self.bought_replaced_state_ids,
            ),
        ):
            for name_a, list_a, name_b, list_b in (
                ("released", released, "obsolete", obsolete),
                ("released", released, "replaced", replaced),
                ("obsolete", obsolete, "replaced", replaced),
            ):
                overlap = set(list_a) & set(list_b)
                if overlap:
                    raise PdmSettingsInvalidError(
                        f"{kind} {name_a} and {name_b} state ids must be disjoint, "
                        f"overlap: {sorted(overlap)}."
                    )

    def normalized_required_fields(self) -> dict[str, list[str]]:
        """`required_fields` without locked names and duplicates. Raises
        ValueError for a field that is not a candidate for its kind."""
        return {
            kind: normalize_required_fields_selection(kind, self.required_fields.get(kind, []))
            for kind in ("made", "bought")
        }
