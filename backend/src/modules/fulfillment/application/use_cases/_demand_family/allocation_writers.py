"""
The manual allocation writers the demand families share. An order line
allocation links a bought or source item demand to one order line with a
given quantity and is created, changed in quantity and deleted here. The one
stock allocation of a demand, in all three families, is set to an absolute
quantity and removed here. Made item demands are allocated on lots by the
lot use cases, so only the stock writers serve them.

Every writer checks the allocation permission first and then locks through
the request's lock plan, the order line before the demand
(allocation_locks.py), holding the locks until its single commit. Two
concurrent writes against the same line or the same demand therefore
serialize and cannot both pass the capacity and overallocation checks on
the same totals. A fulfilled or canceled demand takes no new or changed
allocation, a fulfilled one also keeps the allocations it has, and a
canceled order line takes no new allocation. The capacity of a line counts
the allocations of bought and source item demands on it together. After
the write the lifecycle reconciler derives the demand's status, which
commits with the write.

A family's subclass binds `_spec` and supplies what differs as hooks: the
result of a saved allocation, the item match and the row of a new order
line allocation, the stock allocation row, and for source item demands the
log line of a new allocation and the schedule recompute after the commit.
"""

from abc import abstractmethod
from dataclasses import Field
from dataclasses import replace
from typing import Any
from typing import ClassVar
from typing import Generic
from typing import Protocol
from typing import TypeVar

from src.modules.fulfillment.application.services.allocation_fill import LineFillRepos
from src.modules.fulfillment.application.services.allocation_fill import (
    assert_takes_no_arrived_pieces,
)
from src.modules.fulfillment.application.services.allocation_locks import lock_for_allocation
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.use_cases._demand_family.spec import ALLOCATION_REASON
from src.modules.fulfillment.application.use_cases._demand_family.spec import D
from src.modules.fulfillment.application.use_cases._demand_family.spec import DemandFamilySpec
from src.modules.fulfillment.application.use_cases._demand_family.spec import DemandRepo
from src.modules.fulfillment.application.use_cases._demand_family.spec import FamilyAllocation
from src.modules.fulfillment.application.use_cases._demand_family.spec import WritableAllocationRepo
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.errors import AllocationAlreadyExistsError
from src.modules.fulfillment.domain.errors import AllocationNotFoundError
from src.modules.fulfillment.domain.errors import AllocationOverflowError
from src.modules.fulfillment.domain.errors import OrderItemNotFoundError
from src.modules.fulfillment.domain.services.allocation_coverage import (
    assert_line_takes_allocations,
)
from src.modules.fulfillment.domain.services.allocation_coverage import order_item_capacity_left
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.quantities import quantity_gt
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class OrderLineAllocation(FamilyAllocation, Protocol):
    """An allocation on an order line, a dataclass so that a change of its
    quantity copies every other field."""

    __dataclass_fields__: ClassVar[dict[str, Field[Any]]]
    order_item_id: int | None


A = TypeVar("A", bound=FamilyAllocation)
L = TypeVar("L", bound=OrderLineAllocation)
AR = TypeVar("AR")


class OrderLineAllocationRepo(WritableAllocationRepo[L], Protocol[L]):
    """The allocation repository of a family whose demands are allocated on
    order lines."""

    async def get_allocated_quantity(self, demand_item_id: int, /) -> float: ...

    async def get_allocated_quantity_for_order_item(self, order_item_id: int, /) -> float: ...

    async def get_allocated_quantities_for_order_items(
        self, order_item_ids: list[int], /
    ) -> dict[int, float]: ...


class QuantityCommand(Protocol):
    @property
    def quantity(self) -> float: ...


class NewLineAllocationCommand(QuantityCommand, Protocol):
    @property
    def demand_item_id(self) -> int: ...

    @property
    def order_item_id(self) -> int: ...


C = TypeVar("C", bound=NewLineAllocationCommand)


