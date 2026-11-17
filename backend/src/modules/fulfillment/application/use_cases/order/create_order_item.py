"""
Creates a new order item for an order, optionally allocating demands to this line.
Display identity (name, article, etc.) is denormalized at read time from the catalogue, not
persisted here. A bought or source line needs an item new work may name: active, not archived
and, for a bought item, not missing in PDM.

The request names the share of the line each demand takes, bought item demands on a bought
line and source item demands on the line for their material, so the buyer decides which
demand a substitute or a short line is meant for. Each share must fit what the demand still
needs, its quantity minus everything already allocated to it from orders or stock, and the
shares together must fit the line. A demand that is fulfilled, canceled or unknown is refused,
never skipped, so a repeated request cannot add a line nobody asked for. A line for another
item than the demand's records the substitution. The lifecycle reconciler then derives each
demand's status from its allocations, as after every allocation write.

An order someone canceled takes no new line; one that is canceled only because every line
is canceled still does. The line's supplier must exist and its project must be active; the
project is locked in shared mode before the lifecycle locks, so a concurrent project delete
either counts the line or makes this request find the project gone. The order and the
demands are locked together before the checks, and the lifecycle reconciler derives the
order's status with the new line. A source item allocation moves the schedule, which is
recomputed after the commit.
"""

from dataclasses import dataclass
from datetime import datetime

