"""
The automatic allocation of a bought or source item demand on order lines.
It finds the open lines (ORDERED or PARTIALLY_DELIVERED) for the demand's
material and allocates greedily, in priority order, until the demand is
covered or no line has anything left:

  1. ORDERED before PARTIALLY_DELIVERED, preferring fresh orders.
  2. Earliest expected delivery date first.
  3. Largest available quantity first, touching as few lines as possible.

What a line has available counts the allocations of bought and source item
demands on it together, since both can hold part of the same line. The
candidate lines are locked in ascending id before the demand, the order in
which every allocation writer takes its locks, and every decision is made on
the rows read under those locks. After allocating, the lifecycle reconciler
derives the demand's status. A fulfilled or canceled demand, and a demand of
a deleted project, take no allocation.

A family's subclass binds `_spec` and `_result` and supplies what differs
as hooks: which lines carry the demand's material, the allocation row it
saves, and for source item demands the schedule recompute after the commit.
"""

from abc import abstractmethod
from collections.abc import Callable
from dataclasses import replace
from datetime import date
from typing import Any
from typing import Generic
from typing import Protocol
from typing import TypeVar

from src.modules.fulfillment.application.services.allocation_fill import LineFillRepos
from src.modules.fulfillment.application.services.allocation_fill import displaced_on_line
from src.modules.fulfillment.application.services.allocation_locks import lock_for_allocation
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.use_cases._demand_family.allocation_writers import L
from src.modules.fulfillment.application.use_cases._demand_family.allocation_writers import (
    OrderLineAllocationRepo,
)
from src.modules.fulfillment.application.use_cases._demand_family.spec import ALLOCATION_REASON
from src.modules.fulfillment.application.use_cases._demand_family.spec import DemandFamilySpec
from src.modules.fulfillment.application.use_cases._demand_family.spec import DemandRepo
from src.modules.fulfillment.application.use_cases._demand_family.spec import FamilyDemand
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.services.allocation_coverage import order_item_capacity_left
from src.modules.fulfillment.domain.services.allocation_coverage import units_differ
from src.modules.fulfillment.domain.services.lifecycle.demand import uncovered_rest
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.quantities import quantity_gt
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.ports.outbound.workspace_queries import IProjectQueries
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc

ELIGIBLE_LINE_STATUSES = frozenset(
    {
        OrderItemStatus.ORDERED,
        OrderItemStatus.PARTIALLY_DELIVERED,
    }
)


class ProjectDemand(FamilyDemand, Protocol):
    project_id: int


class AutoAllocateCommand(Protocol):
    @property
    def demand_item_id(self) -> int: ...


PD = TypeVar("PD", bound=ProjectDemand)
C = TypeVar("C", bound=AutoAllocateCommand)
AR = TypeVar("AR")