class AllocationWriter(Generic[D, A, AR]):
    """What every allocation writer does around its own check and write: the
    locked read of the demand, the reconciler run and the commit."""

    _spec: DemandFamilySpec[D, Any]

    def __init__(
        self,
        allocation_repo: WritableAllocationRepo[A],
        demand_repo: DemandRepo[D],
        *,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
    ) -> None:
        self._allocations = allocation_repo
        self._demands = demand_repo
        self._uow = uow
        self._reconciler = reconciler

    async def _read_locked_demand(self, demand_id: int) -> D:
        spec = self._spec
        return found_or_raise(
            await self._demands.get_by_id_for_update(demand_id),
            spec.terms.not_found_error,
            spec.not_found_message(demand_id),
        )

    async def _note(self, demand: D, actor: User, change: str) -> None:
        """Records a manual allocation change on the demand's changelog, so
        the history shows who allocated what, since an allocation row only
        keeps who created it."""
        demand.changes = append_changelog(demand.changes, actor.full_name, change)
        demand.changed = now_utc()
        await self._demands.save(demand)

    async def _reconcile_and_commit(self, actor: User, demand_id: int, *, action: str) -> None:
        """Derives the demand's status, commits, and then runs the family's
        after-commit step for `action`, which names the committed write."""
        self._reconciler.touch_demands(self._spec.aggregate, [demand_id])
        await self._reconciler.run(actor, now_utc(), reason=ALLOCATION_REASON)
        await self._uow.commit()
        await self._after_commit(action)

    async def _after_commit(self, action: str) -> None:
        """Runs once the write is committed; nothing by default. `action`
        completes a sentence such as "Schedule recompute failed after ..."."""

    @abstractmethod
    def _result(self, allocation: A) -> AR:
        """The family's result DTO of a saved allocation."""


class OrderLineAllocationWriter(AllocationWriter[D, L, AR]):
    """An allocation writer that also reads the order line it allocates on."""

    _allocations: OrderLineAllocationRepo[L]

    def __init__(
        self,
        allocation_repo: OrderLineAllocationRepo[L],
        demand_repo: DemandRepo[D],
        order_item_repo: IOrderItemRepository,
        *,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
        fill_repos: LineFillRepos,
    ) -> None:
        super().__init__(allocation_repo, demand_repo, uow=uow, reconciler=reconciler)
        self._order_items = order_item_repo
        self._fill_repos = fill_repos

    async def _lock_line_and_demand(self, demand_id: int, order_item_id: int) -> OrderItem:
        """Locks the order line and then the demand, and returns the line as
        read under the lock."""
        await lock_for_allocation(
            self._reconciler, self._spec.aggregate, [demand_id], order_item_ids=[order_item_id]
        )
        return found_or_raise(
            await self._order_items.get_by_id_for_update(order_item_id),
            OrderItemNotFoundError,
            f"Order item #{order_item_id} not found.",
        )

    async def _existing(self, demand_id: int, order_item_id: int) -> L:
        existing = next(
            (
                a
                for a in await self._allocations.get_by_demand_item_id(demand_id)
                if a.order_item_id == order_item_id
            ),
            None,
        )
        if not existing:
            raise AllocationNotFoundError(
                f"No allocation found for demand #{demand_id} / order item #{order_item_id}."
            )
        return existing


