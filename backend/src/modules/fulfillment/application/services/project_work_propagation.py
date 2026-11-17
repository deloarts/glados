"""
Planning & fulfillment's side of the project work propagation port: what a
project update does to the work planned on the project. A changed delivery
date is set on the project's open demands and on the open lots allocated to
them, and a changed production time budget is apportioned again over the
project's lots, with the durations of their queued and paused production
orders snapshotted again.

Every lot, production order and demand that may be written is locked in one
acquisition through the request's lock plan (lots, production orders,
demands), after the project row the caller locked and before the time
budget lock the recompute takes.
"""

from collections.abc import Set as AbstractSet
from datetime import date
from typing import Protocol
from typing import TypeVar

from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.application.services.lifecycle_loader import AggregateIds
from src.modules.fulfillment.application.services.lifecycle_lock_plan import LockPlan
from src.modules.fulfillment.application.services.time_budget_propagation import BudgetOrders
from src.modules.fulfillment.application.services.time_budget_propagation import budget_order_locks
from src.modules.fulfillment.application.services.time_budget_propagation import (
    recompute_project_time_budgets,
)
from src.modules.fulfillment.domain.entities.bought_item_demand_item import BoughtItemDemandItem
from src.modules.fulfillment.domain.entities.made_item_demand_item import MadeItemDemandItem
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemDemandItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    IMadeItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    IMadeItemDemandItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    IProductionOrderRepository,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.workspace.api import IProjectWorkPropagation
from src.modules.workspace.api import ProjectWorkChange
from src.modules.workspace.domain.entities.project import Project
from src.modules.workspace.ports.outbound.workspace_queries import IProjectQueries
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc

# Demands in these statuses are considered "completed" and are skipped by
# delivery-date propagation (they also reject further mutation, see
# MadeItemDemandRules/BoughtItemDemandRules).
_TERMINAL_MADE_STATUSES = {
    MadeItemDemandStatus.FULFILLED,
    MadeItemDemandStatus.CANCELED,
}
_TERMINAL_BOUGHT_STATUSES = {
    BoughtItemDemandStatus.FULFILLED,
    BoughtItemDemandStatus.CANCELED,
}
_TERMINAL_LOT_STATUSES = {
    LotStatus.COMPLETED,
    LotStatus.CANCELED,
    LotStatus.SCRAPPED,
}

_TItem = TypeVar("_TItem")
# Constrained so the propagation loop below can read/write the fields both
# demand entities share (they have no common base class).
_TDemand = TypeVar("_TDemand", MadeItemDemandItem, BoughtItemDemandItem)


class _DemandDateRepo(Protocol[_TItem]):
    """The narrow slice of the made/bought demand repositories that
    delivery-date propagation touches, both satisfy it structurally, so
    one generic loop serves both without widening items to a union."""

    async def get_by_project_id(self, project_id: int) -> list[_TItem]: ...
    async def save(self, demand: _TItem) -> _TItem: ...