class AutoAllocateOnOrderLines(Generic[PD, L, C, AR]):
    """`_result` builds the family's result DTO from the fields every
    family's result has."""

    _spec: DemandFamilySpec[PD, Any]
    _result: Callable[..., AR]

    def __init__(
        self,
        demand_repo: DemandRepo[PD],
        order_item_repo: IOrderItemRepository,
        allocation_repo: OrderLineAllocationRepo[L],
        *,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
        project_repo: IProjectQueries,
        fill_repos: LineFillRepos,
    ) -> None:
        self._demands = demand_repo
        self._order_items = order_item_repo
        self._allocations = allocation_repo
        self._fill_repos = fill_repos
        self._uow = uow
        self._reconciler = reconciler
        self._projects = project_repo

    async def execute(self, actor: User, cmd: C) -> AR:
        spec = self._spec
        spec.rules.assert_can_allocate(actor)

        # Discovery read: it only tells which material's lines to lock. Apart
        # from a missing demand, every decision is made on the locked read
        # further down, and this copy is never saved.
        discovered = found_or_raise(
            await self._demands.get_by_id(cmd.demand_item_id),
            spec.terms.not_found_error,
            spec.not_found_message(cmd.demand_item_id),
        )

        # The candidate lines and then the demand are locked through the
        # request's lock plan in one acquisition, held until the single
        # uow.commit() below, so a concurrent allocation against the same
        # line or the same demand waits instead of passing on the same
        # totals (allocation_locks.py).
        lines = await self._lock_candidate_lines(discovered)
        demand = found_or_raise(
            await self._demands.get_by_id_for_update(cmd.demand_item_id),
            spec.terms.not_found_error,
            spec.not_found_message(cmd.demand_item_id),
        )

        if demand.status in (spec.terms.fulfilled, spec.terms.canceled):
            return self._nothing_allocated(demand.id)

        existing_allocations = await self._allocations.get_by_demand_item_id(demand.id)
        already_allocated = sum(a.quantity for a in existing_allocations)
        remaining = uncovered_rest(demand.status, demand.quantity, already_allocated)

        if not quantity_gt(remaining, 0.0):
            return self._nothing_allocated(demand.id)
        if await self._project_deleted(demand.project_id):
            return self._nothing_allocated(demand.id, remaining)

        candidates, available = await self._ranked_candidates(demand, lines)
        allocated = await self._allocate_greedily(
            actor, demand, candidates, available, existing_allocations, remaining
        )
        created, updated, total_newly_allocated, remaining, unit_mismatches = allocated

        new_status: str | None = None
        if total_newly_allocated > 0:
            await self._record_allocated(actor, demand, total_newly_allocated, created + updated)
            self._reconciler.touch_demands(spec.aggregate, [demand.id])
            result = await self._reconciler.run(actor, now_utc(), reason=ALLOCATION_REASON)
            new_status = result.new_status(spec.aggregate, demand.id)

        await self._uow.commit()
        # A run that allocated nothing moved no date.
        if total_newly_allocated > 0:
            await self._after_commit(
                f"auto-allocating {spec.log_noun} #{demand.id}; the allocation itself is committed."
            )

        log.info(
            f"Auto-allocated {spec.log_noun} #{demand.id}: "
            f"{total_newly_allocated:.3f} units across {created} new + {updated} updated "
            f"allocations. Remaining unallocated: {remaining:.3f}."
        )
        return self._result(
            demand_item_id=demand.id,
            allocations_created=created,
            allocations_updated=updated,
            total_newly_allocated=total_newly_allocated,
            remaining_unallocated=max(0.0, remaining),
            demand_status_changed_to=new_status,
            unit_mismatches=unit_mismatches,
        )

    @abstractmethod
    async def _find_lines(self, demand: PD) -> list[OrderItem]:
        """The order lines for the demand's material, of any status."""

    @abstractmethod
    def _line_matches(self, demand: PD, line: OrderItem) -> bool:
        """Whether the line is for the demand's own material, the safety
        check against a line or a demand repointed since the discovery read."""

    @abstractmethod
    def _new_allocation(self, demand_id: int, order_item_id: int, quantity: float) -> L:
        """The family's allocation row of the demand on the line."""

    async def _after_commit(self, action: str) -> None:
        """Runs once the run is committed; nothing by default. `action`
        completes a sentence such as "Schedule recompute failed after ..."."""

    async def _lock_candidate_lines(self, demand: PD) -> list[OrderItem]:
        """Locks the lines that auto-allocation may draw on together with
        the demand, and returns the lines as read under the lock. A line
        that is no longer eligible by then is filtered out later."""
        found = await self._find_lines(demand)
        line_ids = sorted({line.id for line in found if line.status in ELIGIBLE_LINE_STATUSES})
        await lock_for_allocation(
            self._reconciler, self._spec.aggregate, [demand.id], order_item_ids=line_ids
        )
        # The lock re-read the lines' columns; this one read their relations.
        locked = await self._order_items.get_by_ids(line_ids, refresh=True)
        return sorted(locked, key=lambda line: line.id)

    async def _ranked_candidates(
        self, demand: PD, lines: list[OrderItem]
    ) -> tuple[list[OrderItem], dict[int, float]]:
        """The locked lines that are still eligible for the demand, in
        priority order, and what each has available."""
        candidates = [
            line
            for line in lines
            if line.status in ELIGIBLE_LINE_STATUSES and self._line_matches(demand, line)
        ]
        available = await self._capacity_left(candidates)
        sort_keys: dict[int, tuple[int, date, float]] = {}
        for line in candidates:
            status_rank = 0 if line.status == OrderItemStatus.ORDERED else 1
            delivery = line.expected_delivery_date or date(9999, 12, 31)
            sort_keys[line.id] = (status_rank, delivery, -available[line.id])
        candidates.sort(key=lambda line: sort_keys[line.id])
        return candidates, available

    async def _capacity_left(self, lines: list[OrderItem]) -> dict[int, float]:
        """What each line still has free, counting the allocations of both
        demand families on it."""
        allocated = await self._allocations.get_allocated_quantities_for_order_items(
            [line.id for line in lines]
        )
        return {
            line.id: order_item_capacity_left(line, allocated.get(line.id, 0.0)) for line in lines
        }

    async def _allocate_greedily(
        self,
        actor: User,
        demand: PD,
        candidates: list[OrderItem],
        available: dict[int, float],
        existing_allocations: list[L],
        remaining: float,
    ) -> tuple[int, int, float, float, int]:
        """Allocates `remaining` across `candidates` in their order until it
        is covered or no candidate has anything left. Returns (created,
        updated, total newly allocated, remaining after, lines used whose
        unit differs from the demand's). Nothing converts between units, so
        the caller warns about the last."""
        created = 0
        updated = 0
        unit_mismatches = 0
        total_newly_allocated = 0.0
        for line in candidates:
            if not quantity_gt(remaining, 0.0):
                break
            # Each line is visited once, so what this run allocated so far
            # sits on other lines and the capacity read above still holds.
            if not quantity_gt(available[line.id], 0.0):
                continue
            allocate_qty = min(remaining, available[line.id])
            existing = next((a for a in existing_allocations if a.order_item_id == line.id), None)
            # A line whose arrived pieces would move from another demand to
            # this one is skipped, as a manual allocation there is refused.
            held = existing.quantity if existing else 0.0
            if await displaced_on_line(
                self._fill_repos, line, self._spec.fill_rank, demand.id, held + allocate_qty
            ):
                continue
            if existing:
                # A top-up changes the quantity only.
                await self._allocations.save(
                    replace(existing, quantity=existing.quantity + allocate_qty)
                )
                updated += 1
            else:
                allocation = self._new_allocation(demand.id, line.id, allocate_qty)
                allocation.created_by_id = actor.id
                await self._allocations.save(allocation)
                created += 1
            if units_differ(demand.unit, line.unit):
                unit_mismatches += 1
            remaining -= allocate_qty
            total_newly_allocated += allocate_qty
        return created, updated, total_newly_allocated, remaining, unit_mismatches

    async def _project_deleted(self, project_id: int) -> bool:
        """Whether the demand's project is deleted, which the project
        repository answers by not finding it."""
        return await self._projects.get_by_id(project_id) is None

    async def _record_allocated(
        self, actor: User, demand: PD, total_newly_allocated: float, order_items_touched: int
    ) -> None:
        """Notes the run on the demand's changelog; the reconciler then
        derives its status and notes a change."""
        demand.changed = now_utc()
        demand.changes = append_changelog(
            demand.changes,
            actor.full_name,
            f"Auto-allocated {total_newly_allocated:.3f} {demand.unit} "
            f"across {order_items_touched} order item(s).",
        )
        await self._demands.save(demand)

    def _nothing_allocated(self, demand_item_id: int, remaining: float = 0.0) -> AR:
        """The result for a demand that took no allocation, `remaining` being
        what it still lacks."""
        return self._result(
            demand_item_id=demand_item_id,
            allocations_created=0,
            allocations_updated=0,
            total_newly_allocated=0.0,
            remaining_unallocated=remaining,
            demand_status_changed_to=None,
        )
