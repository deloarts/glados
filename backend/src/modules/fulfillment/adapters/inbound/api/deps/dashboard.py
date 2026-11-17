"""Use-case factories for the dashboard summary and the Todo sources, the two
reads that stand in for loading whole lists in the browser.
"""

from fastapi import Depends

from src.modules.fulfillment.adapters.inbound.api.deps.demands import get_demand_items_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.demands import get_made_item_demands_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.demands import (
    get_source_item_demands_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.lots import get_lots_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.orders import get_orders_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_demand_item_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_made_item_demand_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_order_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_production_lot_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_source_item_demand_repo,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.get_demand_items import (
    GetDemandItems as GetBoughtDemandItems,
)
from src.modules.fulfillment.application.use_cases.dashboard.get_dashboard_summary import (
    GetDashboardSummary,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.get_demand_items import (
    GetDemandItems as GetMadeDemandItems,
)
from src.modules.fulfillment.application.use_cases.order.get_order import GetOrders
from src.modules.fulfillment.application.use_cases.production_lot.get_lot import GetLots
from src.modules.fulfillment.application.use_cases.source_item_demand.get_source_item_demand import (
    GetSourceItemDemands,
)
from src.modules.fulfillment.application.use_cases.todo.get_todo_sources import GetTodoSources
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemDemandItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    IMadeItemDemandItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import IOrderRepository
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemDemandRepository,
)
from src.modules.workspace.adapters.inbound.api.deps.repositories import get_meeting_card_repo
from src.modules.workspace.ports.outbound.workspace_queries import IMeetingTodoQueries


def get_dashboard_summary_use_case(
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    bought_demand_repo: IBoughtItemDemandItemRepository = Depends(get_demand_item_repo),
    made_demand_repo: IMadeItemDemandItemRepository = Depends(get_made_item_demand_repo),
    source_demand_repo: ISourceItemDemandRepository = Depends(get_source_item_demand_repo),
    order_repo: IOrderRepository = Depends(get_order_repo),
) -> GetDashboardSummary:
    return GetDashboardSummary(
        lot_repo=lot_repo,
        bought_demand_repo=bought_demand_repo,
        made_demand_repo=made_demand_repo,
        source_demand_repo=source_demand_repo,
        order_repo=order_repo,
    )


def get_todo_sources_use_case(
    orders: GetOrders = Depends(get_orders_use_case),
    bought_demands: GetBoughtDemandItems = Depends(get_demand_items_use_case),
    made_demands: GetMadeDemandItems = Depends(get_made_item_demands_use_case),
    source_demands: GetSourceItemDemands = Depends(get_source_item_demands_use_case),
    lots: GetLots = Depends(get_lots_use_case),
    meeting_todos: IMeetingTodoQueries = Depends(get_meeting_card_repo),
) -> GetTodoSources:
    return GetTodoSources(
        orders=orders,
        bought_demands=bought_demands,
        made_demands=made_demands,
        source_demands=source_demands,
        lots=lots,
        meeting_todos=meeting_todos,
    )
