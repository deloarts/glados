"""Backs GET /pat/settings/field-mapping: per-field owner, custom-property
name, update-in-place flag and required flag for made and bought items, so
the SolidWorks add-in reads property names from configuration. Read-only,
non-sensitive configuration, so a valid PAT is enough.

Owners come from item_field_ownership.item_fields(), names from the
variable maps ("" means unmapped and reports None), update-in-place from
the made-item revision policy, and required flags from the locked set plus
the admin selection. The field set and order are a fixed wire contract
(see docs/reference/pdm-settings.md), not item_fields()'s own order.
"""

from src.modules.catalogue.domain.policies.item_field_ownership import item_fields
from src.modules.external_data.application.dto.admin_settings_dto.pdm import (
    FeatureTreeTemplatesResult,
)
from src.modules.external_data.application.dto.admin_settings_dto.pdm import FieldMappingEntryResult
from src.modules.external_data.application.dto.admin_settings_dto.pdm import FieldMappingResult
from src.modules.external_data.application.dto.admin_settings_dto.pdm import RequiredFieldRuleResult
from src.modules.external_data.domain.services.pdm_required_fields import LOCKED_REQUIRED_FIELDS
from src.modules.external_data.domain.services.pdm_required_fields import REQUIRED_FIELD_RULES
from src.modules.external_data.ports.outbound.external_data_settings_repository import (
    IExternalDataSettingsRepository,
)

# Wire order: identity and PDM fields, CAD-authored, web-owned, data_source,
# then fields appended later. Never reorder, only append.
_MADE_ITEM_FIELDS: tuple[str, ...] = (
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
    "processes",
    "status",
    "successor_item_id",
    "approver_id",
    "files",
    "data_source",
    "kind",
    "glados_ids",
    "newest_revision_sync_state",
    "newest_revision_synced_at",
    "article_group_names",
    "process_names",
    "source_item_name",
    "feature_tree_representation",
    "customer_id",
    "customer_part_number",
    "customer_revision",
    "customer_name",
)

_BOUGHT_ITEM_FIELDS: tuple[str, ...] = (
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
    "status",
    "successor_item_id",
    "approver_id",
    "files",
    "data_source",
    "kind",
    "glados_ids",
    "newest_revision_sync_state",
    "newest_revision_synced_at",
    "manufacturer_name",
    "article_group_names",
    "feature_tree_representation",
    "edp_part_id",
)


class GetFieldMapping:
    def __init__(self, repo: IExternalDataSettingsRepository) -> None:
        self._repo = repo

    async def execute(self) -> FieldMappingResult:
        fields = item_fields()
        made_rows = {f.field: f for f in fields["made"]}
        bought_rows = {f.field: f for f in fields["bought"]}

        pdm = await self._repo.get_pdm()
        made_item_settings = await self._repo.get_made_items()
        update_in_place = {
            p.field: p.pdm_update_in_place for p in made_item_settings.revision_field_policy
        }
        made_required = set(LOCKED_REQUIRED_FIELDS["made"]) | set(
            pdm.required_fields.get("made", [])
        )
        bought_required = set(LOCKED_REQUIRED_FIELDS["bought"]) | set(
            pdm.required_fields.get("bought", [])
        )

        return FieldMappingResult(
            made_items=[
                FieldMappingEntryResult(
                    field=field,
                    owner=made_rows[field].owner,
                    custom_property=pdm.made_item_variable_map.get(field) or None,
                    update_in_place=update_in_place.get(field),
                    required=field in made_required,
                    label_of=made_rows[field].label_of,
                )
                for field in _MADE_ITEM_FIELDS
            ],
            bought_items=[
                FieldMappingEntryResult(
                    field=field,
                    owner=bought_rows[field].owner,
                    custom_property=pdm.bought_item_variable_map.get(field) or None,
                    update_in_place=None,
                    required=field in bought_required,
                    label_of=bought_rows[field].label_of,
                )
                for field in _BOUGHT_ITEM_FIELDS
            ],
            templates=FeatureTreeTemplatesResult(
                made=pdm.made_feature_tree_template,
                bought=pdm.bought_feature_tree_template,
            ),
            rules={
                kind: [
                    RequiredFieldRuleResult(
                        name=rule.name, required=rule.name in pdm.required_fields.get(kind, [])
                    )
                    for rule in rules
                ]
                for kind, rules in REQUIRED_FIELD_RULES.items()
            },
        )
