"""
Commands and results for the order and bought item settings.
"""

from pydantic import BaseModel

from src.modules.platform.application.dto.base import ResultBase


class UpdateOrderSettingsCommand(BaseModel):
    order_number_format: str | None = None
    part_number_format: str | None = None
    part_number_auto: bool | None = None
    part_number_editable: bool | None = None
    web_creation_allowed: bool | None = None
    pdm_part_number_pattern: str | None = None
    over_delivery_tolerance_percent: float | None = None
    under_delivery_tolerance_percent: float | None = None
    quote_request_number_format: str | None = None


class AdminOrderSettingsResult(ResultBase):
    order_number_format: str
    example: str  # rendered preview of the current format, e.g. "ORD-2026-0001"
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
