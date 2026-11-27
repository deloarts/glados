"""User-invoked lot lifecycle intents; the planning statuses follow from
position assignment instead. Each use case records its intent on the lot and
the facts it writes on the lot's work, and the lifecycle reconciler it runs
derives the statuses of the lot, its positions, its production orders and
its order lines, and publishes their status events.

HoldLot records held_at and opens a lot_hold interruption on every running
order of its internal positions, which pauses them; external positions
cannot be paused. ResumeLot clears held_at and closes exactly those
interruptions, so an order an operator paused by hand stays paused. The
orders keep their queue slots. A cancel or force-complete of a held lot
clears held_at too, since an ended lot is no longer held; both close the
open interruption of each of its orders and write their own timeline row.

CancelLot is refused while a position of the lot completed good pieces,
which only force-complete keeps. It records canceled_at, cancels the lot's
live work through the cascade of lot_cascades.py, except that a supplier
line already ordered with nothing received stays open for purchasing to
settle with the supplier, and deletes the allocations to the made-item
demands the lot was built for, because coverage counts raw allocation rows
and would otherwise leave those demands allocated forever. It settles the
lot's raw material demand (lot_cascades.settle_input_demand): canceled when
nothing of it is placed or arrived, otherwise fulfilled at what arrived with
the open rest of its supplier lines released. The demands that lost an
allocation and the raw material demand are registered with the reconciler,
which derives their statuses too.

CompleteLot closes the lot short at what it produced, its last position's
completed count: the lot and each position shrink to it (each position
never below its own completed count), the live work stops at what it did,
the made allocations shrink with the lot, the raw material demand is
settled as on a cancel, and force_completed_at completes the lot even while
a position stays short. Its own timeline row is the only one that starts
with "Lot force-completed".

Each use case locks its lot through the request's lock plan before it reads
what it checks, a cascade then the rows it may write (lot_work_lock_targets),
and returns the lot as the reconciler left it.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from datetime import datetime

from src.modules.fulfillment.application.dto.production_lot_dto import CancelLotCommand
from src.modules.fulfillment.application.dto.production_lot_dto import CompleteLotCommand
from src.modules.fulfillment.application.dto.production_lot_dto import HoldLotCommand
from src.modules.fulfillment.application.dto.production_lot_dto import LotResult
from src.modules.fulfillment.application.mappers.production_lot_mapper import LotMapper
from src.modules.fulfillment.application.services.lifecycle_loader import AggregateIds
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.services.lot_cascades import InputSettlement
from src.modules.fulfillment.application.services.lot_cascades import cancel_live_work
from src.modules.fulfillment.application.services.lot_cascades import close_live_work_short
from src.modules.fulfillment.application.services.lot_cascades import lines_to_settle_event
from src.modules.fulfillment.application.services.lot_cascades import lot_work_lock_targets
from src.modules.fulfillment.application.services.lot_cascades import settle_input_demand
from src.modules.fulfillment.application.services.piece_disposition import reallocate_lot_coverage
from src.modules.fulfillment.application.services.time_budget_propagation import BudgetOrders
from src.modules.fulfillment.application.services.time_budget_propagation import budget_order_locks
from src.modules.fulfillment.application.services.time_budget_propagation import (
    recompute_time_budgets_of_projects,
)
from src.modules.fulfillment.application.use_cases.production_lot.lot_positions import locked_lot
from src.modules.fulfillment.application.use_cases.production_schedule.recompute_machine_schedule import (
    RecomputeMachineSchedule,
)
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.entities.production_order_interruption import (
    ProductionOrderInterruption,
)
from src.modules.fulfillment.domain.errors import LotNotFoundError
from src.modules.fulfillment.domain.events.lot_events import LotCanceled
from src.modules.fulfillment.domain.events.lot_events import LotEndedShort
from src.modules.fulfillment.domain.events.lot_events import LotOnHold
from src.modules.fulfillment.domain.events.lot_events import LotResumed
from src.modules.fulfillment.domain.events.production_order_events import ProductionOrderPaused
from src.modules.fulfillment.domain.events.production_order_events import ProductionOrderResumed
from src.modules.fulfillment.domain.services.lot_event_service import build_lot_event
from src.modules.fulfillment.domain.services.lot_rules import LotRules
from src.modules.fulfillment.domain.services.lot_rules import assert_lot_action
from src.modules.fulfillment.domain.services.lot_rules import close_lot_short
from src.modules.fulfillment.domain.services.lot_rules import dropped_wip
from src.modules.fulfillment.domain.services.lot_rules import unused_raw_material
from src.modules.fulfillment.domain.value_objects.interruption_ended_by import InterruptionEndedBy
from src.modules.fulfillment.domain.value_objects.interruption_reason import InterruptionReason
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.lot_event_type import LotEventType
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    IMadeItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    IMadeItemDemandItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import IOrderRepository
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_interruption_repository import (
    IProductionOrderInterruptionRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    IProductionOrderRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemDemandRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.services.schedule_recompute_port import (
    recompute_schedule_after_commit,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.edit_version import assert_edit_version
from src.modules.platform.domain.services.edit_version import bump_edit_version
from src.modules.platform.domain.services.quantities import quantity_gt
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.ports.outbound.workspace_queries import IProjectQueries
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction


async def _reconciled_lot(lots: IProductionLotRepository, lot_id: int) -> ProductionLot:
    """The lot as the reconciler's run stored it."""
    return found_or_raise(
        await lots.get_by_id(lot_id), LotNotFoundError, f"Lot #{lot_id} not found."
    )


