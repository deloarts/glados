"""
Sweeps every made-item demand with unallocated quantity remaining and
groups it into lots: same project + same made item accumulate into one
lot, quantity 1:1 against the unallocated remainder. Unlike bought/source
item auto-allocation (which links a demand to existing supply), a made
item has nothing to allocate against yet, creating the lot IS the
allocation, so commit() reuses CreateLot per group rather than
reimplementing lot construction. Demands whose project is deleted or not
active, or whose made item new work may not name, are left out, since lot
creation refuses them and one refused group would undo the whole sweep.
Every demand of the sweep is locked before the first lot, and the lifecycle
reconciler CreateLot registered the new lots and their demands with runs
once for the whole sweep, before the events are published and the sweep
committed. A demand is picked while it lacks coverage (uncovered_rest in
lifecycle/demand.py), the rule auto-allocation selects by too.
"""

from dataclasses import dataclass
from dataclasses import field
from datetime import date

from src.modules.catalogue.domain.policies.made_item_rules import MadeItemCatalogueRules
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.application.dto.production_lot_dto import (
    AutoAssignLotGroupDemandResult,
)
from src.modules.fulfillment.application.dto.production_lot_dto import AutoAssignLotGroupResult
from src.modules.fulfillment.application.dto.production_lot_dto import CreateLotCommand
from src.modules.fulfillment.application.dto.production_lot_dto import LotDemandAllocationInput
from src.modules.fulfillment.application.dto.production_lot_dto import LotResult
from src.modules.fulfillment.application.mappers.production_lot_mapper import LotMapper
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.use_cases.production_lot.create_lot import CreateLot
from src.modules.fulfillment.domain.entities.made_item_allocation import MadeItemDemandAllocation
from src.modules.fulfillment.domain.entities.made_item_demand_item import MadeItemDemandItem
from src.modules.fulfillment.domain.events.lot_events import LotCreated
from src.modules.fulfillment.domain.services.lifecycle.demand import uncovered_rest
from src.modules.fulfillment.domain.services.lot_rules import LotRules
from src.modules.fulfillment.domain.services.lot_rules import build_lot_coverage
from src.modules.fulfillment.domain.services.made_item_allocation_service import (
    MadeItemAllocationQuantityService,
)
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    IMadeItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    IMadeItemDemandItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.platform.application.services.retry_on_conflict import (
    commit_or_raise_numbering_conflict,
)
from src.modules.platform.application.services.schedule_recompute_port import ScheduleRecompute
from src.modules.platform.application.services.schedule_recompute_port import (
    recompute_schedule_after_commit,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.domain.policies.project_activity import is_project_active
from src.modules.workspace.ports.outbound.workspace_queries import IProjectQueries
from src.shared_kernel.domain.services.clock import now_utc


@dataclass
class _Group:
    made_item_id: int
    project_id: int
    item_part_number: str
    item_revision: str
    item_article_name: str
    project_number: str
    project_customer: str
    quantity: float = 0.0
    high_priority: bool = False
    demands: list[tuple[int, float]] = field(default_factory=list)
    # Earliest desired_delivery_date among this group's demands. None is
    # "no constraint" and never wins over an actual date (mirrors the
    # frontend's earlierDate() used for the same aggregation client-side).
    required_delivery_date: date | None = None


class AutoAssignLots:
    def __init__(
        self,
        demand_repo: IMadeItemDemandItemRepository,
        allocation_repo: IMadeItemAllocationRepository,
        lot_repo: IProductionLotRepository,
        create_lot: CreateLot,
        *,
        uow: IUnitOfWork,
        event_bus: IEventBus,
        reconciler: LifecycleReconciler,
        # None only for unit tests that predate the project filter; the deps
        # factory always passes it.
        project_repo: IProjectQueries | None = None,
        recompute_schedule: ScheduleRecompute | None = None,
    ) -> None:
        """`reconciler` is the request's lifecycle reconciler, the one
        `create_lot` registers the new lots with."""
        self._demands = demand_repo
        self._allocations = allocation_repo
        self._lots = lot_repo
        self._create_lot = create_lot
        self._uow = uow
        self._bus = event_bus
        self._reconciler = reconciler
        self._projects = project_repo
        self._recompute = recompute_schedule

    async def _compute_groups(self) -> list[_Group]:
        # Unpaged: a paged read would stop at its default page size.
        demands = await self._demands.get_by_statuses(
            [MadeItemDemandStatus.OPEN, MadeItemDemandStatus.ALLOCATED]
        )
        demands = await self._demands_new_lots_may_take(demands)
        if not demands:
            return []

        demand_ids = [d.id for d in demands]
        all_allocations = await self._allocations.get_by_demand_item_ids(demand_ids)
        allocations_by_demand: dict[int, list[MadeItemDemandAllocation]] = {}
        for allocation in all_allocations:
            allocations_by_demand.setdefault(allocation.demand_item_id, []).append(allocation)

        lot_ids = sorted({a.lot_id for a in all_allocations if a.lot_id})
        lot_coverage = build_lot_coverage(await self._lots.get_by_ids(lot_ids)) if lot_ids else {}

        groups: dict[tuple[int, int], _Group] = {}
        for demand in demands:
            # The rest reads the allocated and stock pieces only, no fill.
            summary = MadeItemAllocationQuantityService.compute_summary(
                demand, allocations_by_demand.get(demand.id, []), lot_coverage, fill={}
            )
            rest = uncovered_rest(
                demand.status, demand.quantity, summary.allocated + summary.fulfilled_from_stock
            )
            if rest <= 0:
                continue

            key = (demand.project_id, demand.made_item_id)
            group = groups.get(key)
            if group is None:
                group = _Group(
                    made_item_id=demand.made_item_id,
                    project_id=demand.project_id,
                    item_part_number=demand.item_part_number,
                    item_revision=demand.item_revision,
                    item_article_name=demand.item_article_name,
                    project_number=demand.project_number,
                    project_customer=demand.project_customer,
                )
                groups[key] = group
            group.quantity = round(group.quantity + rest, 6)
            group.high_priority = group.high_priority or demand.high_priority
            group.demands.append((demand.id, rest))
            if demand.desired_delivery_date is not None and (
                group.required_delivery_date is None
                or demand.desired_delivery_date < group.required_delivery_date
            ):
                group.required_delivery_date = demand.desired_delivery_date

        return list(groups.values())

    async def _demands_new_lots_may_take(
        self, demands: list[MadeItemDemandItem]
    ) -> list[MadeItemDemandItem]:
        """The demands whose project is active and whose made item new work
        may name. A demand read without its item leaves the item check to
        lot creation itself."""
        active_projects = await self._active_project_ids({d.project_id for d in demands})
        return [
            demand
            for demand in demands
            if (active_projects is None or demand.project_id in active_projects)
            and (
                demand.item is None
                or MadeItemCatalogueRules.demandable_refusal(demand.item) is None
            )
        ]

    async def _active_project_ids(self, project_ids: set[int]) -> set[int] | None:
        """The given projects that are active, None when no project
        repository is wired. A deleted project is not found."""
        if self._projects is None:
            return None
        active: set[int] = set()
        for project_id in sorted(project_ids):
            project = await self._projects.get_by_id(project_id)
            if project is not None and is_project_active(project):
                active.add(project_id)
        return active

    async def preview(self, actor: User) -> list[AutoAssignLotGroupResult]:
        LotRules.assert_can_create(actor)
        return [
            AutoAssignLotGroupResult(
                made_item_id=g.made_item_id,
                item_part_number=g.item_part_number,
                item_revision=g.item_revision,
                item_article_name=g.item_article_name,
                project_id=g.project_id,
                project_number=g.project_number,
                project_customer=g.project_customer,
                quantity=g.quantity,
                high_priority=g.high_priority,
                demands=[
                    AutoAssignLotGroupDemandResult(demand_item_id=demand_id, quantity=quantity)
                    for demand_id, quantity in g.demands
                ],
                required_delivery_date=g.required_delivery_date,
            )
            for g in await self._compute_groups()
        ]

    async def execute(self, actor: User) -> list[LotResult]:
        """All-or-nothing: every group is created inside ONE transaction
        and committed once, rather than committing lot by lot. The preview
        showed the user N groups, so committing 3 of 7 with no indication of
        which is worse than committing none, since a later group raising now rolls
        the whole sweep back. The events are staged into the outbox inside
        that transaction, after the reconciler run and before the single
        commit, so they are delivered only once it commits and no subscriber
        can observe a lot a later failure undid."""
        LotRules.assert_can_create(actor)

        groups = await self._compute_groups()
        # The sweep's projects are locked in shared mode first, as every
        # creation of work locks its project (IProjectQueries), then the
        # queues the new lots' inspections are queued in, as for every
        # writer that draws queue places (queue_scope_locks.py).
        if self._projects is not None:
            await self._projects.lock_for_share(sorted({g.project_id for g in groups}))
        await self._create_lot.lock_routing_queue_scopes(g.made_item_id for g in groups)
        # Every demand of the sweep is locked in one acquisition before the
        # first lot, since the lots link them group by group and a later
        # group's lower demand id would otherwise break the one lock order.
        self._reconciler.touch_demands(
            LifecycleAggregate.MADE_DEMANDS,
            [demand_id for g in groups for demand_id, _ in g.demands],
        )
        await self._reconciler.lock_touched()

        saved_lots = []
        for g in groups:
            cmd = CreateLotCommand(
                made_item_id=g.made_item_id,
                project_id=g.project_id,
                quantity=g.quantity,
                demand_allocations=[
                    LotDemandAllocationInput(demand_item_id=demand_id, quantity=quantity)
                    for demand_id, quantity in g.demands
                ],
                required_delivery_date=g.required_delivery_date,
            )
            saved_lots.append(await self._create_lot.create_no_commit(actor, cmd))

        if not saved_lots:
            return []

        await self._reconciler.run(actor, now_utc())

        # create_no_commit deliberately does not publish; the transaction
        # owner does, staging into the outbox inside its own transaction
        # (see event_outbox.py and CreateLot.execute).
        for lot in saved_lots:
            await self._bus.publish(
                LotCreated(
                    lot_id=lot.id,
                    made_item_id=lot.made_item_id,
                    creator_id=lot.creator_id,
                )
            )

        # create_no_commit draws each lot_number from the row-locked counter,
        # which can still meet a number stored outside it (see
        # retry_on_conflict.py); this sweep cannot simply be replayed (the
        # groups were computed up front), so a collision surfaces as a clean
        # 409 rather than a raw 500. The staged event rows roll back with the
        # writes when it does.
        await commit_or_raise_numbering_conflict(self._uow)
        # The orders auto-queued for the new lots' inspection positions join
        # their queues.
        await recompute_schedule_after_commit(
            self._recompute, after="auto-assigning lots; the new lots are committed."
        )

        results = []
        for lot in saved_lots:
            refreshed = await self._lots.get_by_id(lot.id)
            results.append(LotMapper.to_result(refreshed if refreshed is not None else lot))
        return results
