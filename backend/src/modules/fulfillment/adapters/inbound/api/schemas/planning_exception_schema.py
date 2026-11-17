"""
HTTP response schema of the planner's exception list (GET
/production-exceptions), mirroring PlanningExceptionResult.
"""

from datetime import date
from datetime import datetime
from typing import Literal

from pydantic import ConfigDict

from src.modules.fulfillment.domain.value_objects.planning_exception_kind import (
    PlanningExceptionKind,
)
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel


class PlanningExceptionResponse(ResponseModel):
    kind: PlanningExceptionKind
    family: Literal["bought", "source", "made"] | None = None
    demand_id: int | None = None
    lot_id: int | None = None
    lot_number: str | None = None
    order_id: int | None = None
    order_number: str | None = None
    line_position: int | None = None
    item_kind: Literal["made", "bought", "source"] | None = None
    item_id: int | None = None
    item_number: str = ""
    item_revision: str = ""
    item_name: str = ""
    item_label: str = ""
    project_id: int | None = None
    project_number: str = ""
    project_customer: str = ""
    quantity_short: float | None = None
    unit: str | None = None
    unallocated: float | None = None
    undated: bool = False
    target_date: date | None = None
    planned_end: datetime | None = None
    since: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
