"""
In-memory fake repositories and collaborators shared by the
production_order test modules.

The production order fakes return the stored objects themselves, so the
lifecycle reconciler built by production_order_reconciler writes its derived
status onto the very objects a test reads. An order's interruptions live on
the order (ProductionOrder.interruptions), where the derivation reads them,
and FakeProductionOrderInterruptionRepository writes there.
"""

import itertools
from datetime import datetime
from types import SimpleNamespace
from typing import Any

from src.modules.fulfillment.application.services.lifecycle_loader import LifecycleRepositories
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.machine_pool import MachinePool
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_machine import ProductionMachine
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.entities.production_order_completion import (
    ProductionOrderCompletion,
)
from src.modules.fulfillment.domain.entities.production_order_file import ProductionOrderFile
from src.modules.fulfillment.domain.entities.production_order_interruption import (
    ProductionOrderInterruption,
)
from src.modules.fulfillment.domain.services.scheduling import ExternalForecast
from src.modules.fulfillment.domain.value_objects.interruption_ended_by import InterruptionEndedBy
from src.modules.fulfillment.domain.value_objects.interruption_reason import InterruptionReason
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    ProductionOrderFilterDto,
)
from tests.unit._external_work import external_work_lot_ids
from tests.unit.lifecycle.fake_demand_reconciler import ReconcilerAllocations
from tests.unit.lifecycle.fake_demand_reconciler import ReconcilerDemands
from tests.unit.lifecycle.fake_reconciler import EmptyRows
from tests.unit.lifecycle.fake_reconciler import ReconcilerOrderItems
from tests.unit.lifecycle.fake_reconciler import ReconcilerOrders


class FakeProductionLotRepository:
    def __init__(
        self,
        lots: list[ProductionLot] | None = None,
        raw_material_arrived_by_demand: dict[int, float] | None = None,
    ) -> None:
        self._lots: dict[int, ProductionLot] = {lot.id: lot for lot in (lots or [])}
        self._positions: dict[int, LotPosition] = {}
        for lot in lots or []:
            for position in lot.positions:
                self._positions[position.id] = position
        self._raw_material_arrived_by_demand = raw_material_arrived_by_demand or {}
        self._events: list = []
        self.for_update_calls: list[int] = []
        self.lock_calls: list[list[int]] = []
        # A production order fake to fill a read position's production
        # orders from, as the repository does; None leaves them as stored.
        self.production_orders: Any | None = None

    async def get_raw_material_arrived_quantity(self, demand_id: int) -> float:
        return self._raw_material_arrived_by_demand.get(demand_id, 0.0)

    async def get_raw_material_arrived_quantities(self, demand_ids: list[int]) -> dict[int, float]:
        return {d: await self.get_raw_material_arrived_quantity(d) for d in demand_ids}

    async def get_by_id(self, id: int) -> ProductionLot | None:
        return self._lots.get(id)

    async def get_by_id_for_update(self, id: int) -> ProductionLot | None:
        self.for_update_calls.append(id)
        return self._lots.get(id)

    async def lock_for_update(self, ids: list[int]) -> None:
        self.lock_calls.append(list(ids))

    async def get_ids_with_external_work(self) -> list[int]:
        return external_work_lot_ids(await self.get_by_ids(sorted(self._lots)))

    async def get_by_ids(self, ids: list[int], *, refresh: bool = False) -> list[ProductionLot]:
        return [self._lots[i] for i in ids if i in self._lots]

    async def get_multi(self, filters):
        items = [
            lot
            for lot in self._lots.values()
            if getattr(filters, "project_id", None) is None or lot.project_id == filters.project_id
        ]
        return len(items), items

    async def get_by_project_id(
        self, project_id: int, *, refresh: bool = False
    ) -> list[ProductionLot]:
        return sorted(
            (lot for lot in self._lots.values() if lot.project_id == project_id),
            key=lambda lot: lot.id,
        )

    async def lock_time_budgets(self, project_id: int) -> None:
        return None

    async def save_step_time_budgets(self, budgets: dict[int, float | None]) -> None:
        for lot in self._lots.values():
            for position in lot.positions:
                for step in position.steps:
                    if step.id in budgets:
                        step.time_budget_per_piece = budgets[step.id]

    async def save(self, lot: ProductionLot) -> ProductionLot:
        self._lots[lot.id] = lot
        return lot

    async def next_lot_number(self, template: str) -> str:
        raise NotImplementedError

    async def get_steps(self, lot_id: int):
        lot = self._lots.get(lot_id)
        if not lot:
            return []
        return sorted((s for p in lot.positions for s in p.steps), key=lambda s: s.sequence)

    async def get_step_by_id(self, step_id: int):
        for lot in self._lots.values():
            for position in lot.positions:
                for step in position.steps:
                    if step.id == step_id:
                        return step
        return None

    async def save_step(self, step):
        for lot in self._lots.values():
            for position in lot.positions:
                for i, existing in enumerate(position.steps):
                    if existing.id == step.id:
                        position.steps[i] = step
                        return step
        return step

    async def delete_step(self, step):
        raise NotImplementedError

    async def reorder_steps(self, lot_id, ordered_step_ids):
        raise NotImplementedError

    async def get_positions(self, lot_id: int) -> list[LotPosition]:
        return sorted(
            (p for p in self._positions.values() if p.lot_id == lot_id), key=lambda p: p.sequence
        )

    async def get_position_by_id(self, position_id: int) -> LotPosition | None:
        position = self._positions.get(position_id)
        if position is not None and self.production_orders is not None:
            position.production_orders = await self.production_orders.get_by_lot_position_id(
                position_id
            )
        return position

    async def get_positions_by_ids(self, position_ids: list[int]) -> list:
        positions = [await self.get_position_by_id(i) for i in position_ids]
        return [p for p in positions if p is not None]

    async def save_position(self, position: LotPosition) -> LotPosition:
        self._positions[position.id] = position
        return position

    async def save_position_forecasts(self, forecasts: list[ExternalForecast]) -> None:
        for forecast in forecasts:
            position = self._positions.get(forecast.position_id)
            if position is not None:
                position.planned_pickup_date = forecast.planned_pickup_date
                position.planned_delivery_date = forecast.planned_delivery_date

    async def delete_position(self, position):
        raise NotImplementedError

    async def get_events(self, lot_id: int):
        return [e for e in self._events if e.lot_id == lot_id]

    async def record_event(self, event):
        if event.id == 0:
            event.id = len(self._events) + 1
        self._events.append(event)
        return event


