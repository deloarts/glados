"""
The manual allocation writers of bought item demands, through the writers
the demand families share (_demand_family/allocation_writers.py): an
allocation of a demand on one order line, created, changed and deleted, and
the demand's stock allocation, set and removed. A bought item demand is
covered by an order line for its own catalogue item, or by a line for
another bought item when the caller declares that substitution
(BoughtItemAllocationRules.assert_bought_item_matches). The allocation
records a substitution only when the line's item differs from the demand's
(recorded_substitution), so a plain match sent with a substitute is stored
as a plain match and a reason without a substitution is dropped.
"""

from src.modules.catalogue.domain.value_objects.bought_item_status import AllocationSource
from src.modules.fulfillment.application.dto.allocation_dto import AllocationResult
from src.modules.fulfillment.application.dto.allocation_dto import CreateAllocationCommand
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.use_cases._demand_family import (
    allocation_writers as shared,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand._demand_spec import SPEC
from src.modules.fulfillment.domain.entities.bought_item_allocation import (
    BoughtItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.bought_item_demand_item import BoughtItemDemandItem
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.services.allocation_coverage import recorded_substitution
from src.modules.fulfillment.domain.services.allocation_service import BoughtItemAllocationRules
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemDemandItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


def _to_result(allocation: BoughtItemDemandAllocation) -> AllocationResult:
    return AllocationResult(
        demand_item_id=allocation.demand_item_id,
        order_item_id=allocation.order_item_id,
        source=allocation.source,
        quantity=allocation.quantity,
        substitute_item_id=allocation.substitute_item_id,
        substitute_reason=allocation.substitute_reason,
    )


class CreateAllocation(
    shared.CreateOrderLineAllocation[
        BoughtItemDemandItem,
        BoughtItemDemandAllocation,
        AllocationResult,
        CreateAllocationCommand,
    ]
):
    _spec = SPEC

    def _result(self, allocation: BoughtItemDemandAllocation) -> AllocationResult:
        return _to_result(allocation)

    def _assert_item_matches(
        self, demand: BoughtItemDemandItem, order_item: OrderItem, cmd: CreateAllocationCommand
    ) -> None:
        BoughtItemAllocationRules.assert_bought_item_matches(
            demand, order_item, cmd.substitute_item_id
        )

    def _new_allocation(
        self, demand: BoughtItemDemandItem, order_item: OrderItem, cmd: CreateAllocationCommand
    ) -> BoughtItemDemandAllocation:
        substitution = recorded_substitution(
            demand.item_id, order_item.bought_item_id, cmd.substitute_reason
        )
        return BoughtItemDemandAllocation(
            demand_item_id=cmd.demand_item_id,
            order_item_id=cmd.order_item_id,
            quantity=cmd.quantity,
            substitute_item_id=substitution.item_id,
            substitute_reason=substitution.reason,
        )


class UpdateAllocation(
    shared.UpdateOrderLineAllocation[
        BoughtItemDemandItem, BoughtItemDemandAllocation, AllocationResult
    ]
):
    """Update the quantity of an existing allocation."""

    _spec = SPEC

    def _result(self, allocation: BoughtItemDemandAllocation) -> AllocationResult:
        return _to_result(allocation)


class DeleteAllocation(
    shared.DeleteOrderLineAllocation[BoughtItemDemandItem, BoughtItemDemandAllocation]
):
    _spec = SPEC


class UpdateStockAllocation(
    shared.UpdateStockAllocation[BoughtItemDemandItem, BoughtItemDemandAllocation, AllocationResult]
):
    """Manually overrides the stock allocation quantity of a demand."""

    _spec = SPEC

    def __init__(
        self,
        allocation_repo: IBoughtItemAllocationRepository,
        demand_repo: IBoughtItemDemandItemRepository,
        order_item_repo: IOrderItemRepository,
        *,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
    ) -> None:
        super().__init__(allocation_repo, demand_repo, uow=uow, reconciler=reconciler)
        self._order_items = order_item_repo

    def _result(self, allocation: BoughtItemDemandAllocation) -> AllocationResult:
        return _to_result(allocation)

    def _stock_allocation(self, demand_id: int, quantity: float) -> BoughtItemDemandAllocation:
        return BoughtItemDemandAllocation(
            demand_item_id=demand_id,
            order_item_id=None,
            quantity=quantity,
            source=AllocationSource.STOCK,
        )


class DeleteStockAllocation(
    shared.DeleteStockAllocation[BoughtItemDemandItem, BoughtItemDemandAllocation]
):
    """Removes the stock allocation row of a demand."""

    _spec = SPEC

    def __init__(
        self,
        allocation_repo: IBoughtItemAllocationRepository,
        demand_repo: IBoughtItemDemandItemRepository,
        order_item_repo: IOrderItemRepository,
        *,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
    ) -> None:
        super().__init__(allocation_repo, demand_repo, uow=uow, reconciler=reconciler)
        self._order_items = order_item_repo
