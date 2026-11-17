"""
The dashboard summary: status counts over the lot list and the three demand
lists, and the recent spend.
"""

from datetime import date

from pydantic import Field

from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel


class LotStatusCountResponse(ResponseModel):
    status: LotStatus
    count: int


class BoughtDemandStatusCountResponse(ResponseModel):
    status: BoughtItemDemandStatus
    count: int


class MadeDemandStatusCountResponse(ResponseModel):
    status: MadeItemDemandStatus
    count: int


class SourceDemandStatusCountResponse(ResponseModel):
    status: SourceItemDemandStatus
    count: int


class SpendDayResponse(ResponseModel):
    """The net total in cents of the orders placed on `day`, a day in the
    tenant's timezone."""

    day: date
    net_total: int


class SpendSummaryResponse(ResponseModel):
    """The orders placed from `window_from` to `window_to`, both days
    included: their count, their net total in cents and that total per day,
    oldest first with every day of the window listed."""

    window_from: date
    window_to: date
    order_count: int
    net_total: int
    days: list[SpendDayResponse] = Field(default_factory=list)


class DashboardSummaryResponse(ResponseModel):
    """Each count is taken over the whole list, as its table shows it
    without filters. A status no row holds is left out."""

    lots: list[LotStatusCountResponse] = Field(default_factory=list)
    bought_demands: list[BoughtDemandStatusCountResponse] = Field(default_factory=list)
    made_demands: list[MadeDemandStatusCountResponse] = Field(default_factory=list)
    source_demands: list[SourceDemandStatusCountResponse] = Field(default_factory=list)
    spend: SpendSummaryResponse