class FakeProductionMachineRepository:
    def __init__(self, machines: list[ProductionMachine] | None = None) -> None:
        self._machines: dict[int, ProductionMachine] = {m.id: m for m in (machines or [])}

    async def get_by_id(self, id: int) -> ProductionMachine | None:
        return self._machines.get(id)

    async def get_by_ids(self, ids: list[int]) -> list:
        found = [await self.get_by_id(i) for i in ids]
        return [item for item in found if item is not None]

    async def get_multi(self, filters):
        raise NotImplementedError

    async def save(self, item):
        raise NotImplementedError

    async def delete(self, item):
        raise NotImplementedError


class FakeLockPlan:
    """Stands in for a request's lock plan where the fakes hold no row
    locks: acquiring records the ids, for assertions."""

    def __init__(self) -> None:
        self.acquired: list[Any] = []

    async def acquire(self, ids: Any) -> None:
        self.acquired.append(ids)


class FakeProductionOrderRepository:
    def __init__(self, orders: list[ProductionOrder] | None = None) -> None:
        self._orders: dict[int, ProductionOrder] = {}
        self._completions: dict[int, list[ProductionOrderCompletion]] = {}
        self._next_id = 1
        self._next_completion_id = 1
        self._next_number = 1
        self.queue_locks: list[tuple[int | None, int | None]] = []
        self.for_update_calls: list[int] = []
        self.lock_calls: list[list[int]] = []
        for o in orders or []:
            self._orders[o.id] = o
            self._next_id = max(self._next_id, o.id + 1)
            if o.completions:
                self._completions[o.id] = list(o.completions)

    @property
    def orders(self) -> dict[int, ProductionOrder]:
        """The stored production orders by id, for assertions."""
        return self._orders

    async def get_by_id(self, id: int) -> ProductionOrder | None:
        return self._orders.get(id)

    async def get_by_id_for_update(self, id: int) -> ProductionOrder | None:
        self.for_update_calls.append(id)
        return self._orders.get(id)

    async def get_by_ids(self, ids: list[int], *, refresh: bool = False) -> list[ProductionOrder]:
        return [self._orders[i] for i in ids if i in self._orders]

    async def lock_for_update(self, ids: list[int]) -> None:
        self.lock_calls.append(list(ids))

    async def get_by_lot_position_id(self, lot_position_id: int) -> list[ProductionOrder]:
        return sorted(
            (o for o in self._orders.values() if o.lot_position_id == lot_position_id),
            key=lambda o: o.id,
        )

    async def get_by_lot_position_ids(
        self, lot_position_ids: list[int], *, refresh: bool = False
    ) -> list[ProductionOrder]:
        return sorted(
            (o for o in self._orders.values() if o.lot_position_id in lot_position_ids),
            key=lambda o: o.id,
        )

    async def get_by_machine_id(self, machine_id: int) -> list[ProductionOrder]:
        return sorted(
            (o for o in self._orders.values() if o.machine_id == machine_id),
            key=lambda o: o.queue_sequence,
        )

    async def get_live_by_machine_ids(self, machine_ids: list[int | None]) -> list[ProductionOrder]:
        return sorted(
            (
                o
                for o in self._orders.values()
                if o.machine_id in machine_ids and o.status not in ("completed", "canceled")
            ),
            key=lambda o: (o.queue_sequence, o.id),
        )

    async def get_multi(self, filters: ProductionOrderFilterDto):
        raise NotImplementedError

    async def save(self, order: ProductionOrder) -> ProductionOrder:
        if order.id == 0:
            order.id = self._next_id
            self._next_id += 1
        order.completions = self._completions.get(order.id, [])
        self._orders[order.id] = order
        return order

    async def save_schedule(self, orders: list[ProductionOrder]) -> None:
        for order in orders:
            if order.id in self._orders:
                self._orders[order.id] = order

    async def next_production_order_number(self, template: str) -> str:
        n = self._next_number
        self._next_number += 1
        return f"PO-TEST-{n:04d}"

    async def lock_queue_scope(
        self, machine_id: int | None, machine_pool_id: int | None = None
    ) -> None:
        self.queue_locks.append((machine_id, machine_pool_id))

    async def next_queue_sequence(
        self, machine_id: int | None, machine_pool_id: int | None = None
    ) -> int:
        if machine_id is not None:
            scoped = await self.get_by_machine_id(machine_id)
        elif machine_pool_id is not None:
            scoped = [
                o
                for o in self._orders.values()
                if o.machine_id is None and o.machine_pool_id == machine_pool_id
            ]
        else:
            scoped = [
                o
                for o in self._orders.values()
                if o.machine_id is None and o.machine_pool_id is None
            ]
        return (max((o.queue_sequence for o in scoped), default=0)) + 1

    async def shift_queue_sequence(self, order_ids: list[int]) -> None:
        for order_id in order_ids:
            if order_id in self._orders:
                self._orders[order_id].queue_sequence = -order_id

    async def get_completions(self, production_order_id: int) -> list[ProductionOrderCompletion]:
        return self._completions.get(production_order_id, [])

    async def save_completion(
        self, completion: ProductionOrderCompletion
    ) -> ProductionOrderCompletion:
        if completion.id == 0:
            completion.id = self._next_completion_id
            self._next_completion_id += 1
        self._completions.setdefault(completion.production_order_id, []).append(completion)
        if completion.production_order_id in self._orders:
            self._orders[completion.production_order_id].completions = self._completions[
                completion.production_order_id
            ]
        return completion


