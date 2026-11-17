"""
HTTP request and response schemas for the tenant holiday calendar.
"""

from datetime import date
from datetime import datetime

from pydantic import BaseModel
from pydantic import Field

from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.adapters.inbound.api.schemas.user_schema import PublicUserResponse
from src.modules.platform.domain.value_objects.holiday_category import HolidayCategory


class SaveTenantHolidayRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    category: HolidayCategory
    start_date: date
    # Inclusive; the start date again for a single day.
    end_date: date


class TenantHolidayResponse(EntityResponse):
    created: datetime
    changed: datetime | None
    name: str
    category: HolidayCategory
    start_date: date
    end_date: date
    creator_id: int
    changed_by_id: int | None
    changed_by: PublicUserResponse | None
