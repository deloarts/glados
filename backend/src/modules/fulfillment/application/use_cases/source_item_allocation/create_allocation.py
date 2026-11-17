"""
The manual allocation writers of source item demands, through the writers
the demand families share (_demand_family/allocation_writers.py): an
allocation of a demand on one order line, created, changed and deleted, and
the demand's stock allocation, set and removed. Each write recomputes the
machine schedule once it is committed.

A demand sourced from a source item may be allocated to an order line for a
different source item when the caller declares substitute_source_item_id
(SourceItemAllocationRules.assert_material_matches). Demands sourced from a
bought item are not substitutable.
"""

from src.modules.fulfillment.application.dto.source_item_allocation_dto import (
    CreateSourceItemAllocationCommand,
)
from src.modules.fulfillment.application.dto.source_item_allocation_dto import (
    SourceItemAllocationResult,
)
from src.modules.fulfillment.application.services.allocation_fill import LineFillRepos
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.use_cases._demand_family import (
    allocation_writers as shared,
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
from src.modules.fulfillment.domain.services.allocation_coverage import RecordedSubstitution
from src.modules.fulfillment.domain.services.allocation_coverage import recorded_substitution
from src.modules.fulfillment.domain.services.source_item_allocation_service import (
    SourceItemAllocationRules,
)
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemAllocationSource,
)
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
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


def _to_result(allocation: SourceItemDemandAllocation) -> SourceItemAllocationResult:
    return SourceItemAllocationResult(
        demand_item_id=allocation.demand_item_id,
        order_item_id=allocation.order_item_id,
        source=allocation.source,
        quantity=allocation.quantity,
        substitute_source_item_id=allocation.substitute_source_item_id,
        substitute_reason=allocation.substitute_reason,
    )


def _substitution(
    demand: SourceItemDemandItem, order_item: OrderItem, reason: str | None
) -> RecordedSubstitution:
    """The substitution the allocation records, decided by the line's
    material and not by whether the caller sent a substitute_source_item_id:
    a line for the demand's own material is stored as a plain match,
    dropping any reason sent along with it."""
    return recorded_substitution(demand.source_item_id, order_item.source_item_id, reason)


class _RecomputesSchedule:
    """Recomputes the machine schedules after the committed write, which
    every source item allocation writer does."""

    _recompute: RecomputeMachineSchedule | None

    async def _after_commit(self, action: str) -> None:
        await recompute_schedule_after_commit(self._recompute, after=action)


class CreateSourceItemAllocation(
    _RecomputesSchedule,
    shared.CreateOrderLineAllocation[
        SourceItemDemandItem,
        SourceItemDemandAllocation,
        SourceItemAllocationResult,
        CreateSourceItemAllocationCommand,
    ],
):
    _spec = SPEC

    def __init__(
        self,
        allocation_repo: ISourceItemAllocationRepository,
        demand_repo: ISourceItemDemandRepository,
        order_item_repo: IOrderItemRepository,
        recompute_schedule: RecomputeMachineSchedule | None = None,
        *,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
        fill_repos: LineFillRepos,
    ) -> None:
        super().__init__(
            allocation_repo,
            demand_repo,
            order_item_repo,
            uow=uow,
            reconciler=reconciler,
            fill_repos=fill_repos,
        )
        self._recompute = recompute_schedule

    def _result(self, allocation: SourceItemDemandAllocation) -> SourceItemAllocationResult:
        return _to_result(allocation)

    def _assert_item_matches(
        self,
        demand: SourceItemDemandItem,
        order_item: OrderItem,
        cmd: CreateSourceItemAllocationCommand,
    ) -> None:
        SourceItemAllocationRules.assert_material_matches(
            demand, order_item, cmd.substitute_source_item_id
        )

    def _new_allocation(
        self,
        demand: SourceItemDemandItem,
        order_item: OrderItem,
        cmd: CreateSourceItemAllocationCommand,
    ) -> SourceItemDemandAllocation:
        substitution = _substitution(demand, order_item, cmd.substitute_reason)
        return SourceItemDemandAllocation(
            demand_item_id=cmd.demand_item_id,
            order_item_id=cmd.order_item_id,
            quantity=cmd.quantity,
            substitute_source_item_id=substitution.item_id,
            substitute_reason=substitution.reason,
        )

    def _log_created(
        self,
        cmd: CreateSourceItemAllocationCommand,
        demand: SourceItemDemandItem,
        order_item: OrderItem,
    ) -> None:
        log.info(
            f"Allocated {cmd.quantity} units of source item demand "
            f"#{cmd.demand_item_id} to order item #{cmd.order_item_id}"
            + (
                f" as a substitution for #{demand.source_item_id}."
                if _substitution(demand, order_item, None).item_id is not None
                else "."
            )
        )


