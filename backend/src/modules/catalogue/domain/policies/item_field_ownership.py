"""Code counterpart of docs/FIELD_OWNERSHIP.md: per-field ownership for
MadeItem and BoughtItem, and the made-item revision policy that decides
which web changes need a new revision and which PDM file versions update
in place. No I/O; callers pass the resolved policy in.

Label fields are mappable, add-in-owned rows that ingest never reads; see
addin_written_fields.
"""

from dataclasses import dataclass
from datetime import date
from typing import Protocol

from src.modules.catalogue.domain.entities.made_item import MadeItem

# ── Revision policy ─────────────────────────────────────────────────────

# Candidate fields for the revision policy, made items only. `processes`
# is authored as a whole (routing + grouping) rather than through the
# update command; see web_blocked_changes below.
REVISION_POLICY_FIELDS: tuple[str, ...] = (
    "article_name",
    "material",
    "mass",
    "base_size",
    "note",
    "weblink",
    "article_group_ids",
    "bought_item_id",
    "source_item_id",
    "customer_id",
    "customer_part_number",
    "customer_revision",
    "revision_date",
    "revision_note",
    "processes",
)


@dataclass(frozen=True)
class RevisionFieldPolicy:
    field: str
    # On a WEB item this field only changes through "New revision".
    web_requires_revision: bool
    # A new file version under the same PDM.Revision updates this field in
    # place; other fields wait for the next PDM.Revision, which creates a row.
    pdm_update_in_place: bool


def default_policy() -> list[RevisionFieldPolicy]:
    """Default policy per docs/FIELD_OWNERSHIP.md. The PDM column is mostly
    the inverse of the web one, except `mass`, which PDM recomputes on every
    save, and the customer data, which a web edit only changes through a new
    revision but which never holds up ingest; both update in place."""
    web_requires_revision = {
        "article_name",
        "material",
        "mass",
        "base_size",
        "bought_item_id",
        "source_item_id",
        "customer_id",
        "customer_part_number",
        "customer_revision",
    }
    pdm_update_in_place = {
        "mass",
        "note",
        "weblink",
        "article_group_ids",
        "customer_id",
        "customer_part_number",
        "customer_revision",
        "revision_date",
        "revision_note",
    }
    return [
        RevisionFieldPolicy(
            field=field,
            web_requires_revision=field in web_requires_revision,
            pdm_update_in_place=field in pdm_update_in_place,
        )
        for field in REVISION_POLICY_FIELDS
    ]


class _UpdateMadeItemFields(Protocol):
    """The UpdateMadeItemCommand fields the revision policy reads, declared
    structurally because the domain may not import the application layer."""

    article_name: str
    material: str | None
    mass: int | None
    base_size: str | None
    note: str | None
    weblink: str | None
    article_group_ids: list[int]
    bought_item_id: int | None
    source_item_id: int | None
    customer_id: int | None
    customer_part_number: str | None
    customer_revision: str | None
    revision_date: date | None
    revision_note: str | None


# processes is never a field on the update command.
_BLOCKABLE_FIELDS = tuple(f for f in REVISION_POLICY_FIELDS if f != "processes")


def web_blocked_changes(
    item: MadeItem,
    cmd: _UpdateMadeItemFields,
    policy: list[RevisionFieldPolicy],
) -> set[str]:
    """Fields `cmd` would change that the policy reserves for a new
    revision. Article groups compare as a set, since reordering is no change."""
    requires_revision = {p.field: p.web_requires_revision for p in policy}
    blocked: set[str] = set()
    for field in _BLOCKABLE_FIELDS:
        if not requires_revision.get(field, False):
            continue
        old_value = getattr(item, field)
        new_value = getattr(cmd, field)
        changed = (
            set(old_value) != set(new_value)
            if field == "article_group_ids"
            else old_value != new_value
        )
        if changed:
            blocked.add(field)
    return blocked


# ── Static ownership table (docs/reference/field-ownership.md sections 2 and 3) ──────────────


@dataclass(frozen=True)
class ItemFieldOwnership:
    field: str
    owner: str  # "addin" | "pdm" | "addin_web" | "web" | "server"
    mappable: bool  # may be assigned a PDM datacard variable
    policy_applicable: bool  # appears in the revision policy table (made items only)
    # The field this one is a label of, otherwise None.
    label_of: str | None


