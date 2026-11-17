"""
Commands and results for the made item and revision settings.
"""

from pydantic import BaseModel

from src.modules.platform.application.dto.base import ResultBase


class RevisionFieldPolicyEntry(BaseModel):
    """Wire shape of one domain.services.item_field_ownership.
    RevisionFieldPolicy row."""

    field: str
    web_requires_revision: bool
    pdm_update_in_place: bool


class UpdateMadeItemSettingsCommand(BaseModel):
    item_number_format: str | None = None
    lot_number_format: str | None = None
    calculation_number_format: str | None = None
    checklist_number_format: str | None = None
    sequence_number_format: str | None = None
    meeting_number_format: str | None = None
    part_number_auto: bool | None = None
    part_number_editable: bool | None = None
    revision_start: str | None = None
    revision_separator: str | None = None
    revision_skip_ambiguous_letters: bool | None = None
    revision_only_newest_editable: bool | None = None
    revision_predecessor_status_web: str | None = None
    revision_predecessor_status_pdm: str | None = None
    revision_field_policy: list[RevisionFieldPolicyEntry] | None = None
    web_creation_allowed: bool | None = None
    pdm_part_number_pattern: str | None = None


class AdminMadeItemSettingsResult(ResultBase):
    item_number_format: str
    lot_number_format: str
    calculation_number_format: str
    checklist_number_format: str
    sequence_number_format: str
    meeting_number_format: str
    example: str
    lot_example: str
    calculation_example: str
    checklist_example: str
    sequence_example: str
    meeting_example: str
    part_number_auto: bool
    part_number_editable: bool
    revision_start: str
    revision_separator: str
    revision_skip_ambiguous_letters: bool
    revision_only_newest_editable: bool
    revision_predecessor_status_web: str
    revision_predecessor_status_pdm: str
    revision_field_policy: list[RevisionFieldPolicyEntry]
    web_creation_allowed: bool
    pdm_part_number_pattern: str
