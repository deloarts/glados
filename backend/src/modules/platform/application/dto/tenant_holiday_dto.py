"""
Commands and results for the tenant holiday calendar.
"""

from datetime import date
from datetime import datetime

from pydantic import BaseModel
from pydantic import Field

from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.application.dto.user_dto import PublicUserResult
from src.modules.platform.domain.value_objects.holiday_category import HolidayCategory


class SaveTenantHolidayCommand(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    category: HolidayCategory
    start_date: date
    end_date: date


class TenantHolidayResult(ResultBase):
    created: datetime
    changed: datetime | None
    name: str
    category: HolidayCategory
    start_date: date
    end_date: date
    creator_id: int
    changed_by_id: int | None
    changed_by: PublicUserResult | None
