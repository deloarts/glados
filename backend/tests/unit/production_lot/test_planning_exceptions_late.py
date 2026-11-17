"""
The planner's LATE exception compares days of the tenant's timezone: today,
and the day the lot's latest planned end falls on, against the target date.
Around Vienna midnight the two disagree with UTC.
"""

from datetime import UTC
from datetime import date
from datetime import datetime

import pytest

from src.modules.fulfillment.application.services.scheduling_context import SchedulingRepos
from src.modules.fulfillment.application.use_cases.production_lot import get_planning_exceptions
from src.modules.fulfillment.application.use_cases.production_lot.get_planning_exceptions import (
    GetPlanningExceptions,
)
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.value_objects.planning_exception_kind import (
    PlanningExceptionKind,
)
from tests.unit._tenant_settings import TenantSettings
from tests.unit.production_order._helpers import make_lot
from tests.unit.production_order._helpers import make_order
from tests.unit.production_order._helpers import make_position

TARGET = date(2026, 7, 27)


class _Orders:
    def __init__(self, orders: list[ProductionOrder]) -> None:
        self._orders = orders

    async def get_by_lot_position_ids(self, ids: list[int]) -> list[ProductionOrder]:
        return [o for o in self._orders if o.lot_position_id in ids]


def _use_case(orders: list[ProductionOrder], timezone: str) -> GetPlanningExceptions:
    repos = SchedulingRepos(
        orders=_Orders(orders),  # type: ignore[arg-type]
        lots=None,  # type: ignore[arg-type]
        order_items=None,  # type: ignore[arg-type]
        source_item_demands=None,  # type: ignore[arg-type]
        source_item_allocations=None,  # type: ignore[arg-type]
        made_item_allocations=None,  # type: ignore[arg-type]
        made_item_demands=None,  # type: ignore[arg-type]
        settings=TenantSettings(timezone),  # type: ignore[arg-type]
    )
    return GetPlanningExceptions(repos, None, None, None)  # type: ignore[arg-type]


def _lot():
    lot = make_lot(positions=[make_position()])
    lot.required_delivery_date = TARGET
    return lot


@pytest.mark.parametrize(("timezone", "late"), [("Europe/Vienna", True), ("UTC", False)])
async def test_a_planned_end_after_vienna_midnight_overruns_the_target_date(
    monkeypatch, timezone, late
):
    """23:30 UTC on the target date is 01:30 on the next day in Vienna."""
    monkeypatch.setattr(
        get_planning_exceptions, "now_utc", lambda: datetime(2026, 7, 20, 8, 0, tzinfo=UTC)
    )
    order = make_order()
    order.planned_start = datetime(2026, 7, 27, 20, 0, tzinfo=UTC)
    order.planned_end = datetime(2026, 7, 27, 23, 30, tzinfo=UTC)

    rows = await _use_case([order], timezone)._late([_lot()])

    assert [r.kind for r in rows] == ([PlanningExceptionKind.LATE] if late else [])


@pytest.mark.parametrize(("timezone", "late"), [("Europe/Vienna", True), ("UTC", False)])
async def test_a_target_date_is_past_once_the_vienna_day_after_it_began(
    monkeypatch, timezone, late
):
    """22:30 UTC on the target date is already the next day in Vienna."""
    monkeypatch.setattr(
        get_planning_exceptions, "now_utc", lambda: datetime(2026, 7, 27, 22, 30, tzinfo=UTC)
    )

    rows = await _use_case([], timezone)._late([_lot()])

    assert [r.kind for r in rows] == ([PlanningExceptionKind.LATE] if late else [])