from src.modules.catalogue.domain.errors import BoughtItemNotFoundError
from src.modules.catalogue.domain.errors import SourceItemNotFoundError
from src.modules.catalogue.domain.errors import SupplierNotFoundError
from src.modules.catalogue.domain.policies.bought_item_rules import BoughtItemCatalogueRules
from src.modules.catalogue.domain.policies.source_item_rules import SourceItemCatalogueRules
from src.modules.catalogue.ports.outbound.catalogue_queries import IBoughtItemQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import ISourceItemQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import ISupplierQueries
from src.modules.fulfillment.application.dto.order_dto import CreateOrderItemCommand
from src.modules.fulfillment.application.dto.order_dto import OrderItemResult
from src.modules.fulfillment.application.mappers.order_mapper import OrderItemMapper
from src.modules.fulfillment.application.services.lifecycle_loader import AggregateIds
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.use_cases.production_schedule.recompute_machine_schedule import (
    RecomputeMachineSchedule,
)
from src.modules.fulfillment.domain.entities.bought_item_allocation import (
    BoughtItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.bought_item_demand_item import BoughtItemDemandItem
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.source_item_allocation import (
    SourceItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.source_item_demand_item import SourceItemDemandItem
from src.modules.fulfillment.domain.errors import DemandItemNotFoundError
from src.modules.fulfillment.domain.errors import OrderNotFoundError
from src.modules.fulfillment.domain.errors import SourceItemDemandNotFoundError
from src.modules.fulfillment.domain.services.allocation_coverage import recorded_substitution
from src.modules.fulfillment.domain.services.allocation_service import BoughtItemAllocationRules
from src.modules.fulfillment.domain.services.order_rules import OrderRules
from src.modules.fulfillment.domain.services.source_item_allocation_service import (
    SourceItemAllocationRules,
)
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
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
from src.modules.platform.domain.services.quantities import assert_whole_pieces
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.domain.errors import ProjectNotFoundError
from src.modules.workspace.domain.policies.project_activity import assert_project_active
from src.modules.workspace.ports.outbound.workspace_queries import IProjectQueries
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


@dataclass(frozen=True)
class LineIdentity:
    """A new line's display name, for the log, and its line type."""

    display_name: str
    line_type: OrderLineType


class CreateOrderItem:
    def __init__(
        self,
        order_item_repo: IOrderItemRepository,
        item_repo: IBoughtItemQueries,
        order_repo: IOrderRepository,
        demand_repo: IBoughtItemDemandItemRepository,
        allocation_repo: IBoughtItemAllocationRepository,
        source_item_repo: ISourceItemQueries,
        *,
        project_repo: IProjectQueries,
        supplier_repo: ISupplierQueries,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
        source_demand_repo: ISourceItemDemandRepository | None = None,
        source_allocation_repo: ISourceItemAllocationRepository | None = None,
        recompute_schedule: RecomputeMachineSchedule | None = None,
    ) -> None:
        """The source item repositories are needed for source item demand
        allocations only, and the schedule recompute after them."""
        self._source_demands = source_demand_repo
        self._source_allocations = source_allocation_repo
        self._recompute = recompute_schedule
        self._order_items = order_item_repo
        self._items = item_repo
        self._orders = order_repo
        self._demands = demand_repo
        self._allocations = allocation_repo
        self._source_items = source_item_repo
        self._projects = project_repo
        self._suppliers = supplier_repo
        self._uow = uow
        self._reconciler = reconciler

    async def execute(self, actor: User, cmd: CreateOrderItemCommand) -> OrderItemResult:
        order = found_or_raise(
            await self._orders.get_by_id(cmd.order_id),
            OrderNotFoundError,
            f"Order #{cmd.order_id} not found.",
        )
        OrderRules.assert_can_update_line(actor, order, OrderItemStatus.PENDING, "A new line")
        identity = await self.check_item(
            bought_item_id=cmd.bought_item_id,
            source_item_id=cmd.source_item_id,
            virtual_name=cmd.virtual_name,
        )

        found_or_raise(
            await self._suppliers.get_by_id(cmd.supplier_id),
            SupplierNotFoundError,
            f"Supplier #{cmd.supplier_id} not found.",
        )
        # Shared, before the lifecycle locks, as every writer of new work for
        # a project takes it (IProjectQueries.lock_for_share).
        await self._projects.lock_for_share([cmd.project_id])
        assert_project_active(
            found_or_raise(
                await self._projects.get_by_id(cmd.project_id),
                ProjectNotFoundError,
                f"Project #{cmd.project_id} not found.",
            ),
            work="new order lines",
        )

        self._reconciler.touch_orders([cmd.order_id])
        await self._reconciler.lock_touched(
            also=AggregateIds.of(
                {
                    LifecycleAggregate.BOUGHT_DEMANDS: {
                        a.demand_item_id for a in cmd.bought_demand_allocations
                    },
                    LifecycleAggregate.SOURCE_DEMANDS: {
                        a.demand_item_id for a in cmd.source_demand_allocations
                    },
                }
            )
        )
        now = now_utc()
        saved = await self.add_under_lock(actor, cmd, identity, now)

        await self._reconciler.run(actor, now)
        await self._uow.commit()
        if cmd.source_demand_allocations:
            await recompute_schedule_after_commit(
                self._recompute,
                after=f"adding order item #{saved.id} for source item demands; it is committed.",
            )
        added = await self._order_items.get_by_id(saved.id)
        return OrderItemMapper.to_result(added or saved)

    async def check_item(
        self,
        *,
        bought_item_id: int | None,
        source_item_id: int | None,
        virtual_name: str | None,
    ) -> LineIdentity:
        """The line's type and display name, refusing a bought or source
        item new work may not name. Runs before any lock."""
        # The command validator guarantees exactly one of bought_item_id /
        # source_item_id / virtual_name, so each branch fully determines the
        # line type, no branch may fall through to the default. Display
        # identity (item_order_code_1/2, item_specification,
        # item_article_name, ...) is denormalized read-side only, by
        # order_item_orm_to_entity() from the live catalogue row: it is
        # not persisted here (order_item_entity_to_dict() drops it, and
        # save() below returns the re-derived entity), so this
        # branch only needs display_name for the log line and line_type for
        # the row itself.
        if bought_item_id is not None:
            bought_item = found_or_raise(
                await self._items.get_by_id(bought_item_id),
                BoughtItemNotFoundError,
                f"Catalogue item #{bought_item_id} not found.",
            )
            BoughtItemCatalogueRules.assert_item_demandable(bought_item)
            return LineIdentity(bought_item.article_name, OrderLineType.BOUGHT)
        if source_item_id is not None:
            source_item = found_or_raise(
                await self._source_items.get_by_id(source_item_id),
                SourceItemNotFoundError,
                f"Source item #{source_item_id} not found.",
            )
            SourceItemCatalogueRules.assert_item_demandable(source_item)
            return LineIdentity(
                source_item.dimension or f"Source item #{source_item.id}",
                OrderLineType.SOURCE,
            )
        return LineIdentity(virtual_name or "", OrderLineType.VIRTUAL)

    async def add_under_lock(
        self,
        actor: User,
        cmd: CreateOrderItemCommand,
        identity: LineIdentity,
        now: datetime,
        *,
        quote_request_line_id: int | None = None,
    ) -> OrderItem:
        """Adds the line and its demand allocations once the caller locked
        the order and the demands, without running the reconciler or
        committing. The supplier must exist and the project must be active
        and share-locked, which the caller checked before the locks."""
        order = found_or_raise(
            await self._orders.get_by_id(cmd.order_id),
            OrderNotFoundError,
            f"Order #{cmd.order_id} not found.",
        )
        # The permission depends on the order's status, so it is checked
        # again on the locked read: the order may have been submitted since.
        OrderRules.assert_can_update_line(actor, order, OrderItemStatus.PENDING, "A new line")
        OrderRules.assert_can_add_line(order)
        assert_whole_pieces(cmd.quantity, what="The order line quantity", unit=cmd.unit)
        for share in (*cmd.bought_demand_allocations, *cmd.source_demand_allocations):
            assert_whole_pieces(share.quantity, what="A demand allocation", unit=cmd.unit)

        order_item = OrderItem(
            id=0,
            created=now,
            changed=now,
            changes=append_changelog([], actor.full_name, "Order item created."),
            status=OrderItemStatus.default(),
            position=await self._order_items.next_position(cmd.order_id),
            quantity=cmd.quantity,
            quantity_delivered=0.0,
            unit=cmd.unit,
            items_per_unit=cmd.items_per_unit,
            price=cmd.price,
            note=cmd.note,
            ordered_date=None,
            expected_delivery_date=cmd.expected_delivery_date,
            delivery_date=None,
            storage_place=None,
            expected_pickup_date=cmd.expected_pickup_date,
            ready_for_pickup_date=None,
            creator_id=actor.id,
            orderer_id=None,
            receiver_id=None,
            bought_item_id=cmd.bought_item_id,
            order_id=cmd.order_id,
            supplier_id=cmd.supplier_id,
            project_id=cmd.project_id,
            line_type=identity.line_type,
            lot_position_id=None,
            source_item_id=cmd.source_item_id,
            virtual_name=cmd.virtual_name,
            quote_request_line_id=quote_request_line_id,
            creator=actor,
        )
        OrderRules.assert_valid_line_type(order_item)

        saved = await self._order_items.save(order_item)
        self._reconciler.touch_order_items([saved.id], created=True)
        log.info(f"Added order item {identity.display_name!r} to order #{cmd.order_id}.")

        await self._allocate_bought_demands(actor, cmd, saved)
        await self._allocate_source_demands(actor, cmd, saved)
        return saved

    async def _allocate_bought_demands(
        self, actor: User, cmd: CreateOrderItemCommand, line: OrderItem
    ) -> None:
        """Allocates each bought item demand its share of the new line. The
        line needs no lock, since no other transaction can see it before the
        commit; the demands were locked with the order and are read again
        through their locks, in ascending id."""
        for share in sorted(cmd.bought_demand_allocations, key=lambda a: a.demand_item_id):
            demand = found_or_raise(
                await self._demands.get_by_id_for_update(share.demand_item_id),
                DemandItemNotFoundError,
                f"Demand item #{share.demand_item_id} not found.",
            )
            BoughtItemAllocationRules.assert_not_terminal(demand)
            BoughtItemAllocationRules.assert_no_overallocation(
                demand, await self._allocations.get_allocated_quantity(demand.id), share.quantity
            )
            substitution = recorded_substitution(
                demand.item_id, line.bought_item_id, cmd.substitute_reason
            )
            await self._allocations.save(
                BoughtItemDemandAllocation(
                    demand_item_id=demand.id,
                    order_item_id=line.id,
                    quantity=share.quantity,
                    substitute_item_id=substitution.item_id,
                    substitute_reason=substitution.reason,
                )
            )
            await self._log_allocation(actor, cmd, demand, line, share.quantity)
            await self._demands.save(demand)
            self._reconciler.touch_demands(LifecycleAggregate.BOUGHT_DEMANDS, [demand.id])

    async def _allocate_source_demands(
        self, actor: User, cmd: CreateOrderItemCommand, line: OrderItem
    ) -> None:
        """Allocates each source item demand its share of the new line, as
        _allocate_bought_demands does. The line must be for the demand's
        material; a line for another source item is the substitution the
        buyer chose by ordering it."""
        if not cmd.source_demand_allocations:
            return
        if self._source_demands is None or self._source_allocations is None:
            raise RuntimeError("Source item demands need the source item repositories.")
        for share in sorted(cmd.source_demand_allocations, key=lambda a: a.demand_item_id):
            demand = found_or_raise(
                await self._source_demands.get_by_id_for_update(share.demand_item_id),
                SourceItemDemandNotFoundError,
                f"Source item demand #{share.demand_item_id} not found.",
            )
            SourceItemAllocationRules.assert_not_terminal(demand)
            SourceItemAllocationRules.assert_material_matches(demand, line, line.source_item_id)
            SourceItemAllocationRules.assert_no_overallocation(
                demand,
                await self._source_allocations.get_allocated_quantity(demand.id),
                share.quantity,
            )
            substitution = recorded_substitution(
                demand.source_item_id, line.source_item_id, cmd.substitute_reason
            )
            await self._source_allocations.save(
                SourceItemDemandAllocation(
                    demand_item_id=demand.id,
                    order_item_id=line.id,
                    quantity=share.quantity,
                    substitute_source_item_id=substitution.item_id,
                    substitute_reason=substitution.reason,
                )
            )
            await self._log_allocation(actor, cmd, demand, line, share.quantity)
            await self._source_demands.save(demand)
            self._reconciler.touch_demands(LifecycleAggregate.SOURCE_DEMANDS, [demand.id])

    @staticmethod
    async def _log_allocation(
        actor: User,
        cmd: CreateOrderItemCommand,
        demand: BoughtItemDemandItem | SourceItemDemandItem,
        line: OrderItem,
        quantity: float,
    ) -> None:
        demand.changed = now_utc()
        demand.changes = append_changelog(
            demand.changes,
            actor.full_name,
            f"Allocated {quantity:.3f} {demand.unit} to order #{cmd.order_id} "
            f"via order item #{line.id}.",
        )