async def _budget_order_locks(
    projects: IProjectQueries | None,
    lots: IProductionLotRepository,
    orders: IProductionOrderRepository,
    lot: ProductionLot,
) -> AggregateIds:
    """The queued and paused orders of the lot's project, whose duration
    the time budget recompute after the cascade may snapshot again, locked
    with the cascade's rows; none without a project repository."""
    if projects is None:
        return AggregateIds()
    return await budget_order_locks([lot.project_id], lots, orders)


class CancelLot:
    """Cancels a lot, cascading into its live production orders and order
    lines, and deallocates the demands it was built for."""

    def __init__(
        self,
        lot_repo: IProductionLotRepository,
        order_repo: IProductionOrderRepository,
        order_item_repo: IOrderItemRepository,
        allocation_repo: IBoughtItemAllocationRepository,
        made_item_allocation_repo: IMadeItemAllocationRepository,
        source_item_demand_repo: ISourceItemDemandRepository,
        source_item_allocation_repo: ISourceItemAllocationRepository,
        *,
        event_bus: IEventBus,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
        interruption_repo: IProductionOrderInterruptionRepository,
        parent_order_repo: IOrderRepository,
        recompute_schedule: RecomputeMachineSchedule | None = None,
        project_repo: IProjectQueries | None = None,
    ) -> None:
        self._recompute = recompute_schedule
        self._projects = project_repo
        self._lots = lot_repo
        self._orders = order_repo
        self._order_items = order_item_repo
        self._allocations = allocation_repo
        self._made_item_allocations = made_item_allocation_repo
        self._source_item_demands = source_item_demand_repo
        self._source_item_allocations = source_item_allocation_repo
        self._bus = event_bus
        self._uow = uow
        self._reconciler = reconciler
        self._interruptions = interruption_repo
        self._parent_orders = parent_order_repo

    async def execute(
        self,
        actor: User,
        lot_id: int,
        cmd: CancelLotCommand,
        *,
        under_lock: Callable[[ProductionLot], Awaitable[None]] | None = None,
    ) -> LotResult:
        """`under_lock` is a caller's own check, run once the lot and every
        row the cancel may write are locked, before anything is written."""
        # Locked, because the cascade must not interleave with deliveries or
        # completions on the same lot.
        lot = await locked_lot(self._reconciler, self._lots, lot_id)
        # The base permission first, as hold and resume check it; the intent
        # table adds manage:lots.
        LotRules.assert_can_update(actor, lot)
        assert_lot_action(LifecycleAction.CANCEL, lot, actor)
        assert_edit_version(lot, cmd.expected_edit_version, what=f"Lot #{lot.id}")
        await self._reconciler.lock_touched(
            also=(await self.lock_targets(lot)).union(await self.budget_lock_targets([lot]))
        )
        if under_lock is not None:
            await under_lock(lot)

        now = now_utc()
        await self.cancel_no_commit(actor, lot, cmd, now=now)
        await self._reconciler.run(actor, now)
        # The lot's positions no longer take part in the project's budget,
        # and the time budget lock comes after every lifecycle row lock.
        await self.recompute_budgets([lot])
        canceled = await _reconciled_lot(self._lots, lot_id)
        await self._bus.publish(
            LotCanceled(
                lot_id=canceled.id,
                lot_number=canceled.lot_number,
                actor_id=actor.id,
                creator_id=canceled.creator_id,
            )
        )

        await self._uow.commit()
        # The lot's canceled orders free their places in the queues.
        await recompute_schedule_after_commit(
            self._recompute, after=f"canceling lot #{lot_id}; the cancel is committed."
        )
        log.info(f"Canceled lot {canceled.lot_number!r}.")
        return LotMapper.to_result(canceled)

    async def lock_targets(self, lot: ProductionLot) -> AggregateIds:
        """The rows the cancel cascade of the lot may write, for the caller
        to lock right after the lots it cancels, in one acquisition
        (lot_work_lock_targets)."""
        return await lot_work_lock_targets(self._reconciler, lot, self._orders, self._order_items)

    async def budget_lock_targets(self, lots: list[ProductionLot]) -> AggregateIds:
        """The queued and paused orders of the lots' projects, whose duration
        the time budget recompute after the cancels may snapshot again, for
        the caller to lock with lock_targets; none without a project
        repository."""
        if self._projects is None:
            return AggregateIds()
        return await budget_order_locks({lot.project_id for lot in lots}, self._lots, self._orders)

    async def recompute_budgets(self, lots: list[ProductionLot]) -> None:
        """Recomputes the time budgets of the canceled lots' projects and
        snapshots the durations they change, after the reconciler's run and
        under the locks of budget_lock_targets."""
        await recompute_time_budgets_of_projects(
            {lot.project_id for lot in lots},
            self._projects,
            self._lots,
            BudgetOrders(self._orders, self._reconciler.lock_plan),
        )

    async def cancel_no_commit(
        self, actor: User, lot: ProductionLot, cmd: CancelLotCommand, *, now: datetime
    ) -> ProductionLot:
        """The cancel without reconciling, publishing or committing, so a
        caller can cancel several lots in one transaction. The caller holds
        the lot's lock and the locks of lock_targets, then runs the
        reconciler this use case shares with it, recomputes the budgets
        (recompute_budgets, under the locks of budget_lock_targets) and
        publishes LotCanceled. Returns the lot as written, before the
        reconciler derives it."""
        assert_lot_action(LifecycleAction.CANCEL, lot, actor)
        reason = f"lot {lot.lot_number!r} was canceled"

        left_open = await cancel_live_work(
            lot,
            lot.positions,
            actor,
            now,
            reason=reason,
            lot_repo=self._lots,
            order_repo=self._orders,
            order_item_repo=self._order_items,
            parent_order_repo=self._parent_orders,
            interruption_repo=self._interruptions,
            reconciler=self._reconciler,
            allocation_repo=self._allocations,
            keep_ordered_lines=True,
        )

        # ── Deallocate the demands this lot was built for (module docstring).
        made_item_allocations = await self._made_item_allocations.get_by_lot_id(lot.id)
        affected_made_item_demand_ids = {a.demand_item_id for a in made_item_allocations}
        for allocation in made_item_allocations:
            await self._made_item_allocations.delete(allocation)
        self._reconciler.touch_demands(
            LifecycleAggregate.MADE_DEMANDS, affected_made_item_demand_ids
        )

        settled = await settle_input_demand(
            lot,
            actor,
            now,
            reason=reason,
            source_item_demands=self._source_item_demands,
            source_allocations=self._source_item_allocations,
            bought_allocations=self._allocations,
            order_item_repo=self._order_items,
            reconciler=self._reconciler,
        )
        await _publish_lines_to_settle(
            self._bus,
            self._parent_orders,
            lot,
            actor,
            ended="canceled",
            open_lines=[*left_open, *settled.open_lines],
            canceled_lines=[],
        )

        bump_edit_version(lot)
        lot.canceled_at = now
        lot.held_at = None
        lot.changed = now
        note = f" Reason: {cmd.reason}" if cmd.reason else ""
        lot.changes = append_changelog(lot.changes, actor.full_name, f"Lot canceled.{note}")
        saved = await self._lots.save(lot)
        await self._lots.record_event(
            build_lot_event(
                saved.id, actor, LotEventType.LOT_CANCELED, "lot", f"Lot canceled.{note}"
            )
        )
        await _record_left_over(self._lots, lot, settled, actor, "canceled")
        self._reconciler.touch_lots([saved.id])
        return saved


