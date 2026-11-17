"""
Maps the made item and revision settings entity to its result DTO. The
number examples render for `today`, the tenant's day.
"""

from datetime import date

from src.modules.catalogue.application.dto.admin_settings_dto.made_items import (
    AdminMadeItemSettingsResult,
)
from src.modules.catalogue.application.dto.admin_settings_dto.made_items import (
    RevisionFieldPolicyEntry,
)
from src.modules.catalogue.domain.entities.admin_settings.made_items import AdminMadeItemSettings
from src.modules.platform.domain.services.numbering_format import render_example


class MadeItemSettingsMapper:
    @staticmethod
    def made_items_to_result(
        e: AdminMadeItemSettings, *, today: date
    ) -> AdminMadeItemSettingsResult:
        return AdminMadeItemSettingsResult(
            id=e.id,
            public_id=e.public_id,
            item_number_format=e.item_number_format,
            lot_number_format=e.lot_number_format,
            calculation_number_format=e.calculation_number_format,
            checklist_number_format=e.checklist_number_format,
            sequence_number_format=e.sequence_number_format,
            meeting_number_format=e.meeting_number_format,
            example=render_example(e.item_number_format, today=today),
            lot_example=render_example(e.lot_number_format, today=today),
            calculation_example=render_example(e.calculation_number_format, today=today),
            checklist_example=render_example(e.checklist_number_format, today=today),
            sequence_example=render_example(e.sequence_number_format, today=today),
            meeting_example=render_example(e.meeting_number_format, today=today),
            part_number_auto=e.part_number_auto,
            part_number_editable=e.part_number_editable,
            revision_start=e.revision_start,
            revision_separator=e.revision_separator,
            revision_skip_ambiguous_letters=e.revision_skip_ambiguous_letters,
            revision_only_newest_editable=e.revision_only_newest_editable,
            revision_predecessor_status_web=e.revision_predecessor_status_web,
            revision_predecessor_status_pdm=e.revision_predecessor_status_pdm,
            revision_field_policy=[
                RevisionFieldPolicyEntry(
                    field=p.field,
                    web_requires_revision=p.web_requires_revision,
                    pdm_update_in_place=p.pdm_update_in_place,
                )
                for p in e.revision_field_policy
            ],
            web_creation_allowed=e.web_creation_allowed,
            pdm_part_number_pattern=e.pdm_part_number_pattern,
        )
