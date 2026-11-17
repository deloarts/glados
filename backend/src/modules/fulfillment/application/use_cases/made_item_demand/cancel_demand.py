"""
Canceling a made-item demand is never a lone status flip: the lots built
to fulfill it, those lots' raw-material demands, and the production
orders / supplier order items their positions were committed to all exist
solely because the demand did. Leaving them running would keep machines
and suppliers busy producing parts nobody asked for any more.

PreviewCancelMadeItemDemand answers "what exactly goes away?" without
touching anything, the confirmation dialog's payload. CancelMadeItemDemand
performs the cascade, driving each doomed lot through CancelLot's existing
force-cancel (which already handles positions, production orders, order
items, deallocation and the lot's source item demand), releases the
demand's stock allocation and records the demand's canceled_at. It locks
every lot of the impact first, then every row the lot cancels may write
together with the demand, and runs the lifecycle reconciler it shares with
CancelLot once, which derives the statuses of the canceled production
orders, order lines, lots and the demand and publishes their events, before
it publishes its own LotCanceled events and commits. Who may cancel is
decided by assert_can_change_demand_status, the rule all three demand
families share, which `execute` applies for the cancel route and the status
route has applied before it calls `execute_permitted`. A fulfilled or
already canceled demand is refused with the same errors as in the bought
family.

Both share one collector, so the dialog can never promise something
different from what the cancel actually does.

A lot allocated to several demands survives the cancelation of one of
them: it is still owed to the others. Only its allocation to THIS demand
goes away, which CancelLot would not do on its own, see _release_lot. A lot
the cancel would cancel that already made good pieces refuses its cancel,
which only force-complete keeps them through, so the whole demand cancel is
refused; the preview marks such a lot (cancel_refused), so the dialog never
offers what the cancel then refuses.
"""

from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.application.dto.made_item_demand_dto import CancelImpactLotResult
from src.modules.fulfillment.application.dto.made_item_demand_dto import CancelImpactOrderItemResult
from src.modules.fulfillment.application.dto.made_item_demand_dto import (
    CancelImpactProductionOrderResult,
)
from src.modules.fulfillment.application.dto.made_item_demand_dto import (
    CancelImpactSourceItemDemandResult,
)
from src.modules.fulfillment.application.dto.made_item_demand_dto import (
    CancelMadeItemDemandImpactResult,
)
from src.modules.fulfillment.application.dto.made_item_demand_dto import MadeItemDemandItemResult
from src.modules.fulfillment.application.dto.production_lot_dto import CancelLotCommand
from src.modules.fulfillment.application.mappers.made_item_demand_mapper import (
    MadeItemDemandItemMapper,
)
from src.modules.fulfillment.application.services.lifecycle_loader import AggregateIds
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.use_cases._demand_family.spec import CANCEL_REASON
from src.modules.fulfillment.application.use_cases.production_lot.lot_lifecycle import CancelLot
from src.modules.fulfillment.application.use_cases.production_schedule.recompute_machine_schedule import (
    RecomputeMachineSchedule,
)
from src.modules.fulfillment.domain.entities.made_item_allocation import MadeItemDemandAllocation
from src.modules.fulfillment.domain.entities.made_item_demand_item import MadeItemDemandItem
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.source_item_demand_item import SourceItemDemandItem
from src.modules.fulfillment.domain.errors import DemandItemAlreadyCanceledError
from src.modules.fulfillment.domain.errors import DemandItemAlreadyFulfilledError
from src.modules.fulfillment.domain.errors import DemandItemNotFoundError
from src.modules.fulfillment.domain.events.lot_events import LotCanceled
from src.modules.fulfillment.domain.services.demand_status_rules import (
    assert_can_change_demand_status,
)
from src.modules.fulfillment.domain.services.demand_status_rules import assert_demand_intent
from src.modules.fulfillment.domain.services.lot_rules import line_end_action
from src.modules.fulfillment.domain.services.lot_rules import lot_context
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.lot_status import TERMINAL_LOT_STATUSES
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.production_status import (
    TERMINAL_PRODUCTION_ORDER_STATUSES,
)
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
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
from src.modules.platform.domain.exceptions import ConcurrentModificationError
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction


def _material_label(demand: SourceItemDemandItem, lot: ProductionLot) -> str:
    """Mirrors the lot mapper's _lot_source_label so the dialog names the
    raw material the same way the lot detail view does."""
    if demand.bought_item is not None:
        return demand.bought_item.article_name
    if demand.source_item is not None:
        return demand.source_item.dimension or f"Source item #{demand.source_item.id}"
    return lot.source_label


class CancelImpactCollector:
    """Builds the impact tree for canceling one made-item demand. Read-only,
    shared verbatim by the preview and the cancel so the two can never
     disagree."""

    def __init__(
        self,
        demand_repo: IMadeItemDemandItemRepository,
        allocation_repo: IMadeItemAllocationRepository,
        lot_repo: IProductionLotRepository,
        production_order_repo: IProductionOrderRepository,
        order_repo: IOrderRepository,
        order_item_repo: IOrderItemRepository,
        source_item_demand_repo: ISourceItemDemandRepository,
        source_item_allocation_repo: ISourceItemAllocationRepository,
    ) -> None:
        self._demands = demand_repo
        self._allocations = allocation_repo
        self._lots = lot_repo
        self._production_orders = production_order_repo
        self._orders = order_repo
        self._order_items = order_item_repo
        self._source_item_demands = source_item_demand_repo
        self._source_item_allocations = source_item_allocation_repo

    async def collect(
        self, actor: User, demand: MadeItemDemandItem
    ) -> CancelMadeItemDemandImpactResult:
        allocations = [
            a for a in await self._allocations.get_by_demand_item_id(demand.id) if a.lot_id
        ]
        lot_ids = sorted({a.lot_id for a in allocations if a.lot_id is not None})
        lots = {lot.id: lot for lot in await self._lots.get_by_ids(lot_ids)}

        order_number_cache: dict[int, str] = {}
        lot_impacts = [
            await self._lot_impact(lots[lot_id], demand, allocations, order_number_cache)
            for lot_id in lot_ids
            if lot_id in lots
        ]

        return CancelMadeItemDemandImpactResult(
            demand_item_id=demand.id,
            status=demand.status,
            quantity=demand.quantity,
            unit=demand.unit,
            item_part_number=demand.item_part_number,
            item_revision=demand.item_revision,
            item_article_name=demand.item_article_name,
            project_number=demand.project_number,
            can_cancel_lots=(
                actor.has_permission(Permission.MANAGE_LOTS)
                or not any(impact.will_cancel for impact in lot_impacts)
            ),
            lots=lot_impacts,
        )

    async def _lot_impact(
        self,
        lot: ProductionLot,
        demand: MadeItemDemandItem,
        allocations: list[MadeItemDemandAllocation],
        order_number_cache: dict[int, str],
    ) -> CancelImpactLotResult:
        allocated = sum(a.quantity for a in allocations if a.lot_id == lot.id)
        other_demand_ids = await self._live_sibling_demand_ids(lot.id, demand.id)

        will_cancel = True
        keep_reason: str | None = None
        if lot.status in TERMINAL_LOT_STATUSES:
            will_cancel = False
            keep_reason = f"lot is already {lot.status.value}"
        elif other_demand_ids:
            will_cancel = False
            keep_reason = "lot is also allocated to other open demands"

        return CancelImpactLotResult(
            lot_id=lot.id,
            lot_number=lot.lot_number,
            status=lot.status,
            quantity=lot.quantity,
            quantity_completed=lot.quantity_completed,
            allocated_quantity=allocated,
            will_cancel=will_cancel,
            # The lot's own cancel refuses a lot with good pieces, which
            # force-complete keeps, and so does this cancel then.
            cancel_refused=will_cancel and lot_context(lot).has_good_pieces,
            keep_reason=keep_reason,
            other_demand_ids=other_demand_ids,
            source_item_demand=await self._source_item_demand_impact(
                lot, will_cancel, order_number_cache
            ),
            production_orders=await self._production_order_impacts(lot, will_cancel),
            order_items=await self._order_item_impacts(lot, will_cancel, order_number_cache),
        )

    async def _live_sibling_demand_ids(self, lot_id: int, demand_id: int) -> list[int]:
        """Other demands this lot is allocated to. Demands that are
        themselves already canceled don't count, their allocation is
        stale bookkeeping, not a live claim on the lot's output."""
        sibling_ids = {
            a.demand_item_id
            for a in await self._allocations.get_by_lot_id(lot_id)
            if a.demand_item_id != demand_id
        }
        live: list[int] = []
        for sibling_id in sorted(sibling_ids):
            sibling = await self._demands.get_by_id(sibling_id)
            if sibling and sibling.status != MadeItemDemandStatus.CANCELED:
                live.append(sibling_id)
        return live

    async def _source_item_demand_impact(
        self, lot: ProductionLot, lot_will_cancel: bool, order_number_cache: dict[int, str]
    ) -> CancelImpactSourceItemDemandResult | None:
        if lot.input_demand_id is None:
            return None
        demand = await self._source_item_demands.get_by_id(lot.input_demand_id)
        if not demand:
            return None

        will_cancel = True
        keep_reason: str | None = None
        if not lot_will_cancel:
            will_cancel = False
            keep_reason = "its lot is not being canceled"
        elif demand.canceled_at is not None or demand.status == SourceItemDemandStatus.CANCELED:
            will_cancel = False
            keep_reason = "already canceled"
        elif demand.status == SourceItemDemandStatus.FULFILLED:
            will_cancel = False
            keep_reason = "material has already been delivered"

        return CancelImpactSourceItemDemandResult(
            demand_id=demand.id,
            status=demand.status,
            quantity=demand.quantity,
            unit=demand.unit,
            item_article_name=_material_label(demand, lot),
            will_cancel=will_cancel,
            keep_reason=keep_reason,
            order_items=await self._source_item_order_items(demand.id, order_number_cache),
        )

    async def _source_item_order_items(
        self, base_demand_id: int, order_number_cache: dict[int, str]
    ) -> list[CancelImpactOrderItemResult]:
        results: list[CancelImpactOrderItemResult] = []
        for allocation in await self._source_item_allocations.get_by_demand_item_id(base_demand_id):
            if allocation.order_item_id is None:
                continue
            item = await self._order_items.get_by_id(allocation.order_item_id)
            if not item:
                continue
            results.append(
                await self._order_item_result(
                    item,
                    order_number_cache,
                    will_cancel=False,
                    keep_reason="raw material already on order with the supplier",
                )
            )
        return results

    async def _production_order_impacts(
        self, lot: ProductionLot, lot_will_cancel: bool
    ) -> list[CancelImpactProductionOrderResult]:
        results: list[CancelImpactProductionOrderResult] = []
        for position in sorted(lot.positions, key=lambda p: p.sequence):
            if position.kind not in (LotPositionKind.INTERNAL, LotPositionKind.MIXED):
                continue
            for order in await self._production_orders.get_by_lot_position_id(position.id):
                will_cancel = True
                keep_reason: str | None = None
                if not lot_will_cancel:
                    will_cancel = False
                    keep_reason = "its lot is not being canceled"
                elif order.status in TERMINAL_PRODUCTION_ORDER_STATUSES:
                    will_cancel = False
                    keep_reason = f"already {order.status.value}"
                results.append(
                    CancelImpactProductionOrderResult(
                        production_order_id=order.id,
                        production_order_number=order.production_order_number,
                        status=order.status,
                        quantity=order.quantity,
                        quantity_completed=order.quantity_completed,
                        machine_id=order.machine_id,
                        machine_name=order.machine_internal_name or order.machine_pool_name,
                        lot_position_sequence=position.sequence,
                        will_cancel=will_cancel,
                        keep_reason=keep_reason,
                    )
                )
        return results

    async def _order_item_impacts(
        self, lot: ProductionLot, lot_will_cancel: bool, order_number_cache: dict[int, str]
    ) -> list[CancelImpactOrderItemResult]:
        results: list[CancelImpactOrderItemResult] = []
        for position in sorted(lot.positions, key=lambda p: p.sequence):
            if position.kind not in (LotPositionKind.EXTERNAL, LotPositionKind.MIXED):
                continue
            item = await self._order_items.get_by_lot_position_id(position.id)
            if item is None:
                continue

            will_cancel = True
            keep_reason: str | None = None
            if not lot_will_cancel:
                will_cancel = False
                keep_reason = "its lot is not being canceled"
            else:
                action = await self._line_end_action(item)
                if action is LifecycleAction.CLOSE_SHORT:
                    will_cancel = False
                    keep_reason = "closed short at the pieces already received"
                elif action is not LifecycleAction.CANCEL:
                    will_cancel = False
                    keep_reason = f"already {item.status.value}"

            results.append(
                await self._order_item_result(
                    item,
                    order_number_cache,
                    will_cancel=will_cancel,
                    keep_reason=keep_reason,
                    lot_position_sequence=position.sequence,
                )
            )
        return results

    async def _line_end_action(self, item: OrderItem) -> LifecycleAction | None:
        """How the lot cancel cascade ends the line, by the same rule
        (lot_rules.line_end_action): canceled when nothing was delivered or
        lost on it, closed short when some pieces were."""
        order = await self._orders.get_by_id(item.order_id)
        return line_end_action(item, order.status) if order is not None else None

    async def _order_item_result(
        self,
        item: OrderItem,
        order_number_cache: dict[int, str],
        *,
        will_cancel: bool,
        keep_reason: str | None,
        lot_position_sequence: int | None = None,
    ) -> CancelImpactOrderItemResult:
        return CancelImpactOrderItemResult(
            order_item_id=item.id,
            order_id=item.order_id,
            order_number=await self._order_number(item.order_id, order_number_cache),
            position=item.position,
            status=item.status,
            quantity=item.quantity,
            quantity_delivered=item.quantity_delivered,
            unit=item.unit,
            supplier_name=item.supplier_name,
            item_article_name=item.item_article_name or item.virtual_name or "",
            lot_position_sequence=lot_position_sequence,
            will_cancel=will_cancel,
            keep_reason=keep_reason,
        )

    async def _order_number(self, order_id: int, cache: dict[int, str]) -> str:
        if order_id not in cache:
            order: Order | None = await self._orders.get_by_id(order_id)
            cache[order_id] = order.order_number if order else ""
        return cache[order_id]


