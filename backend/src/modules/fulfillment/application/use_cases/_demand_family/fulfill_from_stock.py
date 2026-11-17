"""
Covers (part of) a bought, made or source item demand directly from stock
instead of through an order line or a lot. No stock level is tracked here
or anywhere in glados, that ledger lives in another service. The use case
only records how much of a demand was satisfied this way, topping up the one
stock allocation row of the demand; the lifecycle reconciler then derives
the demand's status.

The flow is the same for every family. A family's subclass binds `_spec`,
keeps its own constructor, and supplies what differs as hooks: the stock
allocation row it saves, the open quantity of its summary (bought and
source demands read the order lines they are allocated on, made demands
their lots), its log line and, for source demands, the schedule recompute
after the commit.
"""

from abc import abstractmethod
from collections.abc import Callable
from typing import Any
from typing import Generic
from typing import Protocol
from typing import TypeVar

from src.modules.fulfillment.application.services.allocation_locks import lock_for_allocation
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.use_cases._demand_family.spec import STOCK_REASON
from src.modules.fulfillment.application.use_cases._demand_family.spec import A
from src.modules.fulfillment.application.use_cases._demand_family.spec import AllocationRepo
from src.modules.fulfillment.application.use_cases._demand_family.spec import D
from src.modules.fulfillment.application.use_cases._demand_family.spec import DemandFamilySpec
from src.modules.fulfillment.application.use_cases._demand_family.spec import DemandRepo
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class StockCommand(Protocol):
    @property
    def demand_item_id(self) -> int: ...

    @property
    def quantity(self) -> float: ...


C = TypeVar("C", bound=StockCommand)
FR = TypeVar("FR")


class FulfillFromStock(Generic[D, A, C, FR]):
    """`_result` builds the family's result DTO from the fields every family's
    result has."""

    _spec: DemandFamilySpec[D, Any]
    _result: Callable[..., FR]

    def __init__(
        self,
        demand_repo: DemandRepo[D],
        allocation_repo: AllocationRepo[A],
        *,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
    ) -> None:
        self._demands = demand_repo
        self._allocations = allocation_repo
        self._uow = uow
        self._reconciler = reconciler

    async def execute(self, actor: User, cmd: C) -> FR:
        spec = self._spec
        spec.rules.assert_can_allocate(actor)

        # Locked read of the demand only, since stock involves no order line
        # or lot; held until this use case's single uow.commit() below.
        await lock_for_allocation(self._reconciler, spec.aggregate, [cmd.demand_item_id])
        demand = found_or_raise(
            await self._demands.get_by_id_for_update(cmd.demand_item_id),
            spec.terms.not_found_error,
            spec.not_found_message(cmd.demand_item_id),
        )

        spec.rules.assert_not_terminal(demand)

        existing_allocations = await self._allocations.get_by_demand_item_id(cmd.demand_item_id)
        already_committed = sum(a.quantity for a in existing_allocations)
        spec.rules.assert_no_overallocation(demand, already_committed, cmd.quantity)

        stock_allocation = next(
            (a for a in existing_allocations if a.source == spec.stock_source), None
        )
        new_stock_quantity = (stock_allocation.quantity if stock_allocation else 0.0) + cmd.quantity
        await self._allocations.save(self._stock_allocation(cmd.demand_item_id, new_stock_quantity))

        updated_allocations = await self._allocations.get_by_demand_item_id(cmd.demand_item_id)
        remaining_unallocated = await self._unallocated(demand, updated_allocations)

        demand.changed = now_utc()
        demand.changes = append_changelog(
            demand.changes,
            actor.full_name,
            f"Fulfilled {cmd.quantity:.3f} {demand.unit} from stock.",
        )
        await self._demands.save(demand)
        self._reconciler.touch_demands(spec.aggregate, [demand.id])
        result = await self._reconciler.run(actor, now_utc(), reason=STOCK_REASON)
        new_status = result.new_status(spec.aggregate, demand.id)

        await self._uow.commit()
        await self._after_commit(demand)
        self._log_fulfilled(cmd, demand, new_stock_quantity)

        return self._result(
            demand_item_id=demand.id,
            quantity_fulfilled=cmd.quantity,
            total_fulfilled_from_stock=new_stock_quantity,
            remaining_unallocated=remaining_unallocated,
            demand_status_changed_to=new_status,
        )

    async def replay(self, demand_item_id: int, quantity: float) -> FR:
        """The answer to a retry of a fulfilment that went through already
        (services/idempotency.py): what the demand holds from stock now, and
        no status change, since the retry books nothing."""
        spec = self._spec
        demand = found_or_raise(
            await self._demands.get_by_id(demand_item_id),
            spec.terms.not_found_error,
            spec.not_found_message(demand_item_id),
        )
        allocations = await self._allocations.get_by_demand_item_id(demand_item_id)
        stock = next((a for a in allocations if a.source == spec.stock_source), None)
        return self._result(
            demand_item_id=demand.id,
            quantity_fulfilled=quantity,
            total_fulfilled_from_stock=stock.quantity if stock else 0.0,
            remaining_unallocated=await self._unallocated(demand, allocations),
            demand_status_changed_to=None,
        )

    @abstractmethod
    def _stock_allocation(self, demand_id: int, quantity: float) -> A:
        """The family's stock allocation row of the demand with `quantity`."""

    @abstractmethod
    async def _unallocated(self, demand: D, allocations: list[A]) -> float:
        """The quantity of the demand its allocations leave open."""

    async def _after_commit(self, demand: D) -> None:
        """Runs once the fulfilment is committed; nothing by default."""

    def _log_fulfilled(self, cmd: C, demand: D, total_from_stock: float) -> None:
        log.info(
            "Fulfilled %.3f units of demand #%s from stock. Total from stock: %.3f.",
            cmd.quantity,
            cmd.demand_item_id,
            total_from_stock,
        )