class FakeProductionOrderFileRepository:
    def __init__(self, files: list[ProductionOrderFile] | None = None) -> None:
        self._files = files or []

    async def get_by_id(self, id: int) -> ProductionOrderFile | None:
        return next((f for f in self._files if f.id == id), None)

    async def get_by_item_id(self, item_id: int) -> list[ProductionOrderFile]:
        return [f for f in self._files if f.production_order_id == item_id]

    async def get_by_item_ids(self, item_ids: list[int]) -> list[ProductionOrderFile]:
        return [f for f in self._files if f.production_order_id in item_ids]

    async def get_by_item_id_and_category(
        self, item_id: int, category
    ) -> list[ProductionOrderFile]:
        return [
            f for f in self._files if f.production_order_id == item_id and f.category == category
        ]

    async def save(self, file: ProductionOrderFile) -> ProductionOrderFile:
        if file.id == 0:
            file.id = len(self._files) + 1
            self._files.append(file)
        return file

    async def delete(self, file: ProductionOrderFile) -> None:
        self._files = [f for f in self._files if f.id != file.id]


class FakeAdminSettingsRepository:
    async def get_production(self) -> AdminProductionSettings:
        return AdminProductionSettings(
            id=1,
            production_order_number_format="PO-{seq:04d}",
            default_weekly_hours={0: 480, 1: 480, 2: 480, 3: 480, 4: 480, 5: 0, 6: 0},
            default_external_lead_days=0,
            response_time_days=0,
            require_qa=False,
        )

    async def get_general(self) -> SimpleNamespace:
        # Only the tenant timezone is read; UTC keeps calendar hours in UTC.
        return SimpleNamespace(default_timezone="UTC")

    def __getattr__(self, item):
        raise NotImplementedError(item)