class CompleteLot:
    """Force-completes a lot by closing it short at what it produced, see
    the module docstring."""

    def __init__(
        self,
        lot_repo: IProductionLotRepository,
        order_repo: IProductionOrderRepository,
        order_item_repo: IOrderItemRepository,
        *,
        event_bus: IEventBus,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
        interruption_repo: IProductionOrderInterruptionRepository,
        parent_order_repo: IOrderRepository,
        made_item_demand_repo: IMadeItemDemandItemRepository,
        made_item_allocation_repo: IMadeItemAllocationRepository,
        source_item_demand_repo: ISourceItemDemandRepository,
        source_item_allocation_repo: ISourceItemAllocationRepository,
        bought_allocation_repo: IBoughtItemAllocationRepository,
        recompute_schedule: RecomputeMachineSchedule | None = None,
        project_repo: IProjectQueries | None = None,
    ) -> None:
        self._recompute = recompute_schedule
        self._projects = project_repo
        self._lots = lot_repo
        self._orders = order_repo
        self._order_items = order_item_repo
        self._bus = event_bus
        self._uow = uow
        self._reconciler = reconciler
        self._interruptions = interruption_repo
        self._parent_orders = parent_order_repo
        self._made_item_demands = made_item_demand_repo
        self._made_item_allocations = made_item_allocation_repo
        self._source_item_demands = source_item_demand_repo
        self._source_item_allocations = source_item_allocation_repo
        self._bought_allocations = bought_allocation_repo

    async def execute(self, actor: User, lot_id: int, cmd: CompleteLotCommand) -> LotResult:
        # Locked for the cascade, as in CancelLot.
        lot = await locked_lot(self._reconciler, self._lots, lot_id)
        LotRules.assert_can_update(actor, lot)
        assert_lot_action(LifecycleAction.FORCE_COMPLETE, lot, actor)
        assert_edit_version(lot, cmd.expected_edit_version, what=f"Lot #{lot.id}")
        await self._reconciler.lock_touched(
            also=(
                await lot_work_lock_targets(self._reconciler, lot, self._orders, self._order_items)
            ).union(await _budget_order_locks(self._projects, self._lots, self._orders, lot))
        )

        now = now_utc()
        original_quantity = lot.quantity
        dropped = dropped_wip(lot)
        for position in close_lot_short(lot):
            position.changed = now
            position.changes = append_changelog(
                position.changes,
                actor.full_name,
                f"Closed short at {position.quantity:.3f}, lot force-completed.",
            )
            await self._lots.save_position(position)
        canceled_lines = await close_live_work_short(
            lot,
            lot.positions,
            actor,
            now,
            reason=f"lot {lot.lot_number!r} was force-completed",
            lot_repo=self._lots,
            order_repo=self._orders,
            order_item_repo=self._order_items,
            parent_order_repo=self._parent_orders,
            interruption_repo=self._interruptions,
            reconciler=self._reconciler,
        )
        allocated_before = {
            a.demand_item_id: a.quantity
            for a in await self._made_item_allocations.get_by_lot_id(lot.id)
        }
        made_demand_ids = await reallocate_lot_coverage(
            lot=lot,
            made_item_demand_repo=self._made_item_demands,
            made_item_allocation_repo=self._made_item_allocations,
        )
        allocated_after = {
            a.demand_item_id: a.quantity
            for a in await self._made_item_allocations.get_by_lot_id(lot.id)
        }
        cut_demand_ids = sorted(
            demand_id
            for demand_id, quantity in allocated_before.items()
            if quantity_gt(quantity, allocated_after.get(demand_id, 0.0))
        )
        settled = await self._settle_input_demand(actor, lot, now)
        await _publish_lines_to_settle(
            self._bus,
            self._parent_orders,
            lot,
            actor,
            ended="force_completed",
            open_lines=settled.open_lines,
            canceled_lines=canceled_lines,
        )

        bump_edit_version(lot)
        lot.force_completed_at = now
        lot.held_at = None
        lot.changed = now
        note = f" Reason: {cmd.reason}" if cmd.reason else ""
        summary = (
            f"Lot force-completed at {lot.quantity:.3f} of {original_quantity:.3f} piece(s).{note}"
        )
        lot.changes = append_changelog(lot.changes, actor.full_name, summary)
        saved = await self._lots.save(lot)
        await self._lots.record_event(
            build_lot_event(
                saved.id,
                actor,
                LotEventType.LOT_COMPLETED,
                "lot",
                summary,
                payload={"quantity": lot.quantity, "original_quantity": original_quantity},
            )
        )
        for position, pieces in dropped:
            await self._lots.record_event(
                build_lot_event(
                    saved.id,
                    actor,
                    LotEventType.WIP_DROPPED,
                    "position",
                    f"{pieces:g} piece(s) finished at position {position.sequence} did not reach "
                    "the next position and were dropped when the lot was force-completed.",
                    entity_id=position.id,
                    payload={"position_sequence": position.sequence, "pieces": pieces},
                )
            )
        await _record_left_over(self._lots, lot, settled, actor, "force-completed")
        if cut_demand_ids:
            await self._bus.publish(
                LotEndedShort(
                    lot_id=saved.id,
                    lot_number=saved.lot_number,
                    quantity=lot.quantity,
                    original_quantity=original_quantity,
                    demand_ids=cut_demand_ids,
                    actor_id=actor.id,
                )
            )
        self._reconciler.touch_lots([saved.id])
        self._reconciler.touch_demands(LifecycleAggregate.MADE_DEMANDS, made_demand_ids)
        await self._reconciler.run(actor, now)
        # The lot closed at a smaller quantity, after every lifecycle row lock.
        await recompute_time_budgets_of_projects(
            [lot.project_id],
            self._projects,
            self._lots,
            BudgetOrders(self._orders, self._reconciler.lock_plan),
        )
        completed = await _reconciled_lot(self._lots, lot_id)

        await self._uow.commit()
        # The lot's closed orders free their places in the queues.
        await recompute_schedule_after_commit(
            self._recompute, after=f"force-completing lot #{lot_id}; the close is committed."
        )
        log.info(f"Force-completed lot {completed.lot_number!r}.")
        return LotMapper.to_result(completed)

    async def _settle_input_demand(
        self, actor: User, lot: ProductionLot, now: datetime
    ) -> InputSettlement:
        """Settles the lot's raw material demand."""
        return await settle_input_demand(
            lot,
            actor,
            now,
            reason=f"lot {lot.lot_number!r} was force-completed",
            source_item_demands=self._source_item_demands,
            source_allocations=self._source_item_allocations,
            bought_allocations=self._bought_allocations,
            order_item_repo=self._order_items,
            reconciler=self._reconciler,
        )


