"""
The dashboard's status counts and recent spend, computed on the server so
the page reads one small answer instead of every lot, demand and order.
"""

from collections import defaultdict
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import time
from datetime import timedelta
from datetime import tzinfo

from src.modules.fulfillment.application.dto.dashboard_dto import DashboardSummaryResult
from src.modules.fulfillment.application.dto.dashboard_dto import SpendDayResult
from src.modules.fulfillment.application.dto.dashboard_dto import SpendSummaryResult
from src.modules.fulfillment.application.dto.dashboard_dto import StatusCountResult
from src.modules.fulfillment.domain.services.extra_cost_rules import extra_costs_total
from src.modules.fulfillment.domain.services.extra_cost_rules import lines_total
from src.modules.fulfillment.domain.services.extra_cost_rules import net_total
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemDemandItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    IMadeItemDemandItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import IOrderRepository
from src.modules.fulfillment.ports.outbound.repositories.order_repository import OrderSpendFacts
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemDemandRepository,
)

# A rolling window that includes today. A calendar month would reset the
# spend chart to a single point on the first of every month.
SPEND_WINDOW_DAYS = 30


def _day_start_utc(day: date, zone: tzinfo) -> datetime:
    return datetime.combine(day, time.min, tzinfo=zone).astimezone(UTC)


def _counts(by_status: dict[str, int]) -> list[StatusCountResult]:
    return [
        StatusCountResult(status=status, count=count) for status, count in sorted(by_status.items())
    ]


def _order_net_total(facts: OrderSpendFacts) -> int:
    """The order's net total in cents as its list row shows it, 0 when it
    has neither a priced line nor an extra cost."""
    total = net_total(
        lines_total(facts.lines),
        extra_costs_total(facts.extra_costs),
        has_costs=bool(facts.extra_costs),
    )
    return total or 0


class GetDashboardSummary:
    def __init__(
        self,
        lot_repo: IProductionLotRepository,
        bought_demand_repo: IBoughtItemDemandItemRepository,
        made_demand_repo: IMadeItemDemandItemRepository,
        source_demand_repo: ISourceItemDemandRepository,
        order_repo: IOrderRepository,
    ) -> None:
        self._lots = lot_repo
        self._bought_demands = bought_demand_repo
        self._made_demands = made_demand_repo
        self._source_demands = source_demand_repo
        self._orders = order_repo

    async def execute(self, today: date, zone: tzinfo) -> DashboardSummaryResult:
        """`today` is the current day in `zone`, the tenant's timezone, which
        also decides the day each order counts on."""
        return DashboardSummaryResult(
            lots=_counts(await self._lots.count_by_status()),
            bought_demands=_counts(await self._bought_demands.count_by_status()),
            made_demands=_counts(await self._made_demands.count_by_status()),
            source_demands=_counts(await self._source_demands.count_by_status()),
            spend=await self._spend(today, zone),
        )

    async def _spend(self, today: date, zone: tzinfo) -> SpendSummaryResult:
        window_from = today - timedelta(days=SPEND_WINDOW_DAYS - 1)
        orders = await self._orders.get_spend_facts(
            _day_start_utc(window_from, zone), _day_start_utc(today + timedelta(days=1), zone)
        )
        by_day: dict[date, int] = defaultdict(int)
        for facts in orders:
            by_day[facts.ordered_date.astimezone(zone).date()] += _order_net_total(facts)
        days = [
            SpendDayResult(day=day, net_total=by_day.get(day, 0))
            for day in (window_from + timedelta(days=i) for i in range(SPEND_WINDOW_DAYS))
        ]
        return SpendSummaryResult(
            window_from=window_from,
            window_to=today,
            order_count=len(orders),
            net_total=sum(day.net_total for day in days),
            days=days,
        )
