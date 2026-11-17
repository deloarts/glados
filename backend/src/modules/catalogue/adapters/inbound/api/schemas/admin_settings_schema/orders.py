"""
HTTP request and response schemas for the order and bought item settings.
"""

from pydantic import BaseModel

from src.modules.catalogue.adapters.inbound.api.schemas.delivery_tolerance_schema import (
    TolerancePercent,
)
from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse


class UpdateOrderSettingsRequest(BaseModel):
    order_number_format: str | None = None
    part_number_format: str | None = None
    part_number_auto: bool | None = None
    part_number_editable: bool | None = None
    web_creation_allowed: bool | None = None
    pdm_part_number_pattern: str | None = None
    over_delivery_tolerance_percent: TolerancePercent | None = None
    under_delivery_tolerance_percent: TolerancePercent | None = None
    quote_request_number_format: str | None = None


class AdminOrderSettingsResponse(EntityResponse):
    order_number_format: str
    example: str
    part_number_format: str
    part_number_example: str
    part_number_auto: bool
    part_number_editable: bool
    web_creation_allowed: bool
    pdm_part_number_pattern: str
    over_delivery_tolerance_percent: float
    under_delivery_tolerance_percent: float
    quote_request_number_format: str
    quote_request_number_example: str
