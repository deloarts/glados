"""
Repository interface for recorded production plans, with their order and
lot rows. A plan is written once and read or purged as a whole.
"""

from datetime import date
from typing import Protocol
from typing import runtime_checkable

from src.modules.fulfillment.domain.entities.production_plan import ProductionPlan
from src.modules.fulfillment.domain.value_objects.plan_kind import PlanKind


@runtime_checkable
class IProductionPlanRepository(Protocol):
    async def add(self, plan: ProductionPlan) -> ProductionPlan:
        """Records the plan with its rows. A second baseline for the same day
        violates the one-baseline-per-day index."""
        ...

    async def get_by_day(self, kind: PlanKind, plan_day: date) -> ProductionPlan | None:
        """The plan of `kind` recorded for the day, with its rows, or None.
        For a kind with several plans a day, the latest one."""
        ...

    async def exists_for(self, kind: PlanKind, plan_day: date) -> bool: ...

    async def delete_before(self, plan_day: date) -> int:
        """Deletes every plan of a day before `plan_day` with its rows and
        returns how many plans it deleted."""
        ...
