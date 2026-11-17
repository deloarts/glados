"""
Row mapping for the admin_made_item_settings singleton. Converts the ORM row to
the domain entity and the entity to the column dict
SqlAlchemyAdminSettingsRepository upserts.
"""

from typing import Any

from src.modules.catalogue.adapters.outbound.persistence.models.admin_settings_model.made_items import (
    AdminMadeItemSettingsOrmModel,
)
from src.modules.catalogue.domain.entities.admin_settings.made_items import AdminMadeItemSettings
from src.modules.catalogue.domain.policies.item_field_ownership import RevisionFieldPolicy


def _policy(stored: list[dict[str, bool | str]]) -> list[RevisionFieldPolicy]:
    """The stored revision policy as entries, in the stored order."""
    return [
        RevisionFieldPolicy(
            field=str(p["field"]),
            web_requires_revision=bool(p["web_requires_revision"]),
            pdm_update_in_place=bool(p["pdm_update_in_place"]),
        )
        for p in stored
    ]


def to_entity(o: AdminMadeItemSettingsOrmModel) -> AdminMadeItemSettings:
    return AdminMadeItemSettings(
        id=o.id,
        public_id=o.public_id,
        item_number_format=o.item_number_format,
        lot_number_format=o.lot_number_format,
        calculation_number_format=o.calculation_number_format,
        checklist_number_format=o.checklist_number_format,
        sequence_number_format=o.sequence_number_format,
        meeting_number_format=o.meeting_number_format,
        part_number_auto=o.part_number_auto,
        part_number_editable=o.part_number_editable,
        revision_start=o.revision_start,
        revision_separator=o.revision_separator,
        revision_skip_ambiguous_letters=o.revision_skip_ambiguous_letters,
        revision_only_newest_editable=o.revision_only_newest_editable,
        revision_predecessor_status_web=o.revision_predecessor_status_web,
        revision_predecessor_status_pdm=o.revision_predecessor_status_pdm,
        revision_field_policy=_policy(o.revision_field_policy),
        web_creation_allowed=o.web_creation_allowed,
        pdm_part_number_pattern=o.pdm_part_number_pattern,
    )


def to_dict(s: AdminMadeItemSettings) -> dict[str, Any]:
    return {
        "item_number_format": s.item_number_format,
        "lot_number_format": s.lot_number_format,
        "calculation_number_format": s.calculation_number_format,
        "checklist_number_format": s.checklist_number_format,
        "sequence_number_format": s.sequence_number_format,
        "meeting_number_format": s.meeting_number_format,
        "part_number_auto": s.part_number_auto,
        "part_number_editable": s.part_number_editable,
        "revision_start": s.revision_start,
        "revision_separator": s.revision_separator,
        "revision_skip_ambiguous_letters": s.revision_skip_ambiguous_letters,
        "revision_only_newest_editable": s.revision_only_newest_editable,
        "revision_predecessor_status_web": s.revision_predecessor_status_web,
        "revision_predecessor_status_pdm": s.revision_predecessor_status_pdm,
        "revision_field_policy": [
            {
                "field": p.field,
                "web_requires_revision": p.web_requires_revision,
                "pdm_update_in_place": p.pdm_update_in_place,
            }
            for p in s.revision_field_policy
        ],
        "web_creation_allowed": s.web_creation_allowed,
        "pdm_part_number_pattern": s.pdm_part_number_pattern,
    }