async def _record_left_over(
    lots: IProductionLotRepository,
    lot: ProductionLot,
    settled: InputSettlement,
    actor: User,
    ended: str,
) -> None:
    """Records the raw material that arrived for the lot and was not used,
    when the settled demand counts pieces."""
    if not settled.fulfilled:
        return
    unused = unused_raw_material(lot, settled.arrived, settled.unit)
    if not quantity_gt(unused, 0.0):
        return
    await lots.record_event(
        build_lot_event(
            lot.id,
            actor,
            LotEventType.RAW_MATERIAL_LEFT_OVER,
            "lot",
            f"{unused:g} {settled.unit} of raw material arrived and was not used when the lot "
            f"was {ended}.",
            payload={"quantity": unused, "unit": settled.unit},
        )
    )


async def _publish_lines_to_settle(
    bus: IEventBus,
    parent_orders: IOrderRepository,
    lot: ProductionLot,
    actor: User,
    *,
    ended: str,
    open_lines: list[OrderItem],
    canceled_lines: list[OrderItem],
) -> None:
    """Tells purchasing which supplier lines the ended lot left to settle
    (lines_to_settle_event)."""
    event = await lines_to_settle_event(
        parent_orders,
        lot,
        actor,
        ended=ended,
        open_lines=open_lines,
        canceled_lines=canceled_lines,
    )
    if event is not None:
        await bus.publish(event)


