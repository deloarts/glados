"""
GetDashboardSummary's spend window and day buckets in the tenant's timezone,
and GetTodoSources reading every page of its filtered lists.
"""

from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
from typing import Any
from typing import cast
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from src.modules.fulfillment.application.dto.bought_item_demand_dto import DemandItemResult
from src.modules.fulfillment.application.dto.made_item_demand_dto import MadeItemDemandItemResult
from src.modules.fulfillment.application.dto.order_dto import OrderResult
from src.modules.fulfillment.application.dto.production_lot_dto import LotSummaryResult
from src.modules.fulfillment.application.dto.source_item_demand_dto import SourceItemDemandResult
from src.modules.fulfillment.application.use_cases.dashboard.get_dashboard_summary import (
    SPEND_WINDOW_DAYS,
)
from src.modules.fulfillment.application.use_cases.dashboard.get_dashboard_summary import (
    GetDashboardSummary,
)
from src.modules.fulfillment.application.use_cases.todo.get_todo_sources import TODO_HORIZON_DAYS
from src.modules.fulfillment.application.use_cases.todo.get_todo_sources import GetTodoSources
from src.modules.fulfillment.domain.services.extra_cost_rules import PricedLine
from src.modules.fulfillment.ports.outbound.repositories.order_repository import OrderSpendFacts
from src.modules.platform.const import MAX_PAGE_SIZE

VIENNA = ZoneInfo("Europe/Vienna")
TODAY = date(2026, 11, 4)


class _Counts:
    def __init__(self, counts: dict[str, int]) -> None:
        self._counts = counts

    async def count_by_status(self) -> dict[str, int]:
        return self._counts


class _Orders:
    def __init__(self, facts: list[OrderSpendFacts]) -> None:
        self.facts = facts
        self.window: tuple[datetime, datetime] | None = None

    async def get_spend_facts(
        self, ordered_from: datetime, ordered_before: datetime
    ) -> list[OrderSpendFacts]:
        self.window = (ordered_from, ordered_before)
        return [f for f in self.facts if ordered_from <= f.ordered_date < ordered_before]


def _summary(orders: _Orders) -> GetDashboardSummary:
    return GetDashboardSummary(
        lot_repo=cast(Any, _Counts({"planned": 2, "draft": 1})),
        bought_demand_repo=cast(Any, _Counts({"open": 3})),
        made_demand_repo=cast(Any, _Counts({})),
        source_demand_repo=cast(Any, _Counts({"canceled": 1})),
        order_repo=cast(Any, orders),
    )


async def test_the_spend_window_is_thirty_tenant_days_ending_today() -> None:
    orders = _Orders([])

    result = await _summary(orders).execute(TODAY, VIENNA)

    window_from = TODAY - timedelta(days=SPEND_WINDOW_DAYS - 1)
    # Midnight in Vienna, an hour before midnight UTC in winter.
    assert orders.window == (
        datetime(2026, 10, 5, 22, 0, tzinfo=UTC),
        datetime(2026, 11, 4, 23, 0, tzinfo=UTC),
    )
    assert result.spend.window_from == window_from
    assert result.spend.window_to == TODAY
    assert [d.day for d in result.spend.days] == [
        window_from + timedelta(days=i) for i in range(SPEND_WINDOW_DAYS)
    ]
    assert result.spend.order_count == 0
    assert result.spend.net_total == 0


async def test_an_order_counts_on_its_day_in_the_tenants_timezone() -> None:
    # 23:30 UTC on 2 November is 00:30 on 3 November in Vienna.
    late_evening = OrderSpendFacts(
        ordered_date=datetime(2026, 11, 2, 23, 30, tzinfo=UTC),
        lines=[
            PricedLine(price=1000, quantity=2.0),
            PricedLine(price=500, quantity=1.0, canceled=True),
            PricedLine(price=None, quantity=4.0),
        ],
        extra_costs=[("shipping", 300), ("discount", 100)],
    )
    unpriced = OrderSpendFacts(ordered_date=datetime(2026, 11, 3, 9, 0, tzinfo=UTC))
    orders = _Orders([late_evening, unpriced])

    result = await _summary(orders).execute(TODAY, VIENNA)

    by_day = {d.day: d.net_total for d in result.spend.days}
    assert by_day[date(2026, 11, 3)] == 2000 + 300 - 100
    assert by_day[date(2026, 11, 2)] == 0
    assert result.spend.order_count == 2
    assert result.spend.net_total == 2200


async def test_the_status_counts_are_listed_by_status() -> None:
    result = await _summary(_Orders([])).execute(TODAY, VIENNA)

    assert [(c.status, c.count) for c in result.lots] == [("draft", 1), ("planned", 2)]
    assert [(c.status, c.count) for c in result.bought_demands] == [("open", 3)]
    assert result.made_demands == []
    assert [(c.status, c.count) for c in result.source_demands] == [("canceled", 1)]


class _Page:
    def __init__(self, total: int, items: list[Any]) -> None:
        self.total = total
        self.items = items


class _PagedList:
    """A list use case over `total` rows of `result`, built without
    validation, that records each filter it got."""

    def __init__(self, result: type[BaseModel], total: int, *, as_tuple: bool = False) -> None:
        self._rows = [result.model_construct(id=i) for i in range(total)]
        self._as_tuple = as_tuple
        self.filters: list[Any] = []

    def _page(self, filters: Any) -> Any:
        self.filters.append(filters)
        items = self._rows[filters.skip : filters.skip + filters.limit]
        if self._as_tuple:
            return len(self._rows), items
        return _Page(len(self._rows), items)

    async def get_many(self, filters: Any) -> Any:
        return self._page(filters)

    async def execute(self, filters: Any) -> Any:
        return self._page(filters)


def _todo(orders: _PagedList, lots: _PagedList) -> GetTodoSources:
    return GetTodoSources(
        orders=cast(Any, orders),
        bought_demands=cast(Any, _PagedList(DemandItemResult, 0)),
        made_demands=cast(Any, _PagedList(MadeItemDemandItemResult, 1)),
        source_demands=cast(Any, _PagedList(SourceItemDemandResult, 0)),
        lots=cast(Any, lots),
    )


async def test_the_todo_sources_read_every_page_with_the_horizon_filter() -> None:
    orders = _PagedList(OrderResult, MAX_PAGE_SIZE + 3)
    lots = _PagedList(LotSummaryResult, 2, as_tuple=True)

    result = await _todo(orders, lots).execute(TODAY, include_lots=True)

    horizon = TODAY + timedelta(days=TODO_HORIZON_DAYS)
    assert result.horizon == horizon
    assert len(result.orders) == MAX_PAGE_SIZE + 3
    assert [f.skip for f in orders.filters] == [0, MAX_PAGE_SIZE]
    assert {f.todo_horizon for f in orders.filters} == {horizon}
    assert len(result.lots) == 2


async def test_the_todo_sources_skip_the_lots_unless_asked() -> None:
    lots = _PagedList(LotSummaryResult, 2, as_tuple=True)

    result = await _todo(_PagedList(OrderResult, 0), lots).execute(TODAY, include_lots=False)

    assert result.lots == []
    assert lots.filters == []
