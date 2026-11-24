"""
HTTP request and response schemas for the production and scheduling settings.
"""

from pydantic import BaseModel
from pydantic import Field

from src.modules.fulfillment.adapters.inbound.api.schemas.production_machine_schema import (
    WorkIntervalSchema,
)
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    MAX_FROZEN_WINDOW_HOURS,
)
from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse


class UpdateProductionSettingsRequest(BaseModel):
    production_order_number_format: str | None = None
    # weekday (0=Monday..6=Sunday) -> working intervals that day, none = off
    default_weekly_hours: dict[int, list[WorkIntervalSchema]] | None = None
    default_external_lead_days: int | None = Field(default=None, ge=0)
    response_time_days: int | None = Field(default=None, ge=0)
    external_safety_margin_days: int | None = Field(default=None, ge=0)
    require_qa: bool | None = None
    frozen_window_hours: int | None = Field(default=None, ge=0, le=MAX_FROZEN_WINDOW_HOURS)
    default_inspection_method_id: int | None = None
    require_source_item_approval: bool | None = None
    assign_approved_material_to_item: bool | None = None
    overwrite_item_material_on_approval: bool | None = None
    external_first_step_needs_no_material: bool | None = None


class AdminProductionSettingsResponse(EntityResponse):
    production_order_number_format: str
    default_weekly_hours: dict[int, list[WorkIntervalSchema]]
    default_external_lead_days: int
    response_time_days: int
    external_safety_margin_days: int
    require_qa: bool
    frozen_window_hours: int
    default_inspection_method_id: int | None = None
    require_source_item_approval: bool
    assign_approved_material_to_item: bool
    overwrite_item_material_on_approval: bool
    external_first_step_needs_no_material: bool
    example: str
