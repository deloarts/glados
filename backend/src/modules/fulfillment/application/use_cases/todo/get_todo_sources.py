"""
The rows the Todo page builds its tasks from: the orders, demands and lots
that can give a task, read through the same list use cases as their tables
so every row has the shape the page already knows, and the open todos of
valid meetings that the user owns, read through Workspace's query port.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from datetime import date
from datetime import timedelta

from src.modules.fulfillment.application.dto.bought_item_demand_dto import DemandItemResult
from src.modules.fulfillment.application.dto.made_item_demand_dto import MadeItemDemandItemResult
from src.modules.fulfillment.application.dto.order_dto import OrderResult
from src.modules.fulfillment.application.dto.production_lot_dto import LotSummaryResult
from src.modules.fulfillment.application.dto.source_item_demand_dto import SourceItemDemandResult
from src.modules.fulfillment.application.dto.todo_dto import MeetingTodoSourceResult
from src.modules.fulfillment.application.dto.todo_dto import TodoSourcesResult
from src.modules.fulfillment.application.use_cases.bought_item_demand.get_demand_items import (
    GetDemandItems as GetBoughtDemandItems,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.get_demand_items import (
    GetDemandItems as GetMadeDemandItems,
)
from src.modules.fulfillment.application.use_cases.order.get_order import GetOrders
from src.modules.fulfillment.application.use_cases.production_lot.get_lot import GetLots
from src.modules.fulfillment.application.use_cases.source_item_demand.get_source_item_demand import (
    GetSourceItemDemands,
)
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    DemandItemFilterDto,
)
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    MadeItemDemandFilterDto,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import OrderFilterDto
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    LotFilterDto,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    SourceItemDemandFilterDto,
)
from src.modules.platform.const import MAX_PAGE_SIZE
from src.modules.workspace.ports.outbound.workspace_queries import IMeetingTodoQueries

# The page lists tasks due within a week of today. One more day keeps the
# rows of the day that comes into that week at midnight, while the page
# stays open and rebuilds its buckets without reading again.
TODO_HORIZON_DAYS = 8


async def _read_all[T](read_page: Callable[[int, int], Awaitable[tuple[int, list[T]]]]) -> list[T]:
    """Every row of a filtered list, read in pages of the largest size the
    list accepts. The filters keep this to the open work, which normally
    fits in one page."""
    rows: list[T] = []
    while True:
        total, page = await read_page(len(rows), MAX_PAGE_SIZE)
        rows.extend(page)
        if len(page) < MAX_PAGE_SIZE or len(rows) >= total:
            return rows


class GetTodoSources:
    def __init__(
        self,
        orders: GetOrders,
        bought_demands: GetBoughtDemandItems,
        made_demands: GetMadeDemandItems,
        source_demands: GetSourceItemDemands,
        lots: GetLots,
        meeting_todos: IMeetingTodoQueries | None = None,
    ) -> None:
        self._meeting_todos = meeting_todos
        self._orders = orders
        self._bought_demands = bought_demands
        self._made_demands = made_demands
        self._source_demands = source_demands
        self._lots = lots

    async def execute(
        self, today: date, *, include_lots: bool, user_id: int | None = None
    ) -> TodoSourcesResult:
        """`today` is the current day in the tenant's timezone. Lots are
        read only when `include_lots` is set, since their tasks belong to
        Production Planning. The meeting todos are those of `user_id`, the
        signed-in user."""
        horizon = today + timedelta(days=TODO_HORIZON_DAYS)

        async def orders(skip: int, limit: int) -> tuple[int, list[OrderResult]]:
            page = await self._orders.get_many(
                OrderFilterDto(skip=skip, limit=limit, todo_horizon=horizon)
            )
            return page.total, page.items

        async def bought(skip: int, limit: int) -> tuple[int, list[DemandItemResult]]:
            page = await self._bought_demands.execute(
                DemandItemFilterDto(skip=skip, limit=limit, todo_horizon=horizon)
            )
            return page.total, page.items

        async def made(skip: int, limit: int) -> tuple[int, list[MadeItemDemandItemResult]]:
            page = await self._made_demands.execute(
                MadeItemDemandFilterDto(skip=skip, limit=limit, todo_horizon=horizon)
            )
            return page.total, page.items

        async def source(skip: int, limit: int) -> tuple[int, list[SourceItemDemandResult]]:
            page = await self._source_demands.execute(
                SourceItemDemandFilterDto(skip=skip, limit=limit, todo_horizon=horizon)
            )
            return page.total, page.items

        async def lots(skip: int, limit: int) -> tuple[int, list[LotSummaryResult]]:
            return await self._lots.execute(
                LotFilterDto(skip=skip, limit=limit, todo_horizon=horizon)
            )

        return TodoSourcesResult(
            horizon=horizon,
            orders=await _read_all(orders),
            bought_demands=await _read_all(bought),
            made_demands=await _read_all(made),
            source_demands=await _read_all(source),
            lots=await _read_all(lots) if include_lots else [],
            meeting_todos=await self._meeting_todo_rows(user_id, horizon),
        )

    async def _meeting_todo_rows(
        self, user_id: int | None, horizon: date
    ) -> list[MeetingTodoSourceResult]:
        if self._meeting_todos is None or user_id is None:
            return []
        rows = await self._meeting_todos.list_open_todos_of_user(user_id, due_on_or_before=horizon)
        return [
            MeetingTodoSourceResult(
                todo_id=row.todo_id,
                title=row.title,
                due_date=row.due_date,
                meeting_id=row.meeting_id,
                meeting_number=row.meeting_number,
                meeting_name=row.meeting_name,
                owner_kind=row.owner_kind,
                owner_id=row.owner_id,
                card_id=row.card_id,
                card_scope=row.card_scope,
            )
            for row in rows
        ]