# Glados writes these datacard variables and never reads them for ingest.
WRITEBACK_MAPPABLE_FIELDS: tuple[str, ...] = (
    "glados_ids",
    "newest_revision_sync_state",
    "newest_revision_synced_at",
)


@dataclass(frozen=True)
class LabelFieldSpec:
    field: str
    source_field: str


# Label fields let datacards, BOMs and PDM search show a name instead of an
# id (see docs/FIELD_OWNERSHIP.md). The order is the wire order of the
# settings and PAT field-mapping responses.
MADE_ITEM_LABEL_FIELDS: tuple[LabelFieldSpec, ...] = (
    LabelFieldSpec(field="article_group_names", source_field="article_group_ids"),
    LabelFieldSpec(field="process_names", source_field="processes"),
    LabelFieldSpec(field="source_item_name", source_field="source_item_id"),
    LabelFieldSpec(field="customer_name", source_field="customer_id"),
)

BOUGHT_ITEM_LABEL_FIELDS: tuple[LabelFieldSpec, ...] = (
    LabelFieldSpec(field="manufacturer_name", source_field="manufacturer_id"),
    LabelFieldSpec(field="article_group_names", source_field="article_group_ids"),
)

# Holds the feature-tree template, written verbatim and resolved by
# SolidWorks; excluded from ingest like labels.
FEATURE_TREE_MAPPABLE_FIELD = "feature_tree_representation"


def label_fields(kind: str) -> tuple[LabelFieldSpec, ...]:
    """The label field specs for `kind` ("made" or "bought")."""
    return MADE_ITEM_LABEL_FIELDS if kind == "made" else BOUGHT_ITEM_LABEL_FIELDS


def addin_written_fields(kind: str) -> frozenset[str]:
    """Mappable fields the add-in writes and ingest never reads: the labels
    and the feature-tree field. Ingest and required-field candidates both
    exclude them."""
    return frozenset(spec.field for spec in label_fields(kind)) | {FEATURE_TREE_MAPPABLE_FIELD}


# The only fields a PDM field mapping may name. `kind` is no item column; it
# lets a `by_kind` folder read a file's kind from its datacard.
MADE_ITEM_MAPPABLE_FIELDS: tuple[str, ...] = (
    "part_number",
    "revision",
    "revision_date",
    "revision_note",
    "article_name",
    "material",
    "mass",
    "base_size",
    "note",
    "weblink",
    "article_group_ids",
    "bought_item_id",
    "source_item_id",
    "customer_id",
    "customer_part_number",
    "customer_revision",
    "processes",
    *(spec.field for spec in MADE_ITEM_LABEL_FIELDS),
    FEATURE_TREE_MAPPABLE_FIELD,
    "kind",
    *WRITEBACK_MAPPABLE_FIELDS,
)

BOUGHT_ITEM_MAPPABLE_FIELDS: tuple[str, ...] = (
    "part_number",
    "revision",
    "article_name",
    "order_code_1",
    "order_code_2",
    "gtin",
    "ean",
    "tariff_number",
    "mass",
    "note",
    "weblink",
    "manufacturer_id",
    "article_group_ids",
    "edp_part_id",
    *(spec.field for spec in BOUGHT_ITEM_LABEL_FIELDS),
    FEATURE_TREE_MAPPABLE_FIELD,
    "kind",
    *WRITEBACK_MAPPABLE_FIELDS,
)

# (field, owner) in the order of docs/FIELD_OWNERSHIP.md.
_MADE_ITEM_OWNERS: tuple[tuple[str, str], ...] = (
    ("part_number", "pdm"),
    ("revision", "pdm"),
    ("revision_date", "pdm"),
    ("revision_note", "pdm"),
    ("public_id", "server"),
    ("vault_id", "pdm"),
    ("pdm_file_id", "pdm"),
    ("pdm_file_version", "pdm"),
    ("pdm_synced_at", "pdm"),
    ("pdm_sync_state", "server"),
    ("article_name", "addin"),
    ("material", "addin"),
    ("mass", "addin"),
    ("base_size", "addin"),
    ("note", "addin"),
    ("weblink", "addin"),
    ("article_group_ids", "addin"),
    ("article_group_names", "addin"),
    ("bought_item_id", "addin"),
    ("source_item_id", "addin_web"),
    # The value ingest last received for source_item_id, see principle 7.
    ("pdm_source_item_id", "server"),
    ("source_item_name", "addin"),
    ("customer_id", "addin"),
    ("customer_name", "addin"),
    ("customer_part_number", "addin"),
    ("customer_revision", "addin"),
    ("processes", "addin"),
    ("process_names", "addin"),
    (FEATURE_TREE_MAPPABLE_FIELD, "addin"),
    ("kind", "addin"),
    # Driven by the PDM workflow state rather than a datacard variable.
    ("status", "pdm"),
    ("successor_item_id", "web"),
    ("approver_id", "web"),
    ("files", "web"),
    ("id", "server"),
    ("data_source", "server"),
    ("created", "server"),
    ("changed", "server"),
    ("changes", "server"),
    ("archived", "server"),
    ("creator_id", "server"),
    ("changed_by_id", "server"),
    ("edit_version", "server"),
    ("source_label", "server"),
    ("source_sublabel", "server"),
    # Write-back only, see WRITEBACK_MAPPABLE_FIELDS.
    ("glados_ids", "server"),
    ("newest_revision_sync_state", "server"),
    ("newest_revision_synced_at", "server"),
)