class FakeRecomputeSchedule:
    """Every use case makes exactly one execute_all() call per execution
    rather than looping execute(machine_id) per touched machine, so this
    fake counts calls rather than recording which machine ids were asked
    about; there is no per-machine slice to record."""

    def __init__(self) -> None:
        self.execute_all_calls: int = 0

    async def execute_all(self, response_time_days=None, settings=None):
        self.execute_all_calls += 1
        return []


class FakeEventBus:
    def __init__(self) -> None:
        self.published: list[object] = []

    async def publish(self, event: object) -> None:
        self.published.append(event)


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.committed = False
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.committed = True
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class FakeMachinePoolRepository:
    def __init__(self, pools: list[MachinePool] | None = None) -> None:
        self._pools: dict[int, MachinePool] = {p.id: p for p in (pools or [])}

    async def get_by_id(self, id: int) -> MachinePool | None:
        return self._pools.get(id)

    async def get_by_ids(self, ids: list[int]) -> list:
        found = [await self.get_by_id(i) for i in ids]
        return [item for item in found if item is not None]

    async def get_multi(self, filters):
        raise NotImplementedError

    async def save(self, item):
        raise NotImplementedError

    async def delete(self, item):
        raise NotImplementedError


class FakeProductionOrderInterruptionRepository:
    """In-memory double for IProductionOrderInterruptionRepository. Given the
    orders of a fake order repository (its `_orders`), it keeps every row on
    its order's `interruptions`, where the lifecycle derivation reads them;
    without, it keeps them to itself."""

    def __init__(self, orders: dict[int, ProductionOrder] | None = None) -> None:
        self._orders = orders
        self._loose: list[ProductionOrderInterruption] = []
        self._next_id = itertools.count(1)

    def _rows_of(self, production_order_id: int) -> list[ProductionOrderInterruption]:
        order = self._orders.get(production_order_id) if self._orders is not None else None
        if order is None:
            return [r for r in self._loose if r.production_order_id == production_order_id]
        return order.interruptions

    @property
    def rows(self) -> list[ProductionOrderInterruption]:
        """Every row, of every order, oldest first."""
        held = [i for o in (self._orders or {}).values() for i in o.interruptions]
        return sorted([*held, *self._loose], key=lambda r: (r.paused_at, r.id))

    async def add(self, interruption: ProductionOrderInterruption) -> ProductionOrderInterruption:
        saved = ProductionOrderInterruption(
            id=next(self._next_id),
            production_order_id=interruption.production_order_id,
            paused_at=interruption.paused_at,
            resumed_at=interruption.resumed_at,
            paused_by_id=interruption.paused_by_id,
            resumed_by_id=interruption.resumed_by_id,
            created=interruption.created,
            reason=interruption.reason,
            paused_operator_id=interruption.paused_operator_id,
            resumed_operator_id=interruption.resumed_operator_id,
            ended_by=interruption.ended_by,
            pause_cause=interruption.pause_cause,
        )
        order = self._orders.get(saved.production_order_id) if self._orders is not None else None
        if order is None:
            self._loose.append(saved)
        else:
            order.interruptions = [*order.interruptions, saved]
        return saved

    async def close_open(
        self,
        production_order_id: int,
        resumed_at: datetime,
        resumed_by_id: int,
        *,
        ended_by: InterruptionEndedBy,
        reason: InterruptionReason | None = None,
        resumed_operator_id: int | None = None,
    ) -> ProductionOrderInterruption | None:
        for row in reversed(self._rows_of(production_order_id)):
            if row.resumed_at is not None:
                continue
            if reason is not None and row.reason != reason.value:
                continue
            row.resumed_at = resumed_at
            row.resumed_by_id = resumed_by_id
            row.resumed_operator_id = resumed_operator_id
            row.ended_by = ended_by
            return row
        return None

    async def get_by_order_ids(self, order_ids: list[int]) -> list[ProductionOrderInterruption]:
        return [r for r in self.rows if r.production_order_id in order_ids]

    async def sum_minutes_by_order_ids(self, order_ids: list[int]) -> dict[int, int]:
        totals: dict[int, int] = {}
        for row in self.rows:
            if row.production_order_id not in order_ids or row.resumed_at is None:
                continue
            minutes = round((row.resumed_at - row.paused_at).total_seconds() / 60)
            totals[row.production_order_id] = totals.get(row.production_order_id, 0) + minutes
        return totals