class CreateOrderLineAllocation(OrderLineAllocationWriter[D, L, AR], Generic[D, L, AR, C]):
    async def execute(self, actor: User, cmd: C) -> AR:
        spec = self._spec
        spec.rules.assert_can_allocate(actor)

        order_item = await self._lock_line_and_demand(cmd.demand_item_id, cmd.order_item_id)
        assert_line_takes_allocations(order_item)
        demand = await self._read_locked_demand(cmd.demand_item_id)

        spec.rules.assert_not_terminal(demand)
        self._assert_item_matches(demand, order_item, cmd)
        await self._assert_not_allocated_yet(cmd.demand_item_id, cmd.order_item_id)

        already_allocated = await self._allocations.get_allocated_quantity(cmd.demand_item_id)
        spec.rules.assert_no_overallocation(demand, already_allocated, cmd.quantity)

        allocated_on_line = await self._allocations.get_allocated_quantity_for_order_item(
            cmd.order_item_id
        )
        available = order_item_capacity_left(order_item, allocated_on_line)
        if quantity_gt(cmd.quantity, available):
            raise AllocationOverflowError(
                f"Order item #{cmd.order_item_id} has only {available:.3f} {order_item.unit} "
                f"available to allocate, but {cmd.quantity:.3f} was requested."
            )

        await assert_takes_no_arrived_pieces(
            self._fill_repos, order_item, spec.fill_rank, demand.id, cmd.quantity
        )

        allocation = self._new_allocation(demand, order_item, cmd)
        allocation.created_by_id = actor.id
        saved = await self._allocations.save(allocation)
        await self._note(
            demand,
            actor,
            f"Allocated {cmd.quantity:.3f} {demand.unit} on order item #{cmd.order_item_id}.",
        )
        await self._reconcile_and_commit(
            actor,
            cmd.demand_item_id,
            action=(
                f"allocating {spec.log_noun} #{cmd.demand_item_id} to order item "
                f"#{cmd.order_item_id}; the allocation itself is committed."
            ),
        )
        self._log_created(cmd, demand, order_item)
        return self._result(saved)

    async def _assert_not_allocated_yet(self, demand_id: int, order_item_id: int) -> None:
        """Refuses a second allocation of the demand on the line, read under
        the locks: the repository saves one row per demand and line, so a
        second create would replace the first one's quantity."""
        held = await self._allocations.get_by_demand_item_id(demand_id)
        if any(a.order_item_id == order_item_id for a in held):
            raise AllocationAlreadyExistsError(
                f"Demand #{demand_id} is already allocated to order item #{order_item_id}; "
                "change that allocation's quantity instead."
            )

    @abstractmethod
    def _assert_item_matches(self, demand: D, order_item: OrderItem, cmd: C) -> None:
        """Raises when the order line may not cover the demand."""

    @abstractmethod
    def _new_allocation(self, demand: D, order_item: OrderItem, cmd: C) -> L:
        """The family's allocation row of `cmd` on the order line."""

    def _log_created(self, cmd: C, demand: D, order_item: OrderItem) -> None:
        log.info(
            f"Allocated {cmd.quantity} units of {self._spec.log_noun} "
            f"#{cmd.demand_item_id} to order item #{cmd.order_item_id}."
        )


class UpdateOrderLineAllocation(OrderLineAllocationWriter[D, L, AR]):
    """Changes the quantity of an existing order line allocation. The source
    and any substitution recorded at creation stay as they are."""

    async def execute(
        self, actor: User, demand_item_id: int, order_item_id: int, cmd: QuantityCommand
    ) -> AR:
        spec = self._spec
        spec.rules.assert_can_allocate(actor)

        order_item = await self._lock_line_and_demand(demand_item_id, order_item_id)
        demand = await self._read_locked_demand(demand_item_id)
        spec.rules.assert_not_terminal(demand)

        existing = await self._existing(demand_item_id, order_item_id)
        already_allocated = await self._allocations.get_allocated_quantity(demand_item_id)
        spec.rules.assert_no_overallocation(
            demand, already_allocated, cmd.quantity, exclude_existing=existing.quantity
        )

        allocated_on_line = await self._allocations.get_allocated_quantity_for_order_item(
            order_item_id
        )
        available = order_item_capacity_left(
            order_item, allocated_on_line, released=existing.quantity
        )
        if quantity_gt(cmd.quantity, available):
            raise AllocationOverflowError(
                f"Order item #{order_item_id} has only {available:.3f} {order_item.unit} "
                f"available (excluding current allocation), but {cmd.quantity:.3f} was requested."
            )

        await assert_takes_no_arrived_pieces(
            self._fill_repos, order_item, spec.fill_rank, demand_item_id, cmd.quantity
        )

        saved = await self._allocations.save(replace(existing, quantity=cmd.quantity))
        await self._note(
            demand,
            actor,
            f"Allocation on order item #{order_item_id} changed from "
            f"{existing.quantity:.3f} to {cmd.quantity:.3f} {demand.unit}.",
        )
        await self._reconcile_and_commit(
            actor,
            demand_item_id,
            action=(
                f"updating allocation demand #{demand_item_id} / order item "
                f"#{order_item_id}; the update itself is committed."
            ),
        )
        log.info(
            f"Updated allocation demand "
            f"#{demand_item_id} / order item #{order_item_id} to {cmd.quantity}."
        )
        return self._result(saved)


