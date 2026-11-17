"""
Updates order fields (note, expected delivery date, storage place, supplier) and optionally
propagates the expected delivery date to the order's open lines, with a schedule recompute.

The order is locked first and its lines are read and locked under that lock,
so no line can be added or ordered between the check and the write. A
supplier change carries to the lines that named the old supplier and is
refused once a line was ordered, since that line is already with the old
supplier; a line given its own supplier keeps it. The delivery date reaches
only the lines still waiting for goods (not delivered, not canceled), and
only when the request sends a date.
"""

from collections.abc import Collection
from datetime import datetime

from src.modules.catalogue.domain.errors import SupplierNotFoundError
from src.modules.catalogue.ports.outbound.catalogue_queries import ISupplierQueries
from src.modules.fulfillment.application.dto.order_dto import OrderResult
from src.modules.fulfillment.application.dto.order_dto import UpdateOrderCommand
from src.modules.fulfillment.application.mappers.order_mapper import OrderMapper
from src.modules.fulfillment.application.services.lifecycle_loader import AggregateIds
from src.modules.fulfillment.application.services.lifecycle_lock_plan import LockPlan
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.use_cases.order._lines import close_line_short
from src.modules.fulfillment.application.use_cases.order._lines import lots_of_made_lines
from src.modules.fulfillment.application.use_cases.order._lines import release_line_allocations
from src.modules.fulfillment.application.use_cases.order.mark_order_item_ordered import (
    record_ordered,
)
from src.modules.fulfillment.application.use_cases.order.mark_order_item_ordered import (
    record_requested,
)
from src.modules.fulfillment.application.use_cases.production_schedule.recompute_machine_schedule import (
    RecomputeMachineSchedule,
)
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.errors import OrderNotFoundError
from src.modules.fulfillment.domain.events.order_events import OrderCanceled
from src.modules.fulfillment.domain.events.order_events import OrderRequested
from src.modules.fulfillment.domain.events.order_events import OrderSubmitted
from src.modules.fulfillment.domain.services.order_item_mark_rules import MARK_ORDERED_SOURCES
from src.modules.fulfillment.domain.services.order_item_mark_rules import MARK_REQUESTED_SOURCES
from src.modules.fulfillment.domain.services.order_rules import OrderRules
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import IOrderRepository
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemAllocationRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.services.schedule_recompute_port import (
    recompute_schedule_after_commit,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import ConcurrentModificationError
from src.modules.platform.domain.services.edit_version import assert_edit_version
from src.modules.platform.domain.services.edit_version import bump_edit_version
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.changelog_service import append_field_changes
from src.shared_kernel.domain.services.clock import now_utc


class UpdateOrder:
    def __init__(
        self,
        order_repo: IOrderRepository,
        order_item_repo: IOrderItemRepository,
        supplier_repo: ISupplierQueries,
        recompute_schedule: RecomputeMachineSchedule | None = None,
        *,
        uow: IUnitOfWork,
        lock_plan: LockPlan | None = None,
    ) -> None:
        self._orders = order_repo
        self._order_items = order_item_repo
        self._suppliers = supplier_repo
        self._recompute = recompute_schedule
        self._uow = uow
        self._lock_plan = lock_plan

    async def execute(self, actor: User, order_id: int, cmd: UpdateOrderCommand) -> OrderResult:
        if self._lock_plan is not None:
            # The order is locked first; its lines are read under that lock,
            # so none can be added in between, and then locked themselves.
            await self._lock_plan.acquire(AggregateIds.of({LifecycleAggregate.ORDERS: [order_id]}))
            line_ids = [line.id for line in await self._order_items.get_by_order_id(order_id)]
            await self._lock_plan.acquire(
                AggregateIds.of({LifecycleAggregate.ORDER_ITEMS: line_ids})
            )
        lines = await self._order_items.get_by_order_id(order_id)
        order = found_or_raise(
            await self._orders.get_by_id(order_id),
            OrderNotFoundError,
            f"Order #{order_id} not found.",
        )

        OrderRules.assert_can_update(actor, order)
        OrderRules.assert_header_editable(order)
        assert_edit_version(order, cmd.expected_edit_version, what=f"Order #{order.id}")

        now = now_utc()
        provided = cmd.model_fields_set
        before = _logged_fields(order)
        bump_edit_version(order)
        if "note" in provided:
            order.note = cmd.note
        if "expected_delivery_date" in provided:
            order.expected_delivery_date = cmd.expected_delivery_date
        if "storage_place" in provided:
            order.storage_place = cmd.storage_place
        order.changed = now

        moved_lines: list[OrderItem] = []
        if cmd.supplier_id is not None and cmd.supplier_id != order.supplier_id:
            moved_lines = await self._change_supplier(actor, order, lines, cmd.supplier_id, now)

        order.changes = append_field_changes(
            order.changes, actor.full_name, before, _logged_fields(order)
        )
        saved = await self._orders.save(order)

        dated = cmd.update_items_delivery_date and "expected_delivery_date" in provided
        for line in lines:
            follows_date = dated and OrderRules.awaits_goods(line)
            if follows_date:
                if line not in moved_lines:
                    bump_edit_version(line)
                line.changes = append_field_changes(
                    line.changes,
                    actor.full_name,
                    {"expected_delivery_date": line.expected_delivery_date},
                    {"expected_delivery_date": cmd.expected_delivery_date},
                )
                line.expected_delivery_date = cmd.expected_delivery_date
                line.changed = now
            if follows_date or line in moved_lines:
                await self._order_items.save(line)

        await self._uow.commit()

        # A bulk expected_delivery_date change on every item is the same
        # material-readiness input UpdateOrderItem's own single-item edit
        # feeds into resolve_material_ready_at, so it needs the same
        # post-commit recompute, but only when that branch actually ran.
        if dated:
            await recompute_schedule_after_commit(
                self._recompute,
                after=(
                    f"updating order #{order_id}'s items' "
                    f"delivery dates; the update itself is committed."
                ),
            )

        return OrderMapper.to_result(saved)

    async def _change_supplier(
        self,
        actor: User,
        order: Order,
        lines: list[OrderItem],
        supplier_id: int,
        now: datetime,
    ) -> list[OrderItem]:
        """Moves the order and its live lines of the old supplier to the new
        one and returns those lines."""
        OrderRules.assert_supplier_changeable(order, lines)
        supplier = found_or_raise(
            await self._suppliers.get_by_id(supplier_id),
            SupplierNotFoundError,
            f"Supplier #{supplier_id} not found.",
        )
        old_supplier_id = order.supplier_id
        order.supplier_id = supplier.id
        order.supplier_name = supplier.name
        moved_lines = [
            line
            for line in lines
            if line.supplier_id == old_supplier_id and line.canceled_at is None
        ]
        for line in moved_lines:
            bump_edit_version(line)
            line.supplier_id = supplier.id
            line.changed = now
            line.changes = append_changelog(
                line.changes, actor.full_name, f"Supplier changed to {supplier.name}."
            )
        return moved_lines


async def _order_of(orders: IOrderRepository, order_id: int) -> Order:
    return found_or_raise(
        await orders.get_by_id(order_id), OrderNotFoundError, f"Order #{order_id} not found."
    )


async def _assert_no_line_added(
    order_items: IOrderItemRepository,
    order_id: int,
    locked_ids: set[int],
    sources: Collection[str],
    action: str,
) -> None:
    """A line added to or moved into the order between the unlocked read and
    the locks was not locked, and the order would be placed while it stays
    behind; the order's lock keeps any further line out, so a retry takes
    every line."""
    if any(
        item.id not in locked_ids and item.status in sources
        for item in await order_items.get_by_order_id(order_id)
    ):
        raise ConcurrentModificationError(
            f"Order #{order_id} gained a line while it was being {action}. Reload and try again."
        )


class SubmitOrder:
    """Places a DRAFT or REQUESTED order: stamps its ordered_date and marks
    every PENDING or REQUESTED line ordered. The lifecycle reconciler derives
    the statuses of the order, the lines and the demands allocated to
    them."""

    def __init__(
        self,
        order_repo: IOrderRepository,
        *,
        event_bus: IEventBus,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
        order_item_repo: IOrderItemRepository,
    ) -> None:
        self._orders = order_repo
        self._order_items = order_item_repo
        self._bus = event_bus
        self._uow = uow
        self._reconciler = reconciler

    async def execute(self, actor: User, order_id: int) -> OrderResult:
        order = await _order_of(self._orders, order_id)
        OrderRules.assert_can_submit(actor, order)

        lines = [
            item
            for item in await self._order_items.get_by_order_id(order_id)
            if item.status in MARK_ORDERED_SOURCES
        ]
        self._reconciler.touch_orders([order_id])
        self._reconciler.touch_order_items([item.id for item in lines])
        await self._reconciler.lock_touched(also=lots_of_made_lines(lines))
        order = await _order_of(self._orders, order_id)
        OrderRules.assert_can_submit(actor, order)
        await _assert_no_line_added(
            self._order_items,
            order_id,
            {item.id for item in lines},
            MARK_ORDERED_SOURCES,
            "submitted",
        )

        now = now_utc()
        order.ordered_date = now
        order.changed = now
        order.changes = append_changelog(
            order.changes, actor.full_name, f"Order submitted on {now:%Y-%m-%d}."
        )
        saved = await self._orders.save(order)

        locked = {item.id for item in lines}
        marked: list[int] = []
        for item in await self._order_items.get_by_order_id(order_id):
            if item.id not in locked or item.status not in MARK_ORDERED_SOURCES:
                continue
            record_ordered(item, actor, now, f"Marked as ordered: order #{order_id} was submitted.")
            await self._order_items.save(item)
            marked.append(item.id)

        await self._reconciler.run(actor, now, reason=f"order #{order_id} submitted")

        await self._bus.publish(
            OrderSubmitted(
                order_id=saved.id,
                order_number=saved.order_number,
                actor_id=actor.id,
                supplier_id=saved.supplier_id,
            )
        )
        await self._uow.commit()

        log.info(
            f"Submitted order {saved.order_number!r}, ID={saved.id}, "
            f"marking {len(marked)} item(s) as ordered."
        )
        return OrderMapper.to_result(await _order_of(self._orders, order_id))


class RequestOrder:
    """Sends a price request for a DRAFT order: stamps its requested_at and
    marks every PENDING line requested. The lifecycle reconciler derives the
    order's and the lines' statuses."""

    def __init__(
        self,
        order_repo: IOrderRepository,
        *,
        event_bus: IEventBus,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
        order_item_repo: IOrderItemRepository,
    ) -> None:
        self._orders = order_repo
        self._order_items = order_item_repo
        self._bus = event_bus
        self._uow = uow
        self._reconciler = reconciler

    async def execute(self, actor: User, order_id: int) -> OrderResult:
        order = await _order_of(self._orders, order_id)
        OrderRules.assert_can_request(actor, order)

        lines = [
            item.id
            for item in await self._order_items.get_by_order_id(order_id)
            if item.status in MARK_REQUESTED_SOURCES
        ]
        self._reconciler.touch_orders([order_id])
        self._reconciler.touch_order_items(lines)
        await self._reconciler.lock_touched()
        order = await _order_of(self._orders, order_id)
        OrderRules.assert_can_request(actor, order)
        await _assert_no_line_added(
            self._order_items, order_id, set(lines), MARK_REQUESTED_SOURCES, "requested"
        )

        now = now_utc()
        order.requested_at = now
        order.changed = now
        order.changes = append_changelog(
            order.changes, actor.full_name, f"Order requested on {now:%Y-%m-%d}."
        )
        saved = await self._orders.save(order)

        marked = 0
        for item in await self._order_items.get_by_order_id(order_id):
            if item.id not in lines or item.status not in MARK_REQUESTED_SOURCES:
                continue
            record_requested(
                item, actor, now, f"Marked as requested: order #{order_id} was requested."
            )
            await self._order_items.save(item)
            marked += 1

        await self._reconciler.run(actor, now, reason=f"order #{order_id} requested")

        await self._bus.publish(
            OrderRequested(
                order_id=saved.id,
                order_number=saved.order_number,
                actor_id=actor.id,
                supplier_id=saved.supplier_id,
            )
        )
        await self._uow.commit()

        log.info(
            f"Requested order {saved.order_number!r}, ID={saved.id}, "
            f"marking {marked} item(s) as requested."
        )
        return OrderMapper.to_result(await _order_of(self._orders, order_id))


class CancelOrder:
    """
    Cancels an order: stamps its canceled_at and settles every line that is
    still open. A line that has received nothing yet is canceled, releasing
    its allocations whatever their demands' status. A line on which pieces
    were delivered or lost is closed short at those pieces, its allocations
    scaled down to them as closing it short by itself does
    (close_order_item_short.py). A delivered line keeps its quantity and
    allocations, so that demand delivery summaries stay accurate. Demands
    whose allocations changed are reset to OPEN (or ALLOCATED/ORDERED if
    other allocations remain); a fulfilled or canceled demand keeps its
    status. The lifecycle reconciler derives the statuses of the order and
    its lines; the order derives CANCELED, because its canceled_at wins.
    """

    def __init__(
        self,
        order_repo: IOrderRepository,
        order_item_repo: IOrderItemRepository,
        allocation_repo: IBoughtItemAllocationRepository,
        recompute_schedule: RecomputeMachineSchedule | None = None,
        *,
        event_bus: IEventBus,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
        source_item_allocation_repo: ISourceItemAllocationRepository | None = None,
    ) -> None:
        self._orders = order_repo
        self._order_items = order_item_repo
        self._allocations = allocation_repo
        self._recompute = recompute_schedule
        self._bus = event_bus
        self._uow = uow
        self._reconciler = reconciler
        self._source_item_allocations = source_item_allocation_repo

    async def execute(
        self, actor: User, order_id: int, *, expected_edit_version: int | None = None
    ) -> OrderResult:
        order = await _order_of(self._orders, order_id)
        OrderRules.assert_can_cancel(actor, order)

        # The order's lock serializes every other writer of its lines, which
        # all take it first; the lines this cancel writes are locked too,
        # after the lots their MADE lines supply, as the one lock order has it.
        settled = [
            item
            for item in await self._order_items.get_by_order_id(order_id)
            if OrderRules.can_cancel_line(order, item)
            or OrderRules.can_close_line_short(order, item)
        ]
        self._reconciler.touch_orders([order_id])
        self._reconciler.touch_order_items([item.id for item in settled])
        await self._reconciler.lock_touched(also=lots_of_made_lines(settled))
        order = await _order_of(self._orders, order_id)
        OrderRules.assert_can_cancel(actor, order)
        assert_edit_version(order, expected_edit_version, what=f"Order #{order.id}")
        # A line added to or moved into the order between the unlocked read
        # and the locks was not locked and would stay live on the canceled
        # order; the order's lock keeps any further line out, so a retry
        # settles every line.
        locked_ids = {item.id for item in settled}
        if any(
            item.id not in locked_ids
            and (
                OrderRules.can_cancel_line(order, item)
                or OrderRules.can_close_line_short(order, item)
            )
            for item in await self._order_items.get_by_order_id(order_id)
        ):
            raise ConcurrentModificationError(
                f"Order #{order_id} gained a line while it was being canceled. "
                "Reload and try again."
            )

        now = now_utc()
        bump_edit_version(order)
        order.canceled_at = now
        order.changed = now
        order.changes = append_changelog(
            order.changes, actor.full_name, f"Order canceled on {now:%Y-%m-%d}."
        )
        saved = await self._orders.save(order)

        affected_demand_ids, affected_source_item_demand_ids = await self._settle_lines(
            order, {item.id for item in settled}, actor, now
        )
        self._reconciler.touch_demands(LifecycleAggregate.BOUGHT_DEMANDS, affected_demand_ids)
        self._reconciler.touch_demands(
            LifecycleAggregate.SOURCE_DEMANDS, affected_source_item_demand_ids
        )

        await self._reconciler.run(actor, now, reason=f"order #{order_id} canceled")

        # Staged in the same transaction as the cancel cascade
        # (see event_outbox.py): publish before commit, always.
        await self._bus.publish(
            OrderCanceled(
                order_id=saved.id,
                order_number=saved.order_number,
                actor_id=actor.id,
                supplier_id=saved.supplier_id,
                creator_id=saved.creator_id,
            )
        )

        await self._uow.commit()

        await recompute_schedule_after_commit(
            self._recompute,
            after=(f"canceling order #{order_id}; the cancellation itself is committed."),
        )

        log.info(
            f"Canceled order {saved.order_number!r}, ID={saved.id}. "
            f"Deallocated {len(affected_demand_ids)} demand(s)."
        )
        return OrderMapper.to_result(await _order_of(self._orders, order_id))

    async def _settle_lines(
        self, order: Order, locked: set[int], actor: User, now: datetime
    ) -> tuple[set[int], set[int]]:
        """Cancels each locked line on which nothing was delivered or lost,
        releasing every allocation on it, and closes each locked line that
        received pieces short, by the order item intent table, see this
        class's own docstring. Returns the bought-item and source-item
        demand ids whose allocations changed, for the caller to touch."""
        affected_demand_ids: set[int] = set()
        affected_source_item_demand_ids: set[int] = set()
        for item in await self._order_items.get_by_order_id(order.id):
            if item.id not in locked:
                continue
            if OrderRules.can_cancel_line(order, item):
                bought_ids, source_ids = await release_line_allocations(
                    item, self._allocations, self._source_item_allocations
                )
                bump_edit_version(item)
                item.canceled_at = now
                item.changed = now
                item.changes = append_changelog(
                    item.changes, actor.full_name, f"Canceled: order #{order.id} was canceled."
                )
                await self._order_items.save(item)
            elif OrderRules.can_close_line_short(order, item):
                bought_ids, source_ids = await close_line_short(
                    item,
                    actor,
                    now,
                    cause=f"order #{order.id} was canceled",
                    order_items=self._order_items,
                    bought_allocations=self._allocations,
                    source_allocations=self._source_item_allocations,
                )
            else:
                continue
            affected_demand_ids |= bought_ids
            affected_source_item_demand_ids |= source_ids
        return affected_demand_ids, affected_source_item_demand_ids


def _logged_fields(order: Order) -> dict[str, object]:
    """The order's editable fields, whose changes its changelog names."""
    return {
        "note": order.note,
        "expected_delivery_date": order.expected_delivery_date,
        "storage_place": order.storage_place,
        "supplier_id": order.supplier_id,
    }
