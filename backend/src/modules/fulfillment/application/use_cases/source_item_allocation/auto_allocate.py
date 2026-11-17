"""
The automatic allocation of a source item demand, through the one the
demand families share (_demand_family/auto_allocate.py). The demand draws on
the open order lines for the catalogue item it is sourced from, a bought
item or a source item, and the machine schedules are recomputed once the
run is committed.
"""

from src.modules.fulfillment.application.dto.source_item_allocation_dto import (
    AutoAllocateSourceItemDemandCommand,
)
from src.modules.fulfillment.application.dto.source_item_allocation_dto import (
    AutoAllocateSourceItemDemandResult,
)
from src.modules.fulfillment.application.services.allocation_fill import LineFillRepos
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.use_cases._demand_family.auto_allocate import (
    AutoAllocateOnOrderLines,
)
from src.modules.fulfillment.application.use_cases.production_schedule.recompute_machine_schedule import (
    RecomputeMachineSchedule,
)
from src.modules.fulfillment.application.use_cases.source_item_demand._spec import SPEC
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.source_item_allocation import (
    SourceItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.source_item_demand_item import SourceItemDemandItem
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemDemandRepository,
)
from src.modules.platform.application.services.schedule_recompute_port import (
    recompute_schedule_after_commit,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.ports.outbound.workspace_queries import IProjectQueries


class AutoAllocateSourceItemDemand(
    AutoAllocateOnOrderLines[
        SourceItemDemandItem,
        SourceItemDemandAllocation,
        AutoAllocateSourceItemDemandCommand,
        AutoAllocateSourceItemDemandResult,
    ]
):
    _spec = SPEC
    _result = AutoAllocateSourceItemDemandResult

    def __init__(
        self,
        demand_repo: ISourceItemDemandRepository,
        order_item_repo: IOrderItemRepository,
        allocation_repo: ISourceItemAllocationRepository,
        recompute_schedule: RecomputeMachineSchedule | None = None,
        *,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
        project_repo: IProjectQueries,
        fill_repos: LineFillRepos,
    ) -> None:
        super().__init__(
            demand_repo,
            order_item_repo,
            allocation_repo,
            uow=uow,
            reconciler=reconciler,
            project_repo=project_repo,
            fill_repos=fill_repos,
        )
        self._recompute = recompute_schedule

    async def _find_lines(self, demand: SourceItemDemandItem) -> list[OrderItem]:
        if demand.bought_item_id is not None:
            return await self._order_items.get_by_bought_item_id(demand.bought_item_id)
        assert demand.source_item_id is not None
        return await self._order_items.get_by_source_item_id(demand.source_item_id)

    def _line_matches(self, demand: SourceItemDemandItem, line: OrderItem) -> bool:
        if demand.bought_item_id is not None:
            return line.bought_item_id == demand.bought_item_id
        return line.source_item_id == demand.source_item_id

    def _new_allocation(
        self, demand_id: int, order_item_id: int, quantity: float
    ) -> SourceItemDemandAllocation:
        return SourceItemDemandAllocation(
            demand_item_id=demand_id, order_item_id=order_item_id, quantity=quantity
        )

    async def _after_commit(self, action: str) -> None:
        await recompute_schedule_after_commit(self._recompute, after=action)