async def _orders_of_internal_positions(
    order_repo: IProductionOrderRepository, lot: ProductionLot
) -> list[ProductionOrder]:
    """The production orders of the lot's internal and mixed positions, the
    ones a hold pauses; an external position's work cannot be paused."""
    rank = {
        position.id: index
        for index, position in enumerate(lot.positions)
        if position.kind in (LotPositionKind.INTERNAL, LotPositionKind.MIXED)
    }
    if not rank:
        return []
    orders = await order_repo.get_by_lot_position_ids(sorted(rank))
    return sorted(orders, key=lambda o: (rank[o.lot_position_id], o.id))


def _open_lot_hold(order: ProductionOrder) -> bool:
    return any(
        i.resumed_at is None and i.reason == InterruptionReason.LOT_HOLD
        for i in order.interruptions
    )


class HoldLot:
    """Puts a lot on hold and pauses its running orders, each by an
    interruption whose reason is the hold, so the lot's resume ends exactly
    those."""

    def __init__(
        self,
        lot_repo: IProductionLotRepository,
        order_repo: IProductionOrderRepository,
        recompute_schedule: RecomputeMachineSchedule | None = None,
        *,
        event_bus: IEventBus,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
        interruption_repo: IProductionOrderInterruptionRepository,
    ) -> None:
        self._lots = lot_repo
        self._orders = order_repo
        self._recompute = recompute_schedule
        self._bus = event_bus
        self._uow = uow
        self._reconciler = reconciler
        self._interruptions = interruption_repo

    async def execute(self, actor: User, lot_id: int, cmd: HoldLotCommand) -> LotResult:
        # The lot first, then its running orders, each read again under its
        # lock before it is paused.
        lot = await locked_lot(self._reconciler, self._lots, lot_id)
        LotRules.assert_can_update(actor, lot)
        assert_lot_action(LifecycleAction.HOLD, lot, actor)
        orders = await _orders_of_internal_positions(self._orders, lot)
        touched_machine_ids: set[int | None] = {o.machine_id for o in orders}
        running = [o.id for o in orders if o.status == ProductionOrderStatus.IN_PROGRESS]
        self._reconciler.touch_lots([lot.id])
        self._reconciler.touch_production_orders(running)
        await self._reconciler.lock_touched()

        now = now_utc()
        paused = await self._pause(running, lot, actor, now) if running else []

        lot.held_at = now
        lot.changed = now
        lot.changes = append_changelog(
            lot.changes, actor.full_name, f"Lot put on hold. Reason: {cmd.reason}"
        )
        await self._lots.save(lot)
        await self._lots.record_event(
            build_lot_event(
                lot.id,
                actor,
                LotEventType.LOT_HELD,
                "lot",
                f"Lot put on hold. Reason: {cmd.reason}",
            )
        )
        await self._reconciler.run(actor, now)
        held = await _reconciled_lot(self._lots, lot_id)

        await self._bus.publish(
            LotOnHold(
                lot_id=held.id,
                lot_number=held.lot_number,
                actor_id=actor.id,
                creator_id=held.creator_id,
            )
        )
        for order in paused:
            await self._bus.publish(
                ProductionOrderPaused(production_order_id=order.id, actor_id=actor.id)
            )

        await self._uow.commit()

        if touched_machine_ids:
            await recompute_schedule_after_commit(
                self._recompute,
                after=(
                    f"putting lot #{lot_id} on hold; "
                    f"the hold itself is committed and its event is published."
                ),
            )

        log.info(f"Put lot {held.lot_number!r} on hold: {cmd.reason}")
        return LotMapper.to_result(held)

    async def _pause(
        self, order_ids: list[int], lot: ProductionLot, actor: User, now: datetime
    ) -> list[ProductionOrder]:
        """Opens an interruption of the hold on every order still running
        under its lock; the reconciler then derives PAUSED."""
        paused: list[ProductionOrder] = []
        for order in await self._orders.get_by_ids(order_ids, refresh=True):
            if order.status != ProductionOrderStatus.IN_PROGRESS:
                continue
            order.changed = now
            order.changes = append_changelog(
                order.changes, actor.full_name, f"Paused, lot {lot.lot_number!r} put on hold."
            )
            await self._orders.save(order)
            await self._interruptions.add(
                ProductionOrderInterruption(
                    id=0,
                    production_order_id=order.id,
                    paused_at=now,
                    resumed_at=None,
                    paused_by_id=actor.id,
                    resumed_by_id=None,
                    created=now,
                    reason=InterruptionReason.LOT_HOLD,
                    # A hold is no one's work at the machine; a personal
                    # account answers for it, a shared one names no one.
                    paused_operator_id=None if actor.is_shared_account else actor.id,
                )
            )
            paused.append(order)
        return paused