class DeleteOrderLineAllocation(OrderLineAllocationWriter[D, L, None]):
    async def execute(self, actor: User, demand_item_id: int, order_item_id: int) -> None:
        spec = self._spec
        spec.rules.assert_can_allocate(actor)

        # The demand is locked so it cannot become fulfilled between the
        # check below and the commit, with the line, whose other demands get
        # the released pieces.
        await lock_for_allocation(
            self._reconciler, spec.aggregate, [demand_item_id], order_item_ids=[order_item_id]
        )
        demand = await self._read_locked_demand(demand_item_id)
        spec.rules.assert_release_allowed(demand)

        existing = await self._existing(demand_item_id, order_item_id)
        await self._allocations.delete(existing)
        await self._note(
            demand,
            actor,
            f"Allocation of {existing.quantity:.3f} {demand.unit} on order item "
            f"#{order_item_id} removed.",
        )
        await self._reconcile_and_commit(
            actor,
            demand_item_id,
            action=(
                f"deleting allocation demand #{demand_item_id} / order item "
                f"#{order_item_id}; the deletion itself is committed."
            ),
        )
        log.info(f"Deleted allocation demand #{demand_item_id} / order item #{order_item_id}.")

    def _result(self, allocation: L) -> None:
        return None


class UpdateStockAllocation(AllocationWriter[D, A, AR]):
    """Sets the stock allocation of a demand to an absolute quantity, creating
    the row when the demand has none yet. It is the counterpart of the
    fulfilment from stock, which tops the row up."""

    async def execute(self, actor: User, demand_item_id: int, cmd: QuantityCommand) -> AR:
        spec = self._spec
        spec.rules.assert_can_allocate(actor)

        # Only the demand is locked, since a stock allocation has no order
        # line or lot to lock first.
        await lock_for_allocation(self._reconciler, spec.aggregate, [demand_item_id])
        demand = await self._read_locked_demand(demand_item_id)
        spec.rules.assert_not_terminal(demand)

        existing_allocations = await self._allocations.get_by_demand_item_id(demand_item_id)
        allocated_elsewhere = sum(
            a.quantity for a in existing_allocations if a.source != spec.stock_source
        )
        spec.rules.assert_no_overallocation(demand, allocated_elsewhere, cmd.quantity)

        previous = next(
            (a.quantity for a in existing_allocations if a.source == spec.stock_source), 0.0
        )
        allocation = self._stock_allocation(demand_item_id, cmd.quantity)
        allocation.created_by_id = actor.id
        saved = await self._allocations.save(allocation)
        await self._note(
            demand,
            actor,
            f"Stock allocation changed from {previous:.3f} to {cmd.quantity:.3f} {demand.unit}.",
        )
        await self._reconcile_and_commit(
            actor,
            demand_item_id,
            action=(
                f"setting stock allocation for {spec.log_noun} #{demand_item_id}; the "
                f"allocation itself is committed."
            ),
        )
        log.info(f"Set stock allocation for {spec.log_noun} #{demand_item_id} to {cmd.quantity}.")
        return self._result(saved)

    @abstractmethod
    def _stock_allocation(self, demand_id: int, quantity: float) -> A:
        """The family's stock allocation row of the demand with `quantity`."""


class DeleteStockAllocation(AllocationWriter[D, A, None]):
    """Removes the stock allocation row of a demand."""

    async def execute(self, actor: User, demand_item_id: int) -> None:
        spec = self._spec
        spec.rules.assert_can_allocate(actor)

        # The demand is locked so it cannot become fulfilled between the
        # check below and the commit.
        await lock_for_allocation(self._reconciler, spec.aggregate, [demand_item_id])
        demand = await self._read_locked_demand(demand_item_id)
        spec.rules.assert_release_allowed(demand)

        existing_allocations = await self._allocations.get_by_demand_item_id(demand_item_id)
        stock_allocation = next(
            (a for a in existing_allocations if a.source == spec.stock_source), None
        )
        if not stock_allocation:
            raise AllocationNotFoundError(
                f"No stock allocation found for demand #{demand_item_id}."
            )

        await self._allocations.delete(stock_allocation)
        await self._note(
            demand,
            actor,
            f"Stock allocation of {stock_allocation.quantity:.3f} {demand.unit} removed.",
        )
        await self._reconcile_and_commit(
            actor,
            demand_item_id,
            action=(
                f"deleting stock allocation for {spec.log_noun} #{demand_item_id}; the "
                f"deletion itself is committed."
            ),
        )
        log.info(f"Deleted stock allocation for {spec.log_noun} #{demand_item_id}.")

    def _result(self, allocation: A) -> None:
        return None