class PreviewCancelMadeItemDemand:
    """Read-only "what would canceling this demand take down with it?"."""

    def __init__(
        self,
        demand_repo: IMadeItemDemandItemRepository,
        collector: CancelImpactCollector,
    ) -> None:
        self._demands = demand_repo
        self._collector = collector

    async def execute(self, actor: User, demand_id: int) -> CancelMadeItemDemandImpactResult:
        demand = found_or_raise(
            await self._demands.get_by_id(demand_id),
            DemandItemNotFoundError,
            f"Demand item #{demand_id} not found.",
        )
        return await self._collector.collect(actor, demand)


class CancelMadeItemDemand:
    def __init__(
        self,
        demand_repo: IMadeItemDemandItemRepository,
        allocation_repo: IMadeItemAllocationRepository,
        lot_repo: IProductionLotRepository,
        collector: CancelImpactCollector,
        cancel_lot: CancelLot,
        recompute_schedule: RecomputeMachineSchedule | None = None,
        *,
        event_bus: IEventBus,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
    ) -> None:
        """`reconciler` is the request's lifecycle reconciler, the same one
        `cancel_lot` registers the production orders it cancels with."""
        self._demands = demand_repo
        self._allocations = allocation_repo
        self._lots = lot_repo
        self._collector = collector
        self._cancel_lot = cancel_lot
        self._recompute = recompute_schedule
        self._bus = event_bus
        self._uow = uow
        self._reconciler = reconciler

    async def execute(self, actor: User, demand_id: int) -> MadeItemDemandItemResult:
        demand = await self._read(demand_id)
        assert_can_change_demand_status(actor, demand, MadeItemDemandStatus.CANCELED)
        return await self._cancel(actor, demand)

    async def execute_permitted(self, actor: User, demand_id: int) -> MadeItemDemandItemResult:
        """The cancel for a caller that has already decided the actor may
        cancel the demand."""
        return await self._cancel(actor, await self._read(demand_id))

    async def _cancel(self, actor: User, demand: MadeItemDemandItem) -> MadeItemDemandItemResult:
        demand_id = demand.id
        self._assert_cancelable(actor, demand, has_allocations=False)

        impact = await self._collector.collect(actor, demand)
        now = now_utc()
        reason = f"made item demand #{demand.id} was canceled"

        # Every lot of the impact is locked first, in one acquisition in the
        # lock order. The second acquisition takes the rows the canceled
        # lots' cascades may write together with the demand itself and the
        # demands allocated to those lots and to the cascade's lines, which
        # all sort after them, before any of them is read.
        await self._reconciler.lock_touched(
            also=AggregateIds.of({LifecycleAggregate.LOTS: [i.lot_id for i in impact.lots]})
        )
        locked: list[tuple[ProductionLot, bool]] = []
        cascade_targets = AggregateIds()
        for lot_impact in impact.lots:
            # Locked read: this feeds the same cancel cascade
            # path as CancelLot.execute, so it needs the same lock (see
            # lot_lifecycle.CancelLot.execute and
            # IProductionLotRepository.get_by_id_for_update).
            lot = await self._lots.get_by_id_for_update(lot_impact.lot_id)
            if not lot:
                continue
            locked.append((lot, lot_impact.will_cancel))
            if lot_impact.will_cancel:
                cascade_targets = cascade_targets.union(await self._cancel_lot.lock_targets(lot))
        # The canceled lots leave their projects' time budgets, so the queued
        # and paused orders whose duration the recompute may snapshot again
        # join the acquisition.
        to_cancel = [lot for lot, will_cancel in locked if will_cancel]
        if to_cancel:
            cascade_targets = cascade_targets.union(
                await self._cancel_lot.budget_lock_targets(to_cancel)
            )
        self._reconciler.touch_lots([lot.id for lot, will_cancel in locked if will_cancel])
        self._reconciler.touch_order_items(cascade_targets.get(LifecycleAggregate.ORDER_ITEMS))
        self._reconciler.touch_demands(LifecycleAggregate.MADE_DEMANDS, [demand_id])
        await self._reconciler.lock_touched(also=cascade_targets)
        demand = await self._read(demand_id)
        self._assert_cancelable(actor, demand, has_allocations=False)
        # The impact was read before the locks; a lot linked or a share
        # changed in between would be canceled or released by what the
        # first reading decided, so the request is refused for a retry.
        if _impact_key(await self._collector.collect(actor, demand)) != _impact_key(impact):
            raise ConcurrentModificationError(
                f"The lots of made item demand #{demand_id} changed while it was being "
                "canceled. Reload and try again."
            )
        old_status = MadeItemDemandStatus(demand.status)

        canceled_lots: list[ProductionLot] = []
        for lot, will_cancel in locked:
            if will_cancel:
                # CancelLot deletes every allocation on the lot, including
                # this demand's own, no separate release needed. The
                # production orders and order lines it cancels are
                # reconciled below.
                canceled_lot = await self._cancel_lot.cancel_no_commit(
                    actor, lot, CancelLotCommand(reason=reason), now=now
                )
                canceled_lots.append(canceled_lot)
            else:
                await self._release_lot(actor, lot, demand.id)
        released_from_stock = await self._release_stock(demand.id)

        demand.canceled_at = now
        demand.changed = now
        demand.changes = append_changelog(
            demand.changes,
            actor.full_name,
            f"Canceled from {old_status.value}"
            + (f", canceling {len(canceled_lots)} lot(s)" if canceled_lots else "")
            + (", releasing its stock allocation" if released_from_stock else "")
            + ".",
        )
        saved = await self._demands.save(demand)
        await self._reconciler.run(actor, now, reason=CANCEL_REASON)
        # After every lifecycle row lock, as the time budget lock requires.
        if canceled_lots:
            await self._cancel_lot.recompute_budgets(canceled_lots)

        # Staged in the same transaction as the cascade (see event_outbox.py):
        # publish before commit, always. The demand's status event comes
        # from the reconciler.
        for lot in canceled_lots:
            await self._bus.publish(
                LotCanceled(
                    lot_id=lot.id,
                    lot_number=lot.lot_number,
                    actor_id=actor.id,
                    creator_id=lot.creator_id,
                )
            )

        await self._uow.commit()

        if canceled_lots:
            await recompute_schedule_after_commit(
                self._recompute,
                after=(
                    f"canceling made item demand #{demand_id}; "
                    f"the cancellation itself is committed and its events are published."
                ),
            )

        log.info(
            "Canceled made item demand #%s, cascading into %s lot(s): %s.",
            saved.id,
            len(canceled_lots),
            ", ".join(lot.lot_number for lot in canceled_lots) or "none",
        )
        canceled = await self._demands.get_by_id(demand_id)
        return MadeItemDemandItemMapper.to_result(canceled or saved)

    async def _read(self, demand_id: int) -> MadeItemDemandItem:
        return found_or_raise(
            await self._demands.get_by_id(demand_id),
            DemandItemNotFoundError,
            f"Demand item #{demand_id} not found.",
        )

    @staticmethod
    def _assert_cancelable(
        actor: User, demand: MadeItemDemandItem, *, has_allocations: bool
    ) -> None:
        assert_demand_intent(
            actor,
            LifecycleAction.CANCEL,
            demand,
            has_allocations=has_allocations,
            already_fulfilled_error=DemandItemAlreadyFulfilledError,
            already_canceled_error=DemandItemAlreadyCanceledError,
            noun="Demand item",
        )

    async def _release_stock(self, demand_id: int) -> bool:
        """Deletes the demand's stock allocation, so a canceled demand holds
        no allocation at all. Returns whether there was one."""
        stock = [
            a for a in await self._allocations.get_by_demand_item_id(demand_id) if a.lot_id is None
        ]
        for allocation in stock:
            await self._allocations.delete(allocation)
        return bool(stock)

    async def _release_lot(self, actor: User, lot: ProductionLot, demand_id: int) -> None:
        """A surviving lot (shared with other demands, or already
        terminal) keeps running, but this demand's claim on its output is
        gone, drop only that allocation. The lot's other demands are
        untouched: their own allocation rows, and therefore their
        coverage, don't change."""
        released = [
            a
            for a in await self._allocations.get_by_lot_id(lot.id)
            if a.demand_item_id == demand_id
        ]
        if not released:
            return
        for allocation in released:
            await self._allocations.delete(allocation)
        lot.changed = now_utc()
        lot.changes = append_changelog(
            lot.changes,
            actor.full_name,
            f"Deallocated from canceled made item demand #{demand_id}.",
        )
        await self._lots.save(lot)


def _impact_key(impact: CancelMadeItemDemandImpactResult) -> frozenset[tuple[int, bool]]:
    """What a cancel decides per lot: which lots it touches and whether it
    cancels each of them."""
    return frozenset((i.lot_id, i.will_cancel) for i in impact.lots)
