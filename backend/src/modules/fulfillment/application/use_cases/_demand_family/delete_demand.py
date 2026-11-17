"""
Deletes a demand of a family whose demands can be deleted, bought and made
item demands; a source item demand belongs to its lot and is only canceled.
A demand that still holds allocations is refused (409), since deleting it
would orphan them; it is canceled instead, which releases them. Who may
delete is decided as for a cancel by assert_can_cancel_demand, and a
fulfilled or canceled demand stays as the record it is.

The delete records no lifecycle fact, and nothing the reconciler derives
reads the deleted row, so the reconciler does not run. The demand is
locked through the request's lock plan before it is read, so an allocation
cannot be added between the check and the delete.
"""

from typing import Any
from typing import Generic

from src.modules.fulfillment.application.services.lifecycle_loader import AggregateIds
from src.modules.fulfillment.application.services.lifecycle_lock_plan import LockPlan
from src.modules.fulfillment.application.use_cases._demand_family.spec import AllocationRepo
from src.modules.fulfillment.application.use_cases._demand_family.spec import D
from src.modules.fulfillment.application.use_cases._demand_family.spec import DeletableDemandRepo
from src.modules.fulfillment.application.use_cases._demand_family.spec import DemandFamilySpec
from src.modules.fulfillment.application.use_cases._demand_family.spec import R
from src.modules.fulfillment.domain.services.demand_ownership_rules import assert_can_cancel_demand
from src.modules.fulfillment.domain.services.demand_status_rules import assert_demand_intent
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction


class DeleteDemand(Generic[D, R]):
    _spec: DemandFamilySpec[D, R]

    def __init__(
        self,
        demand_repo: DeletableDemandRepo[D],
        allocation_repo: AllocationRepo[Any],
        *,
        uow: IUnitOfWork,
        lock_plan: LockPlan | None = None,
    ) -> None:
        self._demands = demand_repo
        self._allocations = allocation_repo
        self._uow = uow
        self._lock_plan = lock_plan

    async def execute(self, actor: User, demand_id: int) -> R:
        spec = self._spec
        if self._lock_plan is not None:
            await self._lock_plan.acquire(AggregateIds.of({spec.aggregate: [demand_id]}))
        demand = found_or_raise(
            await self._demands.get_by_id(demand_id),
            spec.terms.not_found_error,
            spec.not_found_message(demand_id),
        )

        assert_can_cancel_demand(actor, demand)
        assert_demand_intent(
            actor,
            LifecycleAction.REMOVE,
            demand,
            has_allocations=bool(await self._allocations.get_by_demand_item_id(demand.id)),
            already_fulfilled_error=spec.terms.already_fulfilled_error,
            already_canceled_error=spec.terms.already_canceled_error,
            noun=spec.terms.noun,
        )

        demand.changes = append_changelog(
            demand.changes, actor.full_name, f"{spec.terms.noun} deleted."
        )
        await self._demands.delete(demand)
        await self._uow.commit()
        log.info(f"Deleted {spec.log_noun} #%s.", demand_id)
        return spec.to_result(demand)
