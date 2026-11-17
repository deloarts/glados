"""
HTTP request and response schemas for the made item and revision settings.
"""

from typing import Literal

from pydantic import BaseModel

from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel


class RevisionFieldPolicyEntryRequest(BaseModel):
    field: str
    web_requires_revision: bool
    pdm_update_in_place: bool


class UpdateMadeItemSettingsRequest(BaseModel):
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
    revision_field_policy: list[RevisionFieldPolicyEntryRequest] | None = None
    web_creation_allowed: bool | None = None
    pdm_part_number_pattern: str | None = None


class RevisionFieldPolicyEntryResponse(ResponseModel):
    field: str
    web_requires_revision: bool
    pdm_update_in_place: bool


class AdminMadeItemSettingsResponse(EntityResponse):
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
    revision_predecessor_status_web: Literal["ask"] | MadeItemCatalogueStatus
    revision_predecessor_status_pdm: MadeItemCatalogueStatus
    revision_field_policy: list[RevisionFieldPolicyEntryResponse]
    web_creation_allowed: bool
    pdm_part_number_pattern: str