class UpdateSourceItemAllocation(
    _RecomputesSchedule,
    shared.UpdateOrderLineAllocation[
        SourceItemDemandItem, SourceItemDemandAllocation, SourceItemAllocationResult
    ],
):
    """Update the quantity of an existing allocation."""

    _spec = SPEC

    def __init__(
        self,
        allocation_repo: ISourceItemAllocationRepository,
        demand_repo: ISourceItemDemandRepository,
        order_item_repo: IOrderItemRepository,
        recompute_schedule: RecomputeMachineSchedule | None = None,
        *,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
        fill_repos: LineFillRepos,
    ) -> None:
        super().__init__(
            allocation_repo,
            demand_repo,
            order_item_repo,
            uow=uow,
            reconciler=reconciler,
            fill_repos=fill_repos,
        )
        self._recompute = recompute_schedule

    def _result(self, allocation: SourceItemDemandAllocation) -> SourceItemAllocationResult:
        return _to_result(allocation)


class DeleteSourceItemAllocation(
    _RecomputesSchedule,
    shared.DeleteOrderLineAllocation[SourceItemDemandItem, SourceItemDemandAllocation],
):
    _spec = SPEC

    def __init__(
        self,
        allocation_repo: ISourceItemAllocationRepository,
        demand_repo: ISourceItemDemandRepository,
        order_item_repo: IOrderItemRepository,
        recompute_schedule: RecomputeMachineSchedule | None = None,
        *,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
        fill_repos: LineFillRepos,
    ) -> None:
        super().__init__(
            allocation_repo,
            demand_repo,
            order_item_repo,
            uow=uow,
            reconciler=reconciler,
            fill_repos=fill_repos,
        )
        self._recompute = recompute_schedule


class UpdateSourceItemStockAllocation(
    _RecomputesSchedule,
    shared.UpdateStockAllocation[
        SourceItemDemandItem, SourceItemDemandAllocation, SourceItemAllocationResult
    ],
):
    """Manually overrides the stock allocation quantity of a demand."""

    _spec = SPEC

    def __init__(
        self,
        allocation_repo: ISourceItemAllocationRepository,
        demand_repo: ISourceItemDemandRepository,
        order_item_repo: IOrderItemRepository,
        recompute_schedule: RecomputeMachineSchedule | None = None,
        *,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
    ) -> None:
        super().__init__(allocation_repo, demand_repo, uow=uow, reconciler=reconciler)
        self._order_items = order_item_repo
        self._recompute = recompute_schedule

    def _result(self, allocation: SourceItemDemandAllocation) -> SourceItemAllocationResult:
        return _to_result(allocation)

    def _stock_allocation(self, demand_id: int, quantity: float) -> SourceItemDemandAllocation:
        return SourceItemDemandAllocation(
            demand_item_id=demand_id,
            order_item_id=None,
            quantity=quantity,
            source=SourceItemAllocationSource.STOCK,
        )


class DeleteSourceItemStockAllocation(
    _RecomputesSchedule,
    shared.DeleteStockAllocation[SourceItemDemandItem, SourceItemDemandAllocation],
):
    """Removes the stock allocation row of a demand."""

    _spec = SPEC

    def __init__(
        self,
        allocation_repo: ISourceItemAllocationRepository,
        demand_repo: ISourceItemDemandRepository,
        order_item_repo: IOrderItemRepository,
        recompute_schedule: RecomputeMachineSchedule | None = None,
        *,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
    ) -> None:
        super().__init__(allocation_repo, demand_repo, uow=uow, reconciler=reconciler)
        self._order_items = order_item_repo
        self._recompute = recompute_schedule
