"""
Updates order item fields (quantity, unit, dates, notes, etc.) and optionally changes
bought/virtual identity; recomputes substitution allocations on identity change and
reschedules downstream machines on delivery date change. A substitute needs an item new work
may name, and a line moved to another project needs that project active, since the move puts
new work on it.

A quantity changes only while the line is pending, requested or ordered; a
line that received pieces is closed short instead (close_order_item_short.py)
and a canceled line keeps its quantity. A change is refused below the pieces
delivered or lost on the line and below what demands of both allocation
families have allocated to it, and a MADE line never grows past what its
position's production orders leave it. After an accepted change the
lifecycle reconciler derives the statuses of the line, its order and every
demand allocated to the line, because the line now covers a different share
of them. A substitution rewrites the allocations on the
line, so it is refused while one of them belongs to a fulfilled or canceled
demand.
"""

from src.modules.catalogue.domain.errors import BoughtItemNotFoundError
from src.modules.catalogue.domain.policies.bought_item_rules import BoughtItemCatalogueRules
from src.modules.catalogue.ports.outbound.catalogue_queries import IBoughtItemQueries
from src.modules.fulfillment.application.dto.order_dto import OrderItemResult
from src.modules.fulfillment.application.dto.order_dto import UpdateOrderItemCommand
from src.modules.fulfillment.application.mappers.order_mapper import OrderItemMapper
from src.modules.fulfillment.application.services.lifecycle_reconciler import DEFAULT_REASON
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.services.schedule_recompute_helpers import (
    recompute_downstream_position_machines,
)
from src.modules.fulfillment.application.use_cases.order._lines import lots_of_made_lines
from src.modules.fulfillment.application.use_cases.production_schedule.recompute_machine_schedule import (
    RecomputeMachineSchedule,
)
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.source_item_allocation import (
    SourceItemDemandAllocation,
)
from src.modules.fulfillment.domain.errors import OrderItemHoldsRawMaterialError
from src.modules.fulfillment.domain.errors import OrderItemLineTypeMismatchError
from src.modules.fulfillment.domain.errors import OrderItemNotFoundError
from src.modules.fulfillment.domain.errors import OrderNotFoundError
from src.modules.fulfillment.domain.services.allocation_coverage import recorded_substitution
from src.modules.fulfillment.domain.services.allocation_service import BoughtItemAllocationRules
from src.modules.fulfillment.domain.services.lot_rules import compute_position_remaining
from src.modules.fulfillment.domain.services.order_rules import OrderRules
from src.modules.fulfillment.domain.services.quantity_edit_rules import (
    assert_made_line_within_position,
)
from src.modules.fulfillment.domain.services.quantity_edit_rules import (
    assert_order_item_quantity_allowed,
)
from src.modules.fulfillment.domain.services.quantity_edit_rules import quantity_changed
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemDemandItemRepository,
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
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.services.schedule_recompute_port import (
    recompute_schedule_after_commit,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.edit_version import assert_edit_version
from src.modules.platform.domain.services.edit_version import bump_edit_version
from src.modules.platform.domain.services.quantities import assert_whole_pieces
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.domain.errors import ProjectNotFoundError
from src.modules.workspace.domain.policies.project_activity import assert_project_active
from src.modules.workspace.ports.outbound.workspace_queries import IProjectQueries
from src.shared_kernel.domain.services.changelog_service import append_field_changes
from src.shared_kernel.domain.services.clock import now_utc

# Closes the changelog lines of the statuses a quantity change moves.
_QUANTITY_CHANGED = "quantity changed"


class UpdateOrderItem:
    def __init__(
        self,
        order_item_repo: IOrderItemRepository,
        order_repo: IOrderRepository,
        catalogue_repo: IBoughtItemQueries,
        allocation_repo: IBoughtItemAllocationRepository,
        demand_repo: IBoughtItemDemandItemRepository,
        lot_repo: IProductionLotRepository | None = None,
        production_order_repo: IProductionOrderRepository | None = None,
        recompute_schedule: RecomputeMachineSchedule | None = None,
        *,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
        project_repo: IProjectQueries,
        source_allocation_repo: ISourceItemAllocationRepository | None = None,
    ) -> None:
        self._order_items = order_item_repo
        self._orders = order_repo
        self._catalogue = catalogue_repo
        self._allocations = allocation_repo
        self._demands = demand_repo
        self._lots = lot_repo
        self._production_orders = production_order_repo
        self._recompute = recompute_schedule
        self._uow = uow
        self._reconciler = reconciler
        self._projects = project_repo
        self._source_allocations = source_allocation_repo

    async def execute(
        self, actor: User, order_id: int, order_item_id: int, cmd: UpdateOrderItemCommand
    ) -> OrderItemResult:
        order = found_or_raise(
            await self._orders.get_by_id(order_id),
            OrderNotFoundError,
            f"Order #{order_id} not found.",
        )
        found = await self._order_items.get_by_id(order_item_id)
        if not found or found.order_id != order_id:
            raise OrderItemNotFoundError(
                f"Order item #{order_item_id} not found in order #{order_id}."
            )

        if cmd.project_id is not None and cmd.project_id != found.project_id:
            # Moving the line puts its work on the target project: shared,
            # before the lifecycle locks, as every writer of new work for a
            # project takes it (IProjectQueries.lock_for_share).
            await self._projects.lock_for_share([cmd.project_id])

        # Locked with its order, so a delivery booked meanwhile cannot slip
        # past the quantity guard below; a MADE line after its lot, whose
        # position bounds the line's quantity.
        self._reconciler.touch_order_items([order_item_id])
        await self._reconciler.lock_touched(also=lots_of_made_lines([found]))
        item = await self._order_items.get_by_id_for_update(order_item_id)
        if not item or item.order_id != order_id:
            raise OrderItemNotFoundError(
                f"Order item #{order_item_id} not found in order #{order_id}."
            )
        order = found_or_raise(
            await self._orders.get_by_id(order_id),
            OrderNotFoundError,
            f"Order #{order_id} not found.",
        )

        OrderRules.assert_can_update_line(actor, order, item.status, f"Order item #{item.id}")
        assert_edit_version(item, cmd.expected_edit_version, what=f"Order item #{item.id}")
        OrderRules.assert_received_line_keeps_its_identity(
            item,
            unit=cmd.unit,
            items_per_unit=cmd.items_per_unit,
            project_id=cmd.project_id,
            bought_item_id=cmd.bought_item_id,
        )
        if cmd.project_id is not None and cmd.project_id != item.project_id:
            assert_project_active(
                found_or_raise(
                    await self._projects.get_by_id(cmd.project_id),
                    ProjectNotFoundError,
                    f"Project #{cmd.project_id} not found.",
                ),
                work="order lines",
            )

        quantity_edited = quantity_changed(item.quantity, cmd.quantity)
        if quantity_edited or cmd.unit != item.unit:
            assert_whole_pieces(cmd.quantity, what="The order line quantity", unit=cmd.unit)
        if quantity_edited:
            await self._assert_quantity_edit(order, item, cmd.quantity)
        if cmd.bought_item_id is not None and cmd.bought_item_id != item.bought_item_id:
            await self._assert_allocations_repointable(order_item_id)

        # After the quantity check, which names a quantity edit more exactly.
        OrderRules.assert_line_editable(item)

        expected_delivery_date_changed = cmd.expected_delivery_date != item.expected_delivery_date

        now = now_utc()
        before = _logged_fields(item)
        bump_edit_version(item)
        item.quantity = cmd.quantity
        item.unit = cmd.unit
        item.items_per_unit = cmd.items_per_unit
        item.price = cmd.price
        item.note = cmd.note
        item.expected_delivery_date = cmd.expected_delivery_date
        item.expected_pickup_date = cmd.expected_pickup_date
        item.storage_place = cmd.storage_place
        item.changed = now

        if cmd.position is not None:
            item.position = cmd.position

        if cmd.project_id is not None and cmd.project_id != item.project_id:
            item.project_id = cmd.project_id

        await self._apply_identity(item, cmd)

        # Runs after the full mutation block above, never between the
        # bought_item_id/line_type/virtual_name assignments in the VIRTUAL
        # -> BOUGHT branch: a mid-mutation check would see a transiently
        # inconsistent item.
        OrderRules.assert_valid_line_type(item)
        item.changes = append_field_changes(
            item.changes, actor.full_name, before, _logged_fields(item)
        )

        saved = await self._order_items.save(item)
        await self._reconciler.run(
            actor, now, reason=_QUANTITY_CHANGED if quantity_edited else DEFAULT_REASON
        )
        await self._uow.commit()
        log.info(f"Updated order item #{order_item_id} in order #{order_id}.")

        if expected_delivery_date_changed:
            await self._recompute_downstream(saved)

        updated = await self._order_items.get_by_id(order_item_id)
        return OrderItemMapper.to_result(updated or saved)

    async def _assert_quantity_edit(
        self, order: Order, item: OrderItem, new_quantity: float
    ) -> None:
        """A quantity edit must be allowed for the line, stay within what a
        MADE line's position leaves it, and keep room for every allocation
        of both demand families on the line."""
        OrderRules.assert_quantity_editable(order, item)
        await self._assert_within_position(item, new_quantity)
        bought_allocations = await self._allocations.get_by_order_item_id(item.id)
        source_allocations: list[SourceItemDemandAllocation] = []
        if self._source_allocations is not None:
            source_allocations = await self._source_allocations.get_by_order_item_id(item.id)
        allocated = sum(a.quantity for a in bought_allocations) + sum(
            a.quantity for a in source_allocations
        )
        assert_order_item_quantity_allowed(item, new_quantity, allocated)

    async def _apply_identity(self, item: OrderItem, cmd: UpdateOrderItemCommand) -> None:
        """Repoints a line at another bought item, or renames a VIRTUAL line.
        Both edit a line's identity. A MADE line's name comes from its lot's
        made item and a SOURCE line's from its source item, so neither can be
        renamed or repointed here; renaming the catalogue entry renames every
        line already on an order."""
        if cmd.bought_item_id is not None and cmd.bought_item_id != item.bought_item_id:
            # VIRTUAL is allowed too: attaching a catalogue item to a
            # free-text line ("this turned out to be a stock part") is a
            # promotion to a BOUGHT line, and the free-text name goes away
            # with it.
            if item.line_type not in (OrderLineType.BOUGHT, OrderLineType.VIRTUAL):
                raise OrderItemLineTypeMismatchError(
                    f"Order item #{item.id} is a {item.line_type.value} line; its identity "
                    f"comes from its own catalogue entry and cannot be repointed at a "
                    f"bought item."
                )
            new_item = found_or_raise(
                await self._catalogue.get_by_id(cmd.bought_item_id),
                BoughtItemNotFoundError,
                f"Catalogue item #{cmd.bought_item_id} not found.",
            )
            BoughtItemCatalogueRules.assert_item_demandable(new_item)
            was_virtual = item.line_type == OrderLineType.VIRTUAL
            item.bought_item_id = new_item.id
            item.line_type = OrderLineType.BOUGHT
            item.virtual_name = None
            await self._update_allocations(item.id, new_item.id, cmd.substitute_reason)
            log.info(
                f"{'Promoted virtual' if was_virtual else 'Substituted item on'} "
                f"order item #{item.id} with catalogue item #{new_item.id!r}."
            )
        elif cmd.virtual_name is not None:
            if item.line_type != OrderLineType.VIRTUAL:
                raise OrderItemLineTypeMismatchError(
                    f"Order item #{item.id} is a {item.line_type.value} line; only VIRTUAL "
                    f"lines carry their own name."
                )
            item.virtual_name = cmd.virtual_name

    async def _recompute_downstream(self, saved: OrderItem) -> None:
        """A new expected delivery date of a line on a lot position moves the
        machines downstream of that position; one of a line that brings a
        lot's raw material moves the lot's first position, so any other line
        requests a walk too."""
        if saved.lot_position_id is None:
            await recompute_schedule_after_commit(
                self._recompute,
                after=f"a new expected date on order item #{saved.id}; the change is committed.",
            )
            return
        if (
            self._lots is not None
            and self._production_orders is not None
            and self._recompute is not None
        ):
            await recompute_downstream_position_machines(
                saved.lot_position_id, self._lots, self._production_orders, self._recompute
            )

    async def _assert_within_position(self, item: OrderItem, new_quantity: float) -> None:
        """A MADE line supplies its position together with the position's
        production orders, so its quantity never exceeds what they leave
        it."""
        if (
            item.line_type != OrderLineType.MADE
            or item.lot_position_id is None
            or self._lots is None
        ):
            return
        position = await self._lots.get_position_by_id(item.lot_position_id)
        if position is None:
            return
        available = compute_position_remaining(
            position.quantity, None, position.production_orders, position.closed_lines_quantity
        )
        assert_made_line_within_position(item, new_quantity, available)

    async def _assert_allocations_repointable(self, order_item_id: int) -> None:
        """A substitution rewrites the allocations on the line, and a
        fulfilled or canceled demand takes no allocation change. A raw
        material demand on the line takes no substitute at all."""
        if self._source_allocations is not None and (
            await self._source_allocations.get_by_order_item_id(order_item_id)
        ):
            raise OrderItemHoldsRawMaterialError(
                f"Order item #{order_item_id} holds raw material allocations of a lot; "
                "remove them before pointing the line at another item."
            )
        for alloc in await self._allocations.get_by_order_item_id(order_item_id):
            demand = await self._demands.get_by_id(alloc.demand_item_id)
            if demand is not None:
                BoughtItemAllocationRules.assert_not_terminal(demand)

    async def _update_allocations(
        self, order_item_id: int, new_item_id: int, substitute_reason: str | None
    ) -> None:
        for alloc in await self._allocations.get_by_order_item_id(order_item_id):
            demand = await self._demands.get_by_id(alloc.demand_item_id)
            # An allocation whose demand is gone records no substitution.
            demanded_item_id = demand.item_id if demand else new_item_id
            substitution = recorded_substitution(demanded_item_id, new_item_id, substitute_reason)
            alloc.substitute_item_id = substitution.item_id
            alloc.substitute_reason = substitution.reason
            await self._allocations.save(alloc)


def _logged_fields(item: OrderItem) -> dict[str, object]:
    """The line's editable fields, whose changes its changelog names."""
    return {
        "quantity": item.quantity,
        "unit": item.unit,
        "items_per_unit": item.items_per_unit,
        "price": item.price,
        "note": item.note,
        "expected_delivery_date": item.expected_delivery_date,
        "expected_pickup_date": item.expected_pickup_date,
        "storage_place": item.storage_place,
        "position": item.position,
        "project_id": item.project_id,
        "line_type": item.line_type,
        "bought_item_id": item.bought_item_id,
        "source_item_id": item.source_item_id,
        "virtual_name": item.virtual_name,
    }