class ProjectWorkPropagation(IProjectWorkPropagation):
    def __init__(
        self,
        project_repo: IProjectQueries,
        lot_repo: IProductionLotRepository | None = None,
        made_demand_repo: IMadeItemDemandItemRepository | None = None,
        bought_demand_repo: IBoughtItemDemandItemRepository | None = None,
        made_allocation_repo: IMadeItemAllocationRepository | None = None,
        *,
        lock_plan: LockPlan,
        order_repo: IProductionOrderRepository,
    ) -> None:
        """The production orders are the queued and paused ones of the
        project, whose duration a time budget change snapshots again. A time
        budget is recomputed only when the lots are wired."""
        self._projects = project_repo
        self._lots = lot_repo
        self._made_demands = made_demand_repo
        self._bought_demands = bought_demand_repo
        self._made_allocations = made_allocation_repo
        self._lock_plan = lock_plan
        self._orders = order_repo

    async def lock(self, project: Project, change: ProjectWorkChange) -> None:
        """Locks the lots and the open demands a date propagation may write,
        and the queued and paused orders whose duration a time budget
        change snapshots again, in one acquisition through the request's
        lock plan, so they are taken in the one lock order (lots, production
        orders, demands) and read again by the propagation."""
        made_ids: list[int] = []
        bought_ids: list[int] = []
        new_made = project.required_delivery_date_made
        if (
            change.propagate_delivery_date_made
            and self._made_demands is not None
            and new_made is not None
            and new_made != change.old_delivery_date_made
        ):
            made_ids = [
                d.id
                for d in await self._made_demands.get_by_project_id(project.id)
                if d.status not in _TERMINAL_MADE_STATUSES
            ]
        new_bought = project.required_delivery_date_bought
        if (
            change.propagate_delivery_date_bought
            and self._bought_demands is not None
            and new_bought is not None
            and new_bought != change.old_delivery_date_bought
        ):
            bought_ids = [
                d.id
                for d in await self._bought_demands.get_by_project_id(project.id)
                if d.status not in _TERMINAL_BOUGHT_STATUSES
            ]
        lot_ids: list[int] = []
        if made_ids and self._made_allocations is not None:
            allocations = await self._made_allocations.get_by_demand_item_ids(made_ids)
            lot_ids = sorted({a.lot_id for a in allocations if a.lot_id is not None})
        budget_orders = AggregateIds()
        if self._recomputes_budgets(change):
            assert self._lots is not None
            budget_orders = await budget_order_locks([project.id], self._lots, self._orders)
        await self._lock_plan.acquire(
            AggregateIds.of(
                {
                    LifecycleAggregate.LOTS: lot_ids,
                    LifecycleAggregate.BOUGHT_DEMANDS: bought_ids,
                    LifecycleAggregate.MADE_DEMANDS: made_ids,
                }
            ).union(budget_orders)
        )

    async def propagate_delivery_dates(
        self, actor: User, project: Project, change: ProjectWorkChange
    ) -> list[str]:
        """Propagates delivery dates to demands and lots and summarizes the
        affected counts as changelog notes for the project, since the user
        never named those rows."""
        notes: list[str] = []
        if change.propagate_delivery_date_made:
            updated_demand_ids = await self._propagate_delivery_date(
                project_id=project.id,
                old_date=change.old_delivery_date_made,
                new_date=project.required_delivery_date_made,
                repo=self._made_demands,
                terminal_statuses=_TERMINAL_MADE_STATUSES,
                actor=actor,
            )
            lot_count = 0
            if updated_demand_ids and project.required_delivery_date_made is not None:
                lot_count = await self._propagate_to_existing_lots(
                    demand_ids=updated_demand_ids,
                    new_date=project.required_delivery_date_made,
                    actor=actor,
                )
            if updated_demand_ids and project.required_delivery_date_made is not None:
                notes.append(
                    f"Propagated made delivery date "
                    f"{project.required_delivery_date_made.isoformat()} to "
                    f"{len(updated_demand_ids)} demand(s) and {lot_count} lot(s)."
                )
        if change.propagate_delivery_date_bought:
            bought_demand_ids = await self._propagate_delivery_date(
                project_id=project.id,
                old_date=change.old_delivery_date_bought,
                new_date=project.required_delivery_date_bought,
                repo=self._bought_demands,
                terminal_statuses=_TERMINAL_BOUGHT_STATUSES,
                actor=actor,
            )
            if bought_demand_ids and project.required_delivery_date_bought is not None:
                notes.append(
                    f"Propagated bought delivery date "
                    f"{project.required_delivery_date_bought.isoformat()} to "
                    f"{len(bought_demand_ids)} demand(s)."
                )
        return notes

    async def recompute_time_budgets(self, project_id: int) -> set[int | None]:
        if self._lots is None:
            return set()
        return await recompute_project_time_budgets(
            project_id, self._projects, self._lots, BudgetOrders(self._orders, self._lock_plan)
        )

    def _recomputes_budgets(self, change: ProjectWorkChange) -> bool:
        return change.recompute_time_budgets and self._lots is not None

    async def _propagate_delivery_date(
        self,
        *,
        project_id: int,
        old_date: date | None,
        new_date: date | None,
        repo: _DemandDateRepo[_TDemand] | None,
        terminal_statuses: AbstractSet[str],
        actor: User,
    ) -> list[int]:
        """Sets a changed, non-null date on every open demand of the project
        and returns their ids."""
        if new_date is None or new_date == old_date:
            return []
        if repo is None:
            log.warning(
                f"Delivery date propagation requested for project #{project_id} but "
                "no demand repository was wired into UpdateProject; skipping."
            )
            return []

        now = now_utc()
        updated_ids: list[int] = []
        for item in await repo.get_by_project_id(project_id):
            if item.status in terminal_statuses:
                continue
            item.desired_delivery_date = new_date
            item.changed = now
            item.changes = append_changelog(
                item.changes,
                actor.full_name,
                f"Desired delivery date set to {new_date.isoformat()} via project update.",
            )
            await repo.save(item)
            updated_ids.append(item.id)

        return updated_ids

    async def _propagate_to_existing_lots(
        self, *, demand_ids: list[int], new_date: date, actor: User
    ) -> int:
        """Sets the date on every open lot allocated to the updated demands,
        unconditionally, since a lot's date was copied from those demands in
        the first place. Returns the number of lots stamped."""
        if self._made_allocations is None or self._lots is None:
            return 0

        allocations = await self._made_allocations.get_by_demand_item_ids(demand_ids)
        lot_ids = sorted({a.lot_id for a in allocations if a.lot_id is not None})
        if not lot_ids:
            return 0

        now = now_utc()
        updated = 0
        for lot in await self._lots.get_by_ids(lot_ids):
            if lot.status in _TERMINAL_LOT_STATUSES:
                continue
            lot.required_delivery_date = new_date
            lot.changed = now
            lot.changes = append_changelog(
                lot.changes,
                actor.full_name,
                f"Required delivery date set to {new_date.isoformat()} via project update.",
            )
            await self._lots.save(lot)
            updated += 1

        return updated
