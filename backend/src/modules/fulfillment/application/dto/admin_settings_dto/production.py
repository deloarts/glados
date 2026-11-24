"""
Commands and results for the production and scheduling settings.
"""

from pydantic import BaseModel
from pydantic import Field

from src.modules.fulfillment.application.dto.machine_calendar_dto import WorkIntervalDto
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    MAX_FROZEN_WINDOW_HOURS,
)
from src.modules.platform.application.dto.base import ResultBase


class UpdateProductionSettingsCommand(BaseModel):
    production_order_number_format: str | None = None
    # weekday (0=Monday..6=Sunday) -> working intervals that day, none = off
    default_weekly_hours: dict[int, list[WorkIntervalDto]] | None = None
    default_external_lead_days: int | None = Field(default=None, ge=0)
    response_time_days: int | None = Field(default=None, ge=0)
    external_safety_margin_days: int | None = Field(default=None, ge=0)
    require_qa: bool | None = None
    frozen_window_hours: int | None = Field(default=None, ge=0, le=MAX_FROZEN_WINDOW_HOURS)
    # None = leave unchanged, like every field above. There is no supported
    # way to clear an already-set default back to null through this
    # command; harmless, since it's only validated while require_qa=True.
    default_inspection_method_id: int | None = None
    # None = leave unchanged. Flipping this triggers UpdateProductionSettings'
    # off->on/on->off lot backfill (see that use case).
    require_source_item_approval: bool | None = None
    # None = leave unchanged, like every field above.
    assign_approved_material_to_item: bool | None = None
    # None = leave unchanged, like every field above.
    overwrite_item_material_on_approval: bool | None = None


class AdminProductionSettingsResult(ResultBase):
    production_order_number_format: str
    default_weekly_hours: dict[int, list[WorkIntervalDto]]
    default_external_lead_days: int
    response_time_days: int
    external_safety_margin_days: int
    require_qa: bool
    frozen_window_hours: int
    default_inspection_method_id: int | None = None
    require_source_item_approval: bool
    assign_approved_material_to_item: bool
    overwrite_item_material_on_approval: bool
    example: str