class _UnusedRepository:
    """Stands in for a repository the reconciler must not touch while only
    production orders are reconciled; a call fails the test."""

    def __init__(self, name: str) -> None:
        self._name = name

    def __getattr__(self, method: str):
        async def refuse(*_args: object, **_kwargs: object) -> None:
            raise AssertionError(f"The reconciler called {self._name}.{method}.")

        return refuse


class _UnusedLineAllocations(_UnusedRepository):
    """Stands in for the source allocations while no order line is
    reconciled: a read by line fails the test, a read by demand finds
    nothing. The lock step reads the allocations of a lot's raw material
    demand by demand, to lock the demands that share its lines."""

    async def get_by_demand_item_ids(
        self, demand_item_ids: list[int], *, refresh: bool = False
    ) -> list[object]:
        return []


def production_order_reconciler(
    order_repo: object,
    lot_repo: object,
    bus: object,
    *,
    orders: object | None = None,
    order_items: object | None = None,
    made_demands: object | None = None,
    made_allocations: object | None = None,
    source_demands: object | None = None,
    source_allocations: object | None = None,
) -> LifecycleReconciler:
    """The lifecycle reconciler over these fakes, writing what the app's
    RECONCILED_AGGREGATES says. The lot fake serves the lots and positions
    it derives and the lot locks the use cases take before their orders. A
    test whose use case writes order lines, such as a lot cascade over an
    external position, passes its order and order line fakes; without them
    a position has no line and the reconciler must not read any order. A
    test whose use case writes made or source demands, such as the made
    demands a lot covers or a lot's raw material demand, passes their
    demand and allocation fakes; without them the reconciler finds no
    demand."""
    lines_reconciled = orders is not None and order_items is not None
    lock_log: list[tuple[LifecycleAggregate, tuple[int, ...]]] = []

    def demands(fake: object | None, aggregate: LifecycleAggregate) -> object:
        if fake is None:
            return EmptyRows(aggregate)
        return ReconcilerDemands(fake, aggregate, lock_log)

    def allocations(fake: object | None) -> object:
        return EmptyRows() if fake is None else ReconcilerAllocations(fake)

    repositories = LifecycleRepositories(
        lots=lot_repo,
        production_orders=order_repo,
        orders=ReconcilerOrders(orders) if orders is not None else _UnusedRepository("orders"),
        order_items=(ReconcilerOrderItems(order_items) if order_items is not None else EmptyRows()),
        bought_demands=EmptyRows(LifecycleAggregate.BOUGHT_DEMANDS),
        bought_allocations=(
            EmptyRows() if lines_reconciled else _UnusedRepository("bought_allocations")
        ),
        made_demands=demands(made_demands, LifecycleAggregate.MADE_DEMANDS),
        made_allocations=allocations(made_allocations),
        source_demands=demands(source_demands, LifecycleAggregate.SOURCE_DEMANDS),
        source_allocations=(
            allocations(source_allocations)
            if source_allocations is not None or lines_reconciled
            else _UnusedLineAllocations("source_allocations")
        ),
        quote_requests=EmptyRows(LifecycleAggregate.QUOTE_REQUESTS),
    )
    return LifecycleReconciler(repositories, bus)


def lifecycle_collaborators(
    order_repo: Any,
    lot_repo: object,
    bus: object,
    *,
    orders: object | None = None,
    order_items: object | None = None,
    made_demands: object | None = None,
    made_allocations: object | None = None,
    source_demands: object | None = None,
    source_allocations: object | None = None,
) -> dict[str, object]:
    """The reconciler and the interruption repository a production order
    lifecycle use case takes, over the given fakes: start, pause and cancel
    of an order, and hold, resume, cancel and completion of its lot. See
    production_order_reconciler for the other fakes."""
    return {
        "reconciler": production_order_reconciler(
            order_repo,
            lot_repo,
            bus,
            orders=orders,
            order_items=order_items,
            made_demands=made_demands,
            made_allocations=made_allocations,
            source_demands=source_demands,
            source_allocations=source_allocations,
        ),
        "interruption_repo": FakeProductionOrderInterruptionRepository(order_repo._orders),
    }
