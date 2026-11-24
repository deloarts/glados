"""
In-memory fake repositories and collaborators shared by the production_lot
test modules and by the few modules outside this package that import them
directly.
"""

from collections.abc import Mapping
from datetime import UTC
from datetime import date
from datetime import datetime
from typing import Any

from src.modules.catalogue.domain.entities.admin_settings.made_items import AdminMadeItemSettings
from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.entities.fabrication_method import FabricationMethod
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.entities.source_item import SourceItem
from src.modules.catalogue.domain.policies.item_field_ownership import default_policy
from src.modules.fulfillment.application.services.allocation_fill import LineFillRepos
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.use_cases._demand_family.unarrived_release import (
    UnarrivedLineRelease,
)
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.fulfillment.domain.entities.bought_item_allocation import (
    BoughtItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.bought_item_demand_item import BoughtItemDemandItem
from src.modules.fulfillment.domain.entities.lot_event import LotEvent
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.lot_position_provision import LotPositionProvision
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.entities.made_item_allocation import MadeItemDemandAllocation
from src.modules.fulfillment.domain.entities.made_item_demand_item import MadeItemDemandItem
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.order_item_delivery import OrderItemDelivery
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_machine import ProductionMachine
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.entities.source_item_allocation import (
    SourceItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.source_item_demand_item import SourceItemDemandItem
from src.modules.fulfillment.domain.services.scheduling import ExternalForecast
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    MadeItemDemandFilterDto,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import OrderFilterDto
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.modules.workspace.domain.entities.project import Project
from tests.unit._external_work import external_work_lot_ids
from tests.unit._tenant_settings import TenantSettings
from tests.unit.production_lot._helpers import make_inspection_method
from tests.unit.production_order.fakes import FakeProductionOrderInterruptionRepository
from tests.unit.production_order.fakes import production_order_reconciler


class FakeProductionLotRepository:
    def __init__(self, raw_material_arrived_by_demand: dict[int, float] | None = None) -> None:
        self._lots: dict[int, ProductionLot] = {}
        self._positions: dict[int, LotPosition] = {}
        self._steps: dict[int, LotStep] = {}
        self._provisions: dict[int, LotPositionProvision] = {}
        self._events: list[LotEvent] = []
        self._next_lot_id = 1
        self._next_position_id = 1
        self._next_step_id = 1
        self._next_provision_id = 1
        self._next_event_id = 1
        self._lot_number_seq = 1
        self._raw_material_arrived_by_demand = raw_material_arrived_by_demand or {}
        self.for_update_calls: list[int] = []
        self.lock_calls: list[list[int]] = []
        # Lock and step writes in call order, for a test of the order a
        # structure edit takes its time budget lock in.
        self.journal: list[str] = []
        # A production order fake (its `_orders`) to fill a read position's
        # production orders from, as the repository does; None leaves them as
        # stored.
        self.production_orders: dict[int, Any] | None = None

    @property
    def lots(self) -> dict[int, ProductionLot]:
        """The stored lots by id, for assertions."""
        return self._lots

    async def get_raw_material_arrived_quantity(self, demand_id: int) -> float:
        return self._raw_material_arrived_by_demand.get(demand_id, 0.0)

    async def get_raw_material_arrived_quantities(self, demand_ids: list[int]) -> dict[int, float]:
        return {d: await self.get_raw_material_arrived_quantity(d) for d in demand_ids}

    def _with_orders(self, position: LotPosition) -> LotPosition:
        if self.production_orders is not None:
            position.production_orders = sorted(
                (o for o in self.production_orders.values() if o.lot_position_id == position.id),
                key=lambda o: o.id,
            )
        return position

    def _hydrate(self, lot: ProductionLot) -> ProductionLot:
        positions = sorted(
            (p for p in self._positions.values() if p.lot_id == lot.id), key=lambda p: p.sequence
        )
        for position in positions:
            position.steps = sorted(
                (s for s in self._steps.values() if s.position_id == position.id),
                key=lambda s: s.sequence,
            )
            self._with_orders(position)
        lot.positions = positions
        lot.steps = sorted((s for p in positions for s in p.steps), key=lambda s: s.sequence)
        return lot

    async def get_by_id(self, id: int) -> ProductionLot | None:
        lot = self._lots.get(id)
        return self._hydrate(lot) if lot else None

    async def get_by_id_for_update(self, id: int) -> ProductionLot | None:
        self.for_update_calls.append(id)
        return await self.get_by_id(id)

    async def get_ids_with_external_work(self) -> list[int]:
        return external_work_lot_ids(await self.get_by_ids(sorted(self._lots)))

    async def get_by_ids(self, ids: list[int], *, refresh: bool = False) -> list[ProductionLot]:
        return [self._hydrate(self._lots[i]) for i in ids if i in self._lots]

    async def lock_for_update(self, ids: list[int]) -> None:
        self.lock_calls.append(list(ids))
        self.journal.append("lock lots")

    async def get_by_project_id(
        self, project_id: int, *, refresh: bool = False
    ) -> list[ProductionLot]:
        return [
            self._hydrate(lot)
            for lot in sorted(self._lots.values(), key=lambda lot: lot.id)
            if lot.project_id == project_id
        ]

    async def lock_time_budgets(self, project_id: int) -> None:
        self.journal.append("lock time budgets")

    async def save_step_time_budgets(self, budgets: Mapping[int, float | None]) -> None:
        for step_id, budget in budgets.items():
            if step_id in self._steps:
                self._steps[step_id].time_budget_per_piece = budget

    async def get_multi(self, filters):
        raise NotImplementedError

    async def save(self, lot: ProductionLot) -> ProductionLot:
        if lot.id == 0:
            lot.id = self._next_lot_id
            self._next_lot_id += 1
        self._lots[lot.id] = lot
        return self._hydrate(lot)

    async def next_lot_number(self, template: str) -> str:
        n = self._lot_number_seq
        self._lot_number_seq += 1
        return f"LOT-TEST-{n:04d}"

    async def get_steps(self, lot_id: int) -> list[LotStep]:
        return sorted(
            (s for s in self._steps.values() if s.lot_id == lot_id), key=lambda s: s.sequence
        )

    async def get_step_by_id(self, step_id: int) -> LotStep | None:
        return self._steps.get(step_id)

    async def save_step(self, step: LotStep) -> LotStep:
        self.journal.append("write step")
        if step.id == 0:
            step.id = self._next_step_id
            self._next_step_id += 1
        self._steps[step.id] = step
        return step

    async def delete_step(self, step: LotStep) -> None:
        self.journal.append("write step")
        self._steps.pop(step.id, None)

    async def reorder_steps(self, lot_id: int, ordered_step_ids: list[int]) -> list[LotStep]:
        for sequence, step_id in enumerate(ordered_step_ids, start=1):
            self._steps[step_id].sequence = sequence
        return await self.get_steps(lot_id)

    async def reorder_positions(
        self, lot_id: int, ordered_position_ids: list[int]
    ) -> list[LotPosition]:
        for sequence, position_id in enumerate(ordered_position_ids, start=1):
            self._positions[position_id].sequence = sequence
        return await self.get_positions(lot_id)

    async def get_positions(self, lot_id: int) -> list[LotPosition]:
        positions = sorted(
            (p for p in self._positions.values() if p.lot_id == lot_id), key=lambda p: p.sequence
        )
        for position in positions:
            position.steps = sorted(
                (s for s in self._steps.values() if s.position_id == position.id),
                key=lambda s: s.sequence,
            )
        return positions

    async def get_position_by_id(self, position_id: int) -> LotPosition | None:
        position = self._positions.get(position_id)
        if not position:
            return None
        position.steps = sorted(
            (s for s in self._steps.values() if s.position_id == position.id),
            key=lambda s: s.sequence,
        )
        return self._with_orders(position)

    async def get_positions_by_ids(self, position_ids: list[int]) -> list:
        positions = [await self.get_position_by_id(i) for i in position_ids]
        return [p for p in positions if p is not None]

    async def save_position(self, position: LotPosition) -> LotPosition:
        if position.id == 0:
            position.id = self._next_position_id
            self._next_position_id += 1
        self._positions[position.id] = position
        return position

    async def save_position_forecasts(self, forecasts: list[ExternalForecast]) -> None:
        for forecast in forecasts:
            position = self._positions.get(forecast.position_id)
            if position is not None:
                position.planned_pickup_date = forecast.planned_pickup_date
                position.planned_delivery_date = forecast.planned_delivery_date

    async def delete_position(self, position: LotPosition) -> None:
        self._positions.pop(position.id, None)

    async def get_quote_request_ids_of_positions(self, position_ids: list[int]) -> list[int]:
        return []

    async def get_provisions(self, lot_position_id: int):
        return sorted(
            (p for p in self._provisions.values() if p.lot_position_id == lot_position_id),
            key=lambda p: p.id,
        )

    async def save_provision(self, provision):
        if provision.id == 0:
            provision.id = self._next_provision_id
            self._next_provision_id += 1
        self._provisions[provision.id] = provision
        return provision

    async def get_events(self, lot_id: int) -> list[LotEvent]:
        return sorted(
            (e for e in self._events if e.lot_id == lot_id),
            key=lambda e: (e.occurred_at, e.id),
        )

    async def record_event(self, event: LotEvent) -> LotEvent:
        if event.id == 0:
            event.id = self._next_event_id
            self._next_event_id += 1
        self._events.append(event)
        return event


class FakeMadeItemRepository:
    def __init__(self, items: list[MadeItem]) -> None:
        self._items = {i.id: i for i in items}

    async def get_by_id(self, id: int) -> MadeItem | None:
        return self._items.get(id)

    async def get_multi(self, filters):
        raise NotImplementedError

    async def save(self, item):
        raise NotImplementedError

    async def delete(self, item) -> None:
        raise NotImplementedError

    async def merge_article_groups(self, source_id: int, target_id: int) -> None:
        raise NotImplementedError

    async def get_processes(self, made_item_id: int):
        raise NotImplementedError

    async def get_process_by_id(self, process_id: int):
        raise NotImplementedError

    async def save_process(self, process):
        raise NotImplementedError

    async def delete_process(self, process) -> None:
        raise NotImplementedError

    async def reorder_processes(self, made_item_id: int, ordered_process_ids: list[int]):
        raise NotImplementedError


class FakeMadeItemDemandRepository:
    def __init__(self, demands: list[MadeItemDemandItem] | None = None) -> None:
        self._demands: dict[int, MadeItemDemandItem] = {d.id: d for d in (demands or [])}
        self.for_update_calls: list[int] = []

    @property
    def demands(self) -> dict[int, MadeItemDemandItem]:
        """The stored demands by id, for assertions."""
        return self._demands

    async def get_by_id(self, id: int) -> MadeItemDemandItem | None:
        return self._demands.get(id)

    async def get_by_id_for_update(self, id: int) -> MadeItemDemandItem | None:
        self.for_update_calls.append(id)
        return self._demands.get(id)

    async def get_by_ids(
        self, ids: list[int], *, refresh: bool = False
    ) -> list[MadeItemDemandItem]:
        return [self._demands[i] for i in ids if i in self._demands]

    async def get_by_project_id(self, project_id: int):
        raise NotImplementedError

    async def get_pipeline(self, terminal_since: date):
        raise NotImplementedError

    async def get_multi(self, filters: MadeItemDemandFilterDto):
        demands = list(self._demands.values())
        if filters.statuses:
            demands = [d for d in demands if d.status in filters.statuses]
        elif filters.status:
            demands = [d for d in demands if d.status == filters.status]
        if filters.project_id:
            demands = [d for d in demands if d.project_id == filters.project_id]
        if filters.made_item_id:
            demands = [d for d in demands if d.made_item_id == filters.made_item_id]
        return len(demands), demands

    async def get_by_statuses(self, statuses: list[str]) -> list[MadeItemDemandItem]:
        return [d for d in self._demands.values() if d.status in statuses]

    async def save(self, demand: MadeItemDemandItem) -> MadeItemDemandItem:
        self._demands[demand.id] = demand
        return demand

    async def delete(self, demand) -> None:
        raise NotImplementedError


class FakeMadeItemAllocationRepository:
    def __init__(self, allocations: list[MadeItemDemandAllocation] | None = None) -> None:
        self._allocations: list[MadeItemDemandAllocation] = list(allocations or [])

    async def get_by_demand_item_id(self, demand_item_id: int) -> list[MadeItemDemandAllocation]:
        return [a for a in self._allocations if a.demand_item_id == demand_item_id]

    async def get_by_demand_item_ids(self, demand_item_ids: list[int], *, refresh: bool = False):
        return [a for a in self._allocations if a.demand_item_id in demand_item_ids]

    async def get_by_lot_id(self, lot_id: int) -> list[MadeItemDemandAllocation]:
        return [a for a in self._allocations if a.lot_id == lot_id]

    async def get_by_lot_ids(self, lot_ids: list[int], *, refresh: bool = False) -> list:
        return [a for lot_id in lot_ids for a in await self.get_by_lot_id(lot_id)]

    async def get_allocated_quantity(self, demand_item_id: int) -> float:
        return sum(a.quantity for a in await self.get_by_demand_item_id(demand_item_id))

    async def save(self, allocation: MadeItemDemandAllocation) -> MadeItemDemandAllocation:
        # Upsert by (demand_item_id, lot_id), matching
        # SqlAlchemyMadeItemAllocationRepository.save's real behavior:
        # without this, re-saving an existing pair (e.g. shrinking an
        # allocation) would silently duplicate the row instead of
        # updating it in place.
        for i, existing in enumerate(self._allocations):
            if (
                existing.demand_item_id == allocation.demand_item_id
                and existing.lot_id == allocation.lot_id
            ):
                self._allocations[i] = allocation
                return allocation
        self._allocations.append(allocation)
        return allocation

    async def delete(self, allocation) -> None:
        self._allocations = [a for a in self._allocations if a is not allocation]


class FakeAdminSettingsRepository:
    def __init__(
        self, require_qa: bool = False, default_inspection_method_id: int | None = 1
    ) -> None:
        self._require_qa = require_qa
        self._default_inspection_method_id = default_inspection_method_id

    async def get_made_items(self) -> AdminMadeItemSettings:
        return AdminMadeItemSettings(
            id=1,
            item_number_format="MADE-{seq:04d}",
            lot_number_format="LOT-{seq:04d}",
            part_number_auto=False,
            part_number_editable=True,
            revision_start="0",
            revision_separator=":",
            revision_skip_ambiguous_letters=False,
            revision_only_newest_editable=True,
            revision_predecessor_status_web="ask",
            revision_predecessor_status_pdm="replaced",
            revision_field_policy=default_policy(),
            web_creation_allowed=True,
            pdm_part_number_pattern="",
        )

    async def get_production(self) -> AdminProductionSettings:
        return AdminProductionSettings(
            id=1,
            production_order_number_format="PON-{seq:04d}",
            default_weekly_hours={0: 480, 1: 480, 2: 480, 3: 480, 4: 480, 5: 0, 6: 0},
            default_external_lead_days=0,
            response_time_days=1,
            require_qa=self._require_qa,
            default_inspection_method_id=self._default_inspection_method_id,
        )

    def __getattr__(self, item):
        raise NotImplementedError(item)


class FakeInspectionMethodRepository:
    def __init__(self, methods: list | None = None) -> None:
        self._methods = {m.id: m for m in (methods or [make_inspection_method(id=1)])}

    async def get_by_id(self, id: int):
        return self._methods.get(id)

    async def get_live_names(self) -> list[tuple[int, LocalizedText]]:
        raise NotImplementedError

    async def get_multi(self, filters):
        raise NotImplementedError

    async def save(self, inspection_method):
        raise NotImplementedError

    async def delete(self, inspection_method) -> None:
        raise NotImplementedError


class FakeProductionMachineRepository:
    """get_by_id only; the only method create_lot.py's default-machine
    pre-fill resolution calls. Mirrors the real repository's archived=False
    filter: an archived machine reads as not found, exactly what lets
    _resolve_default_machine_id's lenient fallback work
    without checking .archived itself."""

    def __init__(self, machines: list[ProductionMachine] | None = None) -> None:
        self._machines = {m.id: m for m in (machines or [])}

    async def get_by_id(self, id: int) -> ProductionMachine | None:
        machine = self._machines.get(id)
        return machine if machine and not machine.archived else None

    async def get_by_ids(self, ids: list[int]) -> list:
        found = [await self.get_by_id(i) for i in ids]
        return [item for item in found if item is not None]


class FakeFabricationMethodRepository:
    def __init__(self, methods: list[FabricationMethod]) -> None:
        self._methods = {m.id: m for m in methods}

    async def get_by_id(self, id: int) -> FabricationMethod | None:
        return self._methods.get(id)

    async def get_live_names(self) -> list[tuple[int, LocalizedText]]:
        raise NotImplementedError

    async def get_multi(self, filters):
        raise NotImplementedError


class FakeOrderRepository:
    def __init__(self, orders: list[Order]) -> None:
        self._orders = {o.id: o for o in orders}

    @property
    def orders(self) -> dict[int, Order]:
        """The stored orders by id, for assertions."""
        return self._orders

    async def get_by_id(self, id: int) -> Order | None:
        return self._orders.get(id)

    async def get_by_ids(self, ids: list[int], *, refresh: bool = False) -> list[Order]:
        return [self._orders[i] for i in ids if i in self._orders]

    async def get_by_order_number(self, order_number: str):
        raise NotImplementedError

    async def get_multi(self, filters: OrderFilterDto):
        raise NotImplementedError

    async def save(self, order: Order) -> Order:
        self._orders[order.id] = order
        return order

    async def delete(self, order) -> None:
        raise NotImplementedError

    async def next_order_number(self, template: str) -> str:
        raise NotImplementedError

    async def get_project_summary(self, project_id: int):
        raise NotImplementedError


class FakeOrderItemRepository:
    def __init__(self, items: list[OrderItem] | None = None) -> None:
        self._items: dict[int, OrderItem] = {i.id: i for i in (items or [])}
        self._next_id = max((i.id for i in (items or [])), default=0) + 1

    @property
    def items(self) -> dict[int, OrderItem]:
        """The stored order items by id, for assertions."""
        return self._items

    async def get_by_id(self, id: int) -> OrderItem | None:
        return self._items.get(id)

    async def get_by_id_for_update(self, id: int) -> OrderItem | None:
        return self._items.get(id)

    async def get_by_ids(self, ids: list[int], *, refresh: bool = False) -> list[OrderItem]:
        return [self._items[i] for i in ids if i in self._items]

    async def get_by_order_id(self, order_id: int) -> list[OrderItem]:
        return [i for i in self._items.values() if i.order_id == order_id]

    async def get_by_order_ids(
        self, order_ids: list[int], *, refresh: bool = False
    ) -> list[OrderItem]:
        return [i for i in self._items.values() if i.order_id in order_ids]

    async def get_by_bought_item_id(self, bought_item_id: int):
        raise NotImplementedError

    async def get_by_lot_position_id(self, lot_position_id: int) -> OrderItem | None:
        """The live line, else the newest canceled one, as the repository
        returns them."""
        lines = sorted(
            (i for i in self._items.values() if i.lot_position_id == lot_position_id),
            key=lambda i: (i.canceled_at is not None, -i.id),
        )
        return lines[0] if lines else None

    async def get_by_lot_position_ids(
        self, lot_position_ids: list[int], *, refresh: bool = False
    ) -> list[OrderItem]:
        return [i for i in self._items.values() if i.lot_position_id in lot_position_ids]

    async def lock_for_update(self, ids: list[int]) -> None:
        return None

    async def next_position(self, order_id: int) -> int:
        return len(await self.get_by_order_id(order_id)) + 1

    async def save(self, item: OrderItem) -> OrderItem:
        if item.id == 0:
            item.id = self._next_id
            self._next_id += 1
        self._items[item.id] = item
        return item

    async def delete(self, item: OrderItem) -> None:
        self._items.pop(item.id, None)


class FakeOrderItemDeliveryRepository:
    def __init__(self) -> None:
        self._deliveries: list[OrderItemDelivery] = []

    async def get_by_order_item_id(self, order_item_id: int) -> list[OrderItemDelivery]:
        return [d for d in self._deliveries if d.order_item_id == order_item_id]

    async def get_by_order_item_ids(self, order_item_ids: list[int]):
        return [d for d in self._deliveries if d.order_item_id in order_item_ids]

    async def save(self, delivery: OrderItemDelivery) -> OrderItemDelivery:
        self._deliveries.append(delivery)
        return delivery


class FakeBoughtItemAllocationRepository:
    def __init__(self, allocations: list[BoughtItemDemandAllocation] | None = None) -> None:
        self._allocations: list[BoughtItemDemandAllocation] = list(allocations or [])

    async def get_by_order_item_id(self, order_item_id: int):
        return [a for a in self._allocations if a.order_item_id == order_item_id]

    async def get_by_demand_item_id(self, demand_item_id: int):
        return [a for a in self._allocations if a.demand_item_id == demand_item_id]

    async def get_by_order_item_ids(self, order_item_ids: list[int], *, refresh: bool = False):
        return [a for a in self._allocations if a.order_item_id in order_item_ids]

    async def get_allocated_quantity(self, demand_item_id: int) -> float:
        return sum(a.quantity for a in self._allocations if a.demand_item_id == demand_item_id)

    async def save(self, allocation: BoughtItemDemandAllocation) -> BoughtItemDemandAllocation:
        await self.delete(allocation)
        self._allocations.append(allocation)
        return allocation

    async def delete(self, allocation: BoughtItemDemandAllocation) -> None:
        self._allocations = [
            a
            for a in self._allocations
            if not (
                a.demand_item_id == allocation.demand_item_id
                and a.order_item_id == allocation.order_item_id
            )
        ]

    def __getattr__(self, item):
        raise NotImplementedError(item)


class FakeBoughtItemDemandRepository:
    def __init__(self, demands: list[BoughtItemDemandItem] | None = None) -> None:
        self._demands: dict[int, BoughtItemDemandItem] = {d.id: d for d in (demands or [])}

    async def get_by_id(self, id: int):
        return self._demands.get(id)

    async def get_by_id_for_update(self, id: int):
        return self._demands.get(id)

    async def save(self, demand: BoughtItemDemandItem) -> BoughtItemDemandItem:
        self._demands[demand.id] = demand
        return demand

    def __getattr__(self, item):
        raise NotImplementedError(item)


class FakeProductionOrderRepository:
    """Returns the stored orders themselves and keeps an order's completions
    on it, as the lifecycle reconciler reads them there."""

    def __init__(self, orders: list[ProductionOrder] | None = None) -> None:
        self._orders: dict[int, ProductionOrder] = {o.id: o for o in (orders or [])}
        self._next_id = max((o.id for o in (orders or [])), default=0) + 1
        self._completions: dict[int, list] = {
            o.id: list(o.completions) for o in (orders or []) if o.completions
        }
        self._next_completion_id = 1
        self.lock_calls: list[list[int]] = []

    @property
    def orders(self) -> dict[int, ProductionOrder]:
        """The stored production orders by id, for assertions."""
        return self._orders

    async def get_by_lot_position_id(self, lot_position_id: int) -> list[ProductionOrder]:
        return [o for o in self._orders.values() if o.lot_position_id == lot_position_id]

    async def get_by_lot_position_ids(
        self, lot_position_ids: list[int], *, refresh: bool = False
    ) -> list[ProductionOrder]:
        return sorted(
            (o for o in self._orders.values() if o.lot_position_id in lot_position_ids),
            key=lambda o: o.id,
        )

    async def get_by_ids(self, ids: list[int], *, refresh: bool = False) -> list[ProductionOrder]:
        return [self._orders[i] for i in ids if i in self._orders]

    async def lock_for_update(self, ids: list[int]) -> None:
        self.lock_calls.append(list(ids))

    async def save(self, order: ProductionOrder) -> ProductionOrder:
        if order.id == 0:
            order.id = self._next_id
            self._next_id += 1
        self._orders[order.id] = order
        return order

    async def get_completions(self, production_order_id: int) -> list:
        return self._completions.get(production_order_id, [])

    async def save_completion(self, completion):
        if completion.id == 0:
            completion.id = self._next_completion_id
            self._next_completion_id += 1
        self._completions.setdefault(completion.production_order_id, []).append(completion)
        if completion.production_order_id in self._orders:
            self._orders[completion.production_order_id].completions = self._completions[
                completion.production_order_id
            ]
        return completion

    async def next_production_order_number(self, template: str) -> str:
        return "PO-TEST-0001"

    async def lock_queue_scope(
        self, machine_id: int | None, machine_pool_id: int | None = None
    ) -> None:
        return None

    async def next_queue_sequence(
        self, machine_id: int | None, machine_pool_id: int | None = None
    ) -> int:
        return 1

    def __getattr__(self, item):
        raise NotImplementedError(item)


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


class FakeBoughtItemRepository:
    def __init__(self, items: list[BoughtItem] | None = None):
        self._items: dict[int, BoughtItem] = {i.id: i for i in (items or [])}

    async def get_by_id(self, id: int) -> BoughtItem | None:
        return self._items.get(id)


class FakeSourceItemRepository:
    def __init__(self, items: list[SourceItem] | None = None):
        self._items: dict[int, SourceItem] = {i.id: i for i in (items or [])}

    async def get_by_id(self, id: int) -> SourceItem | None:
        return self._items.get(id)


class FakeSourceItemDemandRepository:
    def __init__(self, demands: list[SourceItemDemandItem] | None = None):
        self._demands: dict[int, SourceItemDemandItem] = {d.id: d for d in (demands or [])}
        self._next_id = max([d.id for d in (demands or [])], default=0) + 1

    @property
    def demands(self) -> dict[int, SourceItemDemandItem]:
        """The stored demands by id, for assertions."""
        return self._demands

    async def get_by_id(self, id: int) -> SourceItemDemandItem | None:
        return self._demands.get(id)

    async def get_by_id_for_update(self, id: int) -> SourceItemDemandItem | None:
        return self._demands.get(id)

    async def get_multi(self, filters):
        """The lot, canceled and id-order filters and the limit the use cases
        read through; any other filter is not served."""
        rows = [
            d
            for d in self._demands.values()
            if (not filters.lot_id or d.lot_id in filters.lot_id)
            and not (
                filters.ignore_canceled
                and (d.status == SourceItemDemandStatus.CANCELED or d.canceled_at is not None)
            )
        ]
        rows.sort(key=lambda d: d.id, reverse=filters.order_dir != "asc")
        return len(rows), rows[: filters.limit] if filters.limit else rows

    async def save(self, demand: SourceItemDemandItem) -> SourceItemDemandItem:
        if demand.id == 0:
            demand.id = self._next_id
            self._next_id += 1
        else:
            self._next_id = max(self._next_id, demand.id + 1)
        self._demands[demand.id] = demand
        return demand


class FakeSourceItemAllocationRepository:
    def __init__(self, allocations: list[SourceItemDemandAllocation] | None = None):
        self.allocations: list[SourceItemDemandAllocation] = list(allocations or [])

    async def get_by_demand_item_id(self, demand_item_id: int) -> list[SourceItemDemandAllocation]:
        return [a for a in self.allocations if a.demand_item_id == demand_item_id]

    async def get_allocated_quantity(self, demand_item_id: int) -> float:
        return sum(a.quantity for a in self.allocations if a.demand_item_id == demand_item_id)

    async def get_by_order_item_id(self, order_item_id: int) -> list[SourceItemDemandAllocation]:
        return [a for a in self.allocations if a.order_item_id == order_item_id]

    async def get_by_order_item_ids(
        self, order_item_ids: list[int], *, refresh: bool = False
    ) -> list[SourceItemDemandAllocation]:
        return [a for a in self.allocations if a.order_item_id in order_item_ids]

    async def save(self, allocation: SourceItemDemandAllocation) -> SourceItemDemandAllocation:
        self.allocations = [
            a
            for a in self.allocations
            if not (
                a.demand_item_id == allocation.demand_item_id
                and a.order_item_id == allocation.order_item_id
            )
        ]
        self.allocations.append(allocation)
        return allocation

    async def delete(self, allocation: SourceItemDemandAllocation) -> None:
        self.allocations = [a for a in self.allocations if a is not allocation]


class FakeRecomputeMachineSchedule:
    """The use cases below make at most one execute_all() call per
    execution rather than looping execute(machine_id) once per touched
    machine, so this fake counts calls
    instead of recording which machine ids were asked about."""

    def __init__(self) -> None:
        self.calls: int = 0

    async def execute_all(self, response_time_days=None, settings=None):
        self.calls += 1
        return []


class FakeProjectRepository:
    """Every project id names an active project unless the test seeds a
    project of its own under that id, so a use case that checks the project
    of its lot or line needs no seeding. The share locks are recorded for a
    test of which projects a writer locks."""

    def __init__(self, projects: list[Project] | None = None) -> None:
        self._projects: dict[int, Project] = {p.id: p for p in (projects or [])}
        self.share_locked: list[list[int]] = []

    async def lock_for_update(self, id: int) -> None:
        return None

    async def lock_for_share(self, ids: list[int]) -> None:
        self.share_locked.append(list(ids))

    async def get_by_id(self, id: int) -> Project | None:
        return self._projects.get(id) or Project(
            id=id, created=datetime(2026, 1, 1, tzinfo=UTC), project_number=f"P-{id:04d}"
        )


def fake_line_release(
    source_allocations: "FakeSourceItemAllocationRepository",
    order_items: object | None = None,
) -> UnarrivedLineRelease[Any]:
    """The source family's release of unarrived line allocations over the
    fakes, for a use case that settles a placed source demand. Without
    `order_items` no line exists, so nothing has arrived anywhere."""
    from tests.unit.order._helpers import FakeAllocationRepository
    from tests.unit.order._helpers import FakeOrderItemRepository

    return UnarrivedLineRelease(
        source_allocations,  # type: ignore[arg-type]
        LineFillRepos(
            bought=FakeAllocationRepository(),  # type: ignore[arg-type]
            source=source_allocations,  # type: ignore[arg-type]
        ),
        order_items or FakeOrderItemRepository(),  # type: ignore[arg-type]
    )


def lot_reconciler(
    lot_repo: Any,
    order_repo: Any | None = None,
    *,
    orders: Any | None = None,
    order_items: Any | None = None,
    bus: Any | None = None,
    made_demands: Any | None = None,
    made_allocations: Any | None = None,
    source_demands: Any | None = None,
    source_allocations: Any | None = None,
) -> LifecycleReconciler:
    """The lifecycle reconciler over a lot test's own fakes, which writes
    what the app's RECONCILED_AGGREGATES says (production_order_reconciler).
    It publishes on a bus of its own unless the test passes one, so the
    events a test counts on its use case's bus stay those of the use case."""
    return production_order_reconciler(
        order_repo if order_repo is not None else FakeProductionOrderRepository(),
        lot_repo,
        bus if bus is not None else FakeEventBus(),
        orders=orders,
        order_items=order_items,
        made_demands=made_demands,
        made_allocations=made_allocations,
        source_demands=source_demands,
        source_allocations=source_allocations,
    )


def disposition_collaborators(
    *,
    order_items: Any | None = None,
    orders: Any | None = None,
    source_item_demands: Any | None = None,
    source_item_allocations: Any | None = None,
) -> dict[str, object]:
    """The order line, order, source demand, source allocation and bought
    allocation repositories a disposition writes besides the lot, empty
    fakes unless the test passes its own, and the settings whose tenant
    timezone gives a completion or scrap its day, UTC here."""
    return {
        "settings_repo": TenantSettings(),
        "bought_allocation_repo": FakeBoughtItemAllocationRepository(),
        "order_item_repo": order_items if order_items is not None else FakeOrderItemRepository(),
        "parent_order_repo": orders if orders is not None else FakeOrderRepository([]),
        "source_item_demand_repo": (
            source_item_demands
            if source_item_demands is not None
            else FakeSourceItemDemandRepository()
        ),
        "source_item_allocation_repo": (
            source_item_allocations
            if source_item_allocations is not None
            else FakeSourceItemAllocationRepository()
        ),
    }


def completion_collaborators(order_repo: Any, **given: object) -> dict[str, object]:
    """The repositories a completion's disposition of rejected pieces
    writes besides the lot, as keyword arguments of
    RecordProductionOrderCompletion: the disposition's and an interruption
    repository over `order_repo`'s orders, empty fakes except those the
    test passes."""
    return {
        **disposition_collaborators(),
        "interruption_repo": FakeProductionOrderInterruptionRepository(
            getattr(order_repo, "_orders", None)
        ),
        **given,
    }


def delivery_collaborators(**given: object) -> dict[str, object]:
    """The lot, production order, interruption, source demand, source
    allocation and bought allocation repositories a delivery booking reads
    and writes besides its line, as keyword arguments of
    ProcessOrderItemDelivery: empty fakes, except those the test passes to
    share with its reconciler or its assertions."""
    production_orders = given.get("production_order_repo", FakeProductionOrderRepository())
    return {
        "lot_repo": FakeProductionLotRepository(),
        "production_order_repo": production_orders,
        "interruption_repo": FakeProductionOrderInterruptionRepository(
            getattr(production_orders, "_orders", None)
        ),
        "source_item_demand_repo": FakeSourceItemDemandRepository(),
        "source_item_allocation_repo": FakeSourceItemAllocationRepository(),
        "bought_item_allocation_repo": FakeBoughtItemAllocationRepository(),
        **given,
    }
