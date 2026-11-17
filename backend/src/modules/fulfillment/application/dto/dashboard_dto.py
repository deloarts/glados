"""
The dashboard's numbers, counted and summed on the server so the page never
reads whole lists to compute them.
"""

from datetime import date

from pydantic import Field

from src.modules.platform.application.dto.base import ResultModel


class StatusCountResult(ResultModel):
    """How many rows of one list hold one stored status."""

    status: str
    count: int


class SpendDayResult(ResultModel):
    """The net total of the orders placed on one day in the tenant's
    timezone, in cents."""

    day: date
    net_total: int


class SpendSummaryResult(ResultModel):
    """The orders placed in the rolling window that ends today: how many,
    their net total in cents, and that total per day, oldest day first with
    every day of the window listed."""

    window_from: date
    window_to: date
    order_count: int
    net_total: int
    days: list[SpendDayResult] = Field(default_factory=list)


class DashboardSummaryResult(ResultModel):
    """Status counts over the whole lot list and the three demand lists,
    and the recent spend."""

    lots: list[StatusCountResult] = Field(default_factory=list)
    bought_demands: list[StatusCountResult] = Field(default_factory=list)
    made_demands: list[StatusCountResult] = Field(default_factory=list)
    source_demands: list[StatusCountResult] = Field(default_factory=list)
    spend: SpendSummaryResult