# Bought items have no revision policy. `manufacturer_name` here is the
# datacard label, unrelated to the response field of the same name.
_BOUGHT_ITEM_OWNERS: tuple[tuple[str, str], ...] = (
    ("article_name", "addin"),
    ("order_code_1", "addin"),
    ("order_code_2", "addin"),
    ("gtin", "addin"),
    ("ean", "addin"),
    ("tariff_number", "addin"),
    ("mass", "addin"),
    ("note", "addin"),
    ("weblink", "addin"),
    ("manufacturer_id", "addin"),
    ("manufacturer_name", "addin"),
    ("article_group_ids", "addin"),
    ("article_group_names", "addin"),
    (FEATURE_TREE_MAPPABLE_FIELD, "addin"),
    ("kind", "addin"),
    ("part_number", "pdm"),
    ("revision", "pdm"),
    # PDM-owned, see the matching comment in _MADE_ITEM_OWNERS above.
    ("status", "pdm"),
    ("successor_item_id", "web"),
    ("approver_id", "web"),
    ("files", "web"),
    ("product_family_id", "web"),
    ("over_delivery_tolerance_percent", "web"),
    ("under_delivery_tolerance_percent", "web"),
    # Picked from the EPLAN Data Portal in the web or in the add-in, see
    # principle 7: PDM's value wins only when it changes.
    ("edp_part_id", "addin_web"),
    # The value ingest last received for edp_part_id.
    ("pdm_edp_part_id", "server"),
    ("edp_synced_at", "server"),
    ("data_source", "server"),
    ("vault_id", "pdm"),
    ("pdm_file_id", "pdm"),
    ("pdm_file_version", "pdm"),
    ("pdm_synced_at", "pdm"),
    ("pdm_sync_state", "server"),
    ("public_id", "server"),
    ("id", "server"),
    ("created", "server"),
    ("changed", "server"),
    ("changes", "server"),
    ("archived", "server"),
    ("creator_id", "server"),
    ("changed_by_id", "server"),
    ("edit_version", "server"),
    ("pdf_files", "server"),
    # Write-back-only, see WRITEBACK_MAPPABLE_FIELDS above.
    ("glados_ids", "server"),
    ("newest_revision_sync_state", "server"),
    ("newest_revision_synced_at", "server"),
)


def item_fields() -> dict[str, list[ItemFieldOwnership]]:
    """The static ownership table of the admin "Item Fields" tab, keyed
    "made" and "bought"."""
    made_label_of = {spec.field: spec.source_field for spec in MADE_ITEM_LABEL_FIELDS}
    bought_label_of = {spec.field: spec.source_field for spec in BOUGHT_ITEM_LABEL_FIELDS}
    return {
        "made": [
            ItemFieldOwnership(
                field=field,
                owner=owner,
                mappable=field in MADE_ITEM_MAPPABLE_FIELDS,
                policy_applicable=field in REVISION_POLICY_FIELDS,
                label_of=made_label_of.get(field),
            )
            for field, owner in _MADE_ITEM_OWNERS
        ],
        "bought": [
            ItemFieldOwnership(
                field=field,
                owner=owner,
                mappable=field in BOUGHT_ITEM_MAPPABLE_FIELDS,
                policy_applicable=False,
                label_of=bought_label_of.get(field),
            )
            for field, owner in _BOUGHT_ITEM_OWNERS
        ],
    }