class ResumeLot:
    """Takes a lot off hold and ends the interruptions its hold opened, so
    exactly the orders the hold paused go back to work; an order an operator
    paused by hand stays paused."""

    def __init__(
        self,
        lot_repo: IProductionLotRepository,
        order_repo: IProductionOrderRepository,
        recompute_schedule: RecomputeMachineSchedule | None = None,
        *,
        event_bus: IEventBus,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
        interruption_repo: IProductionOrderInterruptionRepository,
    ) -> None:
        self._lots = lot_repo
        self._orders = order_repo
        self._recompute = recompute_schedule
        self._bus = event_bus
        self._uow = uow
        self._reconciler = reconciler
        self._interruptions = interruption_repo

    async def execute(self, actor: User, lot_id: int) -> LotResult:
        # The lot first, then the orders its hold paused, each read again
        # under its lock before it is resumed.
        lot = await locked_lot(self._reconciler, self._lots, lot_id)
        LotRules.assert_can_update(actor, lot)
        assert_lot_action(LifecycleAction.RESUME, lot, actor)
        orders = await _orders_of_internal_positions(self._orders, lot)
        touched_machine_ids: set[int | None] = {o.machine_id for o in orders}
        held = [o.id for o in orders if _open_lot_hold(o)]
        self._reconciler.touch_lots([lot.id])
        self._reconciler.touch_production_orders(held)
        await self._reconciler.lock_touched()

        now = now_utc()
        resumed = await self._resume(held, lot, actor, now) if held else []

        lot.held_at = None
        lot.changed = now
        lot.changes = append_changelog(lot.changes, actor.full_name, "Lot resumed from hold.")
        await self._lots.save(lot)
        await self._lots.record_event(
            build_lot_event(
                lot.id, actor, LotEventType.LOT_RESUMED, "lot", "Lot resumed from hold."
            )
        )
        await self._reconciler.run(actor, now)
        back = await _reconciled_lot(self._lots, lot_id)

        await self._bus.publish(
            LotResumed(
                lot_id=back.id,
                lot_number=back.lot_number,
                actor_id=actor.id,
                creator_id=back.creator_id,
            )
        )
        for order in resumed:
            await self._bus.publish(
                ProductionOrderResumed(
                    production_order_id=order.id, actor_id=actor.id, machine_id=order.machine_id
                )
            )

        await self._uow.commit()

        if touched_machine_ids:
            await recompute_schedule_after_commit(
                self._recompute,
                after=(
                    f"resuming lot #{lot_id}; the "
                    f"resume itself is committed and its event is published."
                ),
            )

        log.info(f"Resumed lot {back.lot_number!r}.")
        return LotMapper.to_result(back)

    async def _resume(
        self, order_ids: list[int], lot: ProductionLot, actor: User, now: datetime
    ) -> list[ProductionOrder]:
        """Closes the interruption of the hold on every order that still has it
        open under its lock, and returns those orders, which go back to work
        because an order has at most one open interruption; the reconciler
        then derives their status."""
        resumed: list[ProductionOrder] = []
        for order in await self._orders.get_by_ids(order_ids, refresh=True):
            if not _open_lot_hold(order):
                continue
            await self._interruptions.close_open(
                order.id,
                now,
                actor.id,
                ended_by=InterruptionEndedBy.RESUME,
                reason=InterruptionReason.LOT_HOLD,
            )
            order.changed = now
            order.changes = append_changelog(
                order.changes, actor.full_name, f"Resumed, lot {lot.lot_number!r} taken off hold."
            )
            await self._orders.save(order)
            resumed.append(order)
        return resumed
