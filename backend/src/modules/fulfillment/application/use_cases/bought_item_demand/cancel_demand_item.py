"""
Cancels a bought item demand. Canceling records canceled_at and releases
every allocation of the demand, on order lines and from stock, so the line
capacity and the stock it held are free again; the lifecycle reconciler then
derives CANCELED and publishes the status event that notifies the creator.
A fulfilled demand cannot be canceled, and a canceled one is not canceled
again.

Who may cancel is decided by assert_can_change_demand_status, the rule the
status endpoints of all three demand families share. `execute` serves the
cancel route and applies that rule; `execute_permitted` serves the status
route, which has already applied it, so both routes cancel the same way.
"""

from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.fulfillment.application.dto.bought_item_demand_dto import DemandItemResult
from src.modules.fulfillment.application.mappers.bought_item_demand_mapper import (
    BoughtItemDemandItemMapper,
)
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.use_cases._demand_family.spec import CANCEL_REASON
from src.modules.fulfillment.domain.errors import DemandItemAlreadyCanceledError
from src.modules.fulfillment.domain.errors import DemandItemAlreadyFulfilledError
from src.modules.fulfillment.domain.errors import DemandItemNotFoundError
from src.modules.fulfillment.domain.services.demand_status_rules import (
    assert_can_change_demand_status,
)
from src.modules.fulfillment.domain.services.demand_status_rules import assert_demand_intent
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemDemandItemRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction

_BOUGHT = LifecycleAggregate.BOUGHT_DEMANDS


class CancelDemandItem:
    """Cancels one bought item demand; see the module docstring."""

    def __init__(
        self,
        demand_repo: IBoughtItemDemandItemRepository,
        allocation_repo: IBoughtItemAllocationRepository,
        *,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
    ) -> None:
        self._demands = demand_repo
        self._allocations = allocation_repo
        self._uow = uow
        self._reconciler = reconciler

    async def execute(self, actor: User, demand_id: int) -> DemandItemResult:
        demand = found_or_raise(
            await self._demands.get_by_id(demand_id),
            DemandItemNotFoundError,
            f"Demand item #{demand_id} not found.",
        )
        assert_can_change_demand_status(actor, demand, BoughtItemDemandStatus.CANCELED)
        return await self.execute_permitted(actor, demand_id)

    async def execute_permitted(self, actor: User, demand_id: int) -> DemandItemResult:
        """The cancel for a caller that has already decided the actor may
        cancel the demand."""
        # Locked before the checks, so no allocation writer can add to the
        # demand between the release below and the commit.
        self._reconciler.touch_demands(_BOUGHT, [demand_id])
        await self._reconciler.lock_touched()
        demand = found_or_raise(
            await self._demands.get_by_id(demand_id),
            DemandItemNotFoundError,
            f"Demand item #{demand_id} not found.",
        )
        allocations = await self._allocations.get_by_demand_item_id(demand_id)
        assert_demand_intent(
            actor,
            LifecycleAction.CANCEL,
            demand,
            has_allocations=bool(allocations),
            already_fulfilled_error=DemandItemAlreadyFulfilledError,
            already_canceled_error=DemandItemAlreadyCanceledError,
            noun="Demand item",
        )

        for allocation in allocations:
            await self._allocations.delete(allocation)
        now = now_utc()
        demand.canceled_at = now
        demand.changed = now
        demand.changes = append_changelog(
            demand.changes,
            actor.full_name,
            f"Canceled; released {len(allocations)} allocation(s).",
        )
        await self._demands.save(demand)
        await self._reconciler.run(actor, now, reason=CANCEL_REASON)
        await self._uow.commit()

        log.info(f"Canceled demand #{demand_id}, released {len(allocations)} allocation(s).")
        canceled = await self._demands.get_by_id(demand_id)
        return BoughtItemDemandItemMapper.to_result(canceled or demand)
