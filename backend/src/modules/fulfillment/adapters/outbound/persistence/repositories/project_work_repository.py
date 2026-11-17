"""
Planning & fulfillment's side of the project work port: counts the work
still open on a project and rolls up its orders, for the project use cases
of Workspace, which never read these tables themselves.
"""

from typing import Any

from sqlalchemy import Select
from sqlalchemy import distinct
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.adapters.outbound.persistence.models.bought_item_demand_item_model import (
    BoughtItemDemandItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.lot_position_model import (
    LotPositionOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.made_item_demand_item_model import (
    MadeItemDemandItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model import (
    OrderItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model import (
    ProductionLotOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_model import (
    ProductionOrderOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.quote_request_model import (
    QuoteRequestLineOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.quote_request_model import (
    QuoteRequestOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.source_item_demand_item_model import (
    SourceItemDemandItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository import (
    SqlAlchemyOrderRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.quote_request_repository import (
    open_line_condition,
)
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.quote_request_status import QuoteRequestStatus
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.workspace.api import IProjectWork
from src.modules.workspace.api import ProjectSummaryRow
from src.modules.workspace.domain.value_objects.project_live_work import ProjectLiveWork

# Statuses in which a lot, production order, order line or demand is
# finished and no longer counts as a project's live work.
_FINISHED_LOT_STATUSES = (
    LotStatus.COMPLETED.value,
    LotStatus.CANCELED.value,
    LotStatus.SCRAPPED.value,
)
_FINISHED_PRODUCTION_ORDER_STATUSES = (
    ProductionOrderStatus.COMPLETED.value,
    ProductionOrderStatus.CANCELED.value,
)
_FINISHED_ORDER_ITEM_STATUSES = (OrderItemStatus.DELIVERED.value, OrderItemStatus.CANCELED.value)
_FINISHED_BOUGHT_DEMAND_STATUSES = (
    BoughtItemDemandStatus.FULFILLED.value,
    BoughtItemDemandStatus.CANCELED.value,
)
_FINISHED_MADE_DEMAND_STATUSES = (
    MadeItemDemandStatus.FULFILLED.value,
    MadeItemDemandStatus.CANCELED.value,
)
_FINISHED_SOURCE_DEMAND_STATUSES = (
    SourceItemDemandStatus.FULFILLED.value,
    SourceItemDemandStatus.CANCELED.value,
)

# Quote requests a supplier may still be asked or awarded on.
_OPEN_QUOTE_REQUEST_STATUSES = (QuoteRequestStatus.DRAFT.value, QuoteRequestStatus.SENT.value)


def _count_by_project(
    model: Any, project_ids: list[int], finished: tuple[str, ...]
) -> Select[tuple[Any, int]]:
    """The rows of `model` per project that are not in a finished status."""
    return (
        select(model.project_id, func.count(model.id))
        .where(model.project_id.in_(project_ids), model.status.not_in(finished))
        .group_by(model.project_id)
    )


class SqlAlchemyProjectWork(IProjectWork):
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._orders = SqlAlchemyOrderRepository(db)

    async def get_live_work(self, project_id: int) -> ProjectLiveWork:
        return (await self.get_live_work_by_ids([project_id]))[project_id]

    async def get_live_work_by_ids(self, project_ids: list[int]) -> dict[int, ProjectLiveWork]:
        """Counts the unfinished work of every listed project, one grouped
        statement per kind however many projects are listed. A production
        order belongs to the project of its position's lot; a quote request
        counts once per project it has an open line for, a line whose award
        was voided included, since it is open again."""
        ids = sorted(set(project_ids))
        if not ids:
            return {}
        lot_project = ProductionLotOrmModel.project_id
        line_project = QuoteRequestLineOrmModel.project_id
        statements: dict[str, Select[tuple[Any, int]]] = {
            "lots": select(lot_project, func.count(ProductionLotOrmModel.id))
            .where(
                lot_project.in_(ids),
                ProductionLotOrmModel.status.not_in(_FINISHED_LOT_STATUSES),
            )
            .group_by(lot_project),
            "production_orders": select(lot_project, func.count(ProductionOrderOrmModel.id))
            .join(
                LotPositionOrmModel,
                LotPositionOrmModel.id == ProductionOrderOrmModel.lot_position_id,
            )
            .join(ProductionLotOrmModel, ProductionLotOrmModel.id == LotPositionOrmModel.lot_id)
            .where(
                lot_project.in_(ids),
                ProductionOrderOrmModel.status.not_in(_FINISHED_PRODUCTION_ORDER_STATUSES),
            )
            .group_by(lot_project),
            "order_lines": _count_by_project(OrderItemOrmModel, ids, _FINISHED_ORDER_ITEM_STATUSES),
            "bought_demands": _count_by_project(
                BoughtItemDemandItemOrmModel, ids, _FINISHED_BOUGHT_DEMAND_STATUSES
            ),
            "made_demands": _count_by_project(
                MadeItemDemandItemOrmModel, ids, _FINISHED_MADE_DEMAND_STATUSES
            ),
            "source_demands": _count_by_project(
                SourceItemDemandItemOrmModel, ids, _FINISHED_SOURCE_DEMAND_STATUSES
            ),
            "quote_requests": select(
                line_project, func.count(distinct(QuoteRequestLineOrmModel.quote_request_id))
            )
            .join(
                QuoteRequestOrmModel,
                QuoteRequestOrmModel.id == QuoteRequestLineOrmModel.quote_request_id,
            )
            .where(
                line_project.in_(ids),
                QuoteRequestOrmModel.status.in_(_OPEN_QUOTE_REQUEST_STATUSES),
                open_line_condition(),
            )
            .group_by(line_project),
        }
        counts: dict[int, dict[str, int]] = {project_id: {} for project_id in ids}
        for kind, stmt in statements.items():
            for project_id, count in (await self._db.execute(stmt)).tuples():
                if project_id is not None:
                    counts[project_id][kind] = count
        return {project_id: ProjectLiveWork(**counts[project_id]) for project_id in ids}

    async def get_summary(self, project_id: int) -> ProjectSummaryRow:
        return await self._orders.get_project_summary(project_id)
