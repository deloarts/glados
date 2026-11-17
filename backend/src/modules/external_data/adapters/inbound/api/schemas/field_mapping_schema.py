"""
Wire shape of GET /pat/settings/field-mapping (docs/reference/field-ownership.md
sections 2, 3 and 6): per-field owner, SolidWorks custom-property name, PDM
update-in-place flag, required-field state and `label_of` (naming the
field a label row is a label of, null for every other field), for both
item kinds, plus the feature-tree templates (`templates`) and the
pseudo-rule required fields (`rules`), both computed from the same
variable maps / settings. The SolidWorks add-in is already built against
this exact shape: field set, order and null semantics are fixed by
application.use_cases.admin_settings.get_field_mapping, this module only
mirrors the result DTO for the wire.
"""

from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel

__all__ = [
    "FeatureTreeTemplatesResponse",
    "FieldMappingEntryResponse",
    "FieldMappingResponse",
    "RequiredFieldRuleResponse",
]


class FieldMappingEntryResponse(ResponseModel):
    field: str
    owner: str  # "pdm" | "addin" | "addin_web" | "web" | "server"
    custom_property: str | None
    update_in_place: bool | None
    # Whether ingest cannot create/revise/claim a row without this field:
    # true for a locked field, per-field for a configurable one.
    required: bool
    # The field this one is a label of (item_field_ownership.
    # MADE_ITEM_LABEL_FIELDS/BOUGHT_ITEM_LABEL_FIELDS), None for every
    # other field.
    label_of: str | None


class FeatureTreeTemplatesResponse(ResponseModel):
    """AdminPdmSettings.made_feature_tree_template/
    bought_feature_tree_template, read-only here: the web settings
    GET/PUT surface (AdminPdmSettingsResponse) is where they are edited."""

    made: str
    bought: str


class RequiredFieldRuleResponse(ResponseModel):
    """One pseudo-rule required field (currently only made items'
    fabrication_step) with its current configured state."""

    name: str
    required: bool


class FieldMappingResponse(ResponseModel):
    made_items: list[FieldMappingEntryResponse]
    bought_items: list[FieldMappingEntryResponse]
    # AdminPdmSettings.made_feature_tree_template/bought_feature_tree_template,
    # computed on every read. A separate set of rows, not merged into
    # made_items/bought_items above.
    templates: FeatureTreeTemplatesResponse
    # Pseudo-rule required fields per kind, not part of made_items/
    # bought_items above since they are not columns on either item.
    rules: dict[str, list[RequiredFieldRuleResponse]]
