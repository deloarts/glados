"""
Marking a demand fulfilled compares its status again once the demand is
locked: a demand that a concurrent writer fulfilled between the first read
and the lock answers as it does when it already was fulfilled, without a
conflict and without recording another mark.
"""

from typing import Any

from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.fulfillment.application.use_cases.bought_item_demand.update_demand_item_status import (
    UpdateDemandItemStatus,
)
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.order._helpers import FakeAllocationRepository
from tests.unit.order._helpers import FakeOrderItemRepository
from tests.unit.production_lot.fakes import FakeSourceItemAllocationRepository
from tests.unit.test_demand_item_use_cases import make_demand


class _Demands:
    """Answers the first read with an open demand and every later one, the
    read under the lock included, with the demand fulfilled meanwhile."""

    def __init__(self) -> None:
        self.reads = 0
        self.saved: list[Any] = []

    async def get_by_id(self, demand_id: int) -> Any:
        self.reads += 1
        return make_demand(
            id=demand_id,
            status=BoughtItemDemandStatus.OPEN
            if self.reads == 1
            else BoughtItemDemandStatus.FULFILLED,
        )

    async def save(self, demand: Any) -> Any:
        self.saved.append(demand)
        return demand


class _Reconciler:
    def touch_demands(self, aggregate: object, ids: list[int]) -> None:
        return None

    def touch_allocations_on(self, **ids: object) -> None:
        return None

    async def lock_touched(self, **also: object) -> None:
        return None

    async def run(self, *args: object, **kwargs: object) -> None:
        raise AssertionError("nothing is left to reconcile")


class _NoCancel:
    async def execute_permitted(self, actor: object, demand_id: int) -> Any:
        raise AssertionError("a fulfil is no cancel")


async def test_a_demand_fulfilled_before_the_lock_is_answered_as_fulfilled() -> None:
    demands = _Demands()
    uow = FakeUnitOfWork()
    use_case = UpdateDemandItemStatus(
        demands,  # type: ignore[arg-type]
        _NoCancel(),
        uow=uow,
        reconciler=_Reconciler(),  # type: ignore[arg-type]
        allocation_repo=FakeAllocationRepository(),
        source_allocation_repo=FakeSourceItemAllocationRepository(),
        order_item_repo=FakeOrderItemRepository(),
    )
    actor = make_user(permissions=[Permission.WRITE_DEMAND_ITEMS, Permission.MANAGE_DEMAND_ITEMS])

    result = await use_case.execute(actor, 1, "fulfilled")

    assert result.status == "fulfilled"
    assert demands.saved == []
