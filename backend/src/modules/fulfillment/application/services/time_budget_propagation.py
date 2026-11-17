"""
Cross-use-case hook for time_budget_service.py's apportionment. Called
from update_project.py (when
production_time_budget changes) and from lot_steps.py/update_lot.py (when
a lot's step composition, quantity, or a step's own
estimated_minutes_per_piece changes), a project-scoped batch recompute
that rewrites every affected LotStep.time_budget_per_piece under that one
project, distinct from the machine-scoped recompute triggered by
scheduling package callers (recompute_machine_schedule.py).

A production order snapshots its duration from its position's steps, the
time budget included, so a recompute that changes a step's budget copies
the new duration onto the queued and paused orders of that step's
position, in whichever lot of the project it is. Those orders are lifecycle
rows the caller locks through its lock plan before the time budget lock,
with its other lifecycle rows (budget_order_locks), so the recompute writes
only orders its transaction holds.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from src.modules.fulfillment.application.services.lifecycle_loader import AggregateIds
from src.modules.fulfillment.application.services.lifecycle_lock_plan import LockPlan
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.services.production_order_rules import (
    compute_estimated_duration_minutes,
)
from src.modules.fulfillment.domain.services.time_budget_service import StepBudgetInput
from src.modules.fulfillment.domain.services.time_budget_service import apportion_time_budget
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    IProductionOrderRepository,
)
from src.modules.platform.domain.exceptions import ConcurrentModificationError
from src.modules.workspace.ports.outbound.workspace_queries import IProjectQueries

# The orders whose duration snapshot follows their steps; one that started
# keeps the duration it started with.
_RESNAPSHOT_STATUSES = frozenset({ProductionOrderStatus.QUEUED, ProductionOrderStatus.PAUSED})


@dataclass(frozen=True)
class BudgetOrders:
    """The production orders a recompute snapshots again and the request's
    lock plan, which must hold their locks by the time it runs."""

    orders: IProductionOrderRepository
    lock_plan: LockPlan


async def budget_order_locks(
    project_ids: Iterable[int],
    lot_repo: IProductionLotRepository,
    order_repo: IProductionOrderRepository,
) -> AggregateIds:
    """The queued and paused production orders of the projects' lots, which
    a time budget recompute of those projects may snapshot again. A writer
    that recomputes adds them to the lock acquisition of its other
    lifecycle rows, which comes before the time budget lock."""
    position_ids: set[int] = set()
    for project_id in sorted(set(project_ids)):
        for lot in await lot_repo.get_by_project_id(project_id):
            position_ids.update(p.id for p in lot.positions)
    if not position_ids:
        return AggregateIds()
    orders = await order_repo.get_by_lot_position_ids(sorted(position_ids))
    return AggregateIds.of(
        {
            LifecycleAggregate.PRODUCTION_ORDERS: sorted(
                o.id for o in orders if o.status in _RESNAPSHOT_STATUSES
            )
        }
    )


async def recompute_project_time_budgets(
    project_id: int,
    project_repo: IProjectQueries,
    lot_repo: IProductionLotRepository,
    budget_orders: BudgetOrders,
) -> set[int | None]:
    """Rewrites the time budgets of the project's steps and snapshots the
    duration of the queued and paused orders of every position whose
    budgets changed again. Returns the machine ids of the orders it changed,
    for the caller's schedule walk after its commit.

    The recomputes of one project are serialized (lock_time_budgets), each
    reads the lots again and writes the budget column alone, so a recompute
    never writes back a step edit another request committed meanwhile, and
    the last one to run sees every input committed before it. The lock
    comes after every lifecycle row lock of the caller's transaction (its
    lot, project and demand locks, the orders of budget_order_locks and the
    reconciler's run), so a recompute never waits for a row while it holds
    the lock another writer of that row waits for. A caller that writes
    step rows itself takes the lock before its first step write
    (lock_structure_edit), so it never waits for the lock while holding
    rows another recompute writes."""
    project = await project_repo.get_by_id(project_id)
    if not project:
        return set()
    await lot_repo.lock_time_budgets(project_id)

    # Unpaged: a paged read would stop at its default page size and leave
    # the remaining lots' budgets apportioned against the old total.
    lots = await lot_repo.get_by_project_id(project_id, refresh=True)

    step_inputs: list[StepBudgetInput] = []
    steps_by_id: dict[int, LotStep] = {}
    for lot in lots:
        for position in lot.positions:
            for step in position.steps:
                step_inputs.append(
                    StepBudgetInput(
                        step_id=step.id,
                        lot_quantity=lot.quantity,
                        position_kind=position.kind,
                        estimated_minutes_per_piece=step.estimated_minutes_per_piece,
                    )
                )
                steps_by_id[step.id] = step

    if not step_inputs:
        return set()

    results = apportion_time_budget(step_inputs, project.production_time_budget)
    changed: dict[int, float | None] = {}
    for step_id, time_budget_per_piece in results.items():
        step = steps_by_id[step_id]
        if step.time_budget_per_piece != time_budget_per_piece:
            step.time_budget_per_piece = time_budget_per_piece
            changed[step_id] = time_budget_per_piece
    if not changed:
        return set()
    await lot_repo.save_step_time_budgets(changed)
    return await _resnapshot_orders(
        {
            position.id: position
            for lot in lots
            for position in lot.positions
            if any(step.id in changed for step in position.steps)
        },
        budget_orders,
    )


async def _resnapshot_orders(
    positions: dict[int, LotPosition], budget_orders: BudgetOrders
) -> set[int | None]:
    """Copies the duration of each position's steps, their new budgets
    included, onto its queued and paused orders. An order the lock plan
    does not hold went live after the caller read which orders to lock, so
    the request is refused as a concurrent change and nothing commits."""
    touched_machine_ids: set[int | None] = set()
    if not positions:
        return touched_machine_ids
    held = budget_orders.lock_plan.held.get(LifecycleAggregate.PRODUCTION_ORDERS)
    orders = await budget_orders.orders.get_by_lot_position_ids(sorted(positions), refresh=True)
    for order in orders:
        if order.status not in _RESNAPSHOT_STATUSES:
            continue
        duration = compute_estimated_duration_minutes(
            positions[order.lot_position_id].steps, order.quantity
        )
        if duration == order.estimated_duration_minutes:
            continue
        if order.id not in held:
            raise ConcurrentModificationError(
                f"Production order #{order.id} was queued while the time budgets of its "
                "project were recomputed."
            )
        order.estimated_duration_minutes = duration
        await budget_orders.orders.save(order)
        touched_machine_ids.add(order.machine_id)
    return touched_machine_ids


async def recompute_time_budgets_of_projects(
    project_ids: Iterable[int],
    project_repo: IProjectQueries | None,
    lot_repo: IProductionLotRepository,
    budget_orders: BudgetOrders,
) -> set[int | None]:
    """Recomputes the budgets of every project in `project_ids`, in id order
    so two writers take the projects' budget locks in one order, and
    returns the machine ids of the orders it snapshotted again. A cascade
    that changed lot quantities or position kinds calls it after its
    reconciler run, for the lots' projects, whose orders it locked before
    (budget_order_locks); without a project repository it does nothing."""
    touched_machine_ids: set[int | None] = set()
    if project_repo is None:
        return touched_machine_ids
    for project_id in sorted(set(project_ids)):
        touched_machine_ids |= await recompute_project_time_budgets(
            project_id, project_repo, lot_repo, budget_orders
        )
    return touched_machine_ids
