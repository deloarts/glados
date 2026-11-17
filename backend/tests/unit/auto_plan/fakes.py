"""
In-memory fake repositories shared by the auto_plan test modules.
"""

from types import SimpleNamespace

from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.fulfillment.domain.entities.machine_pool import MachinePool
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_machine import ProductionMachine
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.services.scheduling import ExternalForecast
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    ProductionOrderPlanningFields,
)
from src.modules.platform.adapters.outbound.persistence.pagination import clamp_page
from src.modules.platform.const import SERVER_DEFAULT_TIMEZONE

# The tenant's default timezone FakeSettingsRepo reports, the seeded one.
TENANT_TIMEZONE = SERVER_DEFAULT_TIMEZONE


class FakeOrderRepo:
    def __init__(self, orders: list[ProductionOrder]) -> None:
        self.orders = {o.id: o for o in orders}

    async def get_by_id(self, id: int) -> ProductionOrder | None:
        return self.orders.get(id)

    async def get_by_ids(self, ids: list[int], *, refresh: bool = False) -> list[ProductionOrder]:
        return [self.orders[i] for i in ids if i in self.orders]

    async def get_by_lot_position_id(self, lot_position_id: int) -> list[ProductionOrder]:
        return [o for o in self.orders.values() if o.lot_position_id == lot_position_id]

    async def get_by_lot_position_ids(
        self, lot_position_ids: list[int], *, refresh: bool = False
    ) -> list[ProductionOrder]:
        return [o for o in self.orders.values() if o.lot_position_id in lot_position_ids]

    async def get_by_machine_id(self, machine_id: int | None) -> list[ProductionOrder]:
        return [o for o in self.orders.values() if o.machine_id == machine_id]

    async def get_live_by_machine_ids(self, machine_ids: list[int | None]) -> list[ProductionOrder]:
        return sorted(
            (
                o
                for o in self.orders.values()
                if o.machine_id in machine_ids and o.status not in ("completed", "canceled")
            ),
            key=lambda o: (o.queue_sequence, o.id),
        )

    async def get_all_non_terminal(self) -> list[ProductionOrder]:
        # Every order not COMPLETED/CANCELED, sorted the same way the real
        # adapter orders them.
        terminal = {ProductionOrderStatus.COMPLETED.value, ProductionOrderStatus.CANCELED.value}
        return sorted(
            (o for o in self.orders.values() if o.status not in terminal),
            key=lambda o: (o.queue_sequence, o.id),
        )

    async def save(self, order: ProductionOrder) -> ProductionOrder:
        self.orders[order.id] = order
        return order

    async def save_schedule(self, orders: list[ProductionOrder]) -> None:
        for order in orders:
            if order.id in self.orders:
                self.orders[order.id] = order

    async def save_planning_fields(self, plans: list[ProductionOrderPlanningFields]) -> None:
        # Same contract as the real adapter: the three planning fields only,
        # and only on an order whose pin still matches the plan's.
        for plan in plans:
            order = self.orders.get(plan.order_id)
            if order is None or order.pinned != plan.pinned_when_read:
                continue
            order.planned_start = plan.planned_start
            order.planned_end = plan.planned_end
            order.planned_by_id = plan.planned_by_id

    async def lock_for_update(self, ids: list[int]) -> None:
        self.locked = sorted(ids)

    async def lock_queue_scope(
        self, machine_id: int | None, machine_pool_id: int | None = None
    ) -> None:
        # SQLite/fake: matches the real adapter's no-op degradation for a
        # non-Postgres bind. AutoPlan calls this unconditionally (see
        # _lock_and_seed_queue_sequences), nothing here needs to observe it.
        pass

    async def next_queue_sequence(
        self, machine_id: int | None, machine_pool_id: int | None = None
    ) -> int:
        if machine_id is not None:
            scoped = await self.get_by_machine_id(machine_id)
        elif machine_pool_id is not None:
            scoped = [
                o
                for o in self.orders.values()
                if o.machine_id is None and o.machine_pool_id == machine_pool_id
            ]
        else:
            scoped = [
                o
                for o in self.orders.values()
                if o.machine_id is None and o.machine_pool_id is None
            ]
        return (max((o.queue_sequence for o in scoped), default=0)) + 1

    async def shift_queue_sequence(self, order_ids: list[int]) -> None:
        for order_id in order_ids:
            if order_id in self.orders:
                self.orders[order_id].queue_sequence = -order_id


class FakeLotRepo:
    def __init__(self, lots: list[ProductionLot]) -> None:
        self.lots = {lot.id: lot for lot in lots}

    async def get_by_id(self, id: int) -> ProductionLot | None:
        return self.lots.get(id)

    async def get_by_ids(self, ids: list[int], *, refresh: bool = False) -> list:
        found = [await self.get_by_id(i) for i in ids]
        return [item for item in found if item is not None]

    async def get_raw_material_arrived_quantity(self, demand_id: int) -> float:
        # Additive stub for the material-availability gate (see make_lot's
        # material_arrived param, and scheduling.
        # is_unplannable_for_missing_material): fixtures model an
        # abundant, already-arrived supply for any linked demand id by
        # default. A fixture testing the "not arrived" path instead
        # builds its lot with material_arrived=False (input_demand_id
        # left unset entirely, see _resolve_raw_material_arrived's own
        # "no demand" branch) and never reaches this method at all.
        return 1_000_000.0

    async def get_raw_material_arrived_quantities(self, demand_ids: list[int]) -> dict[int, float]:
        return {d: await self.get_raw_material_arrived_quantity(d) for d in demand_ids}

    async def save_position_forecasts(self, forecasts: list[ExternalForecast]) -> None:
        # Positions live inside the held lot objects, so writing onto them
        # is what the recompute's callers then observe.
        positions = {p.id: p for lot in self.lots.values() for p in lot.positions}
        for forecast in forecasts:
            position = positions.get(forecast.position_id)
            if position is not None:
                position.planned_pickup_date = forecast.planned_pickup_date
                position.planned_delivery_date = forecast.planned_delivery_date


class FakeEmptyRepo:
    async def get_by_id(self, id: int):
        return None

    async def get_by_ids(self, ids: list[int], *, refresh: bool = False) -> list:
        return []

    async def get_by_lot_id(self, lot_id: int) -> list:
        return []

    async def get_by_lot_ids(self, lot_ids: list[int], *, refresh: bool = False) -> list:
        return [a for lot_id in lot_ids for a in await self.get_by_lot_id(lot_id)]

    async def get_by_lot_position_id(self, lot_position_id: int):
        return None

    async def get_by_lot_position_ids(
        self, lot_position_ids: list[int], *, refresh: bool = False
    ) -> list:
        return []

    async def get_by_demand_item_id(self, demand_item_id: int) -> list:
        return []

    async def get_by_demand_item_ids(
        self, demand_item_ids: list[int], *, refresh: bool = False
    ) -> list:
        return [a for d in demand_item_ids for a in await self.get_by_demand_item_id(d)]


class FakeMachineRepo:
    def __init__(self, machines: list[ProductionMachine]) -> None:
        self.machines = {m.id: m for m in machines}

    async def get_by_id(self, id: int) -> ProductionMachine | None:
        return self.machines.get(id)

    async def get_by_ids(self, ids: list[int]) -> list:
        found = [await self.get_by_id(i) for i in ids]
        return [item for item in found if item is not None]

    async def get_multi(self, filters) -> tuple[int, list[ProductionMachine]]:
        values = list(self.machines.values())
        return len(values), values

    async def get_all(self) -> list[ProductionMachine]:
        # Unlike get_multi above, ignoring filters is exactly correct here
        # (get_all takes none), not a bug being masked.
        return list(self.machines.values())


class FakePoolRepo:
    def __init__(self, pools: list[MachinePool]) -> None:
        self.pools = {p.id: p for p in pools}

    async def get_by_id(self, id: int) -> MachinePool | None:
        return self.pools.get(id)

    async def get_by_ids(self, ids: list[int]) -> list:
        found = [await self.get_by_id(i) for i in ids]
        return [item for item in found if item is not None]

    async def get_multi(self, filters) -> tuple[int, list[MachinePool]]:
        values = list(self.pools.values())
        return len(values), values

    async def get_all(self) -> list[MachinePool]:
        # See FakeMachineRepo.get_all.
        return list(self.pools.values())


class ClampingFakeMachineRepo:
    """Unlike FakeMachineRepo above, which ignores `filters` entirely and
    so cannot distinguish a paginated call from an unpaginated one, this
    applies the real `clamp_page` and slice to get_multi, mirroring
    SqlAlchemyProductionMachineRepository.get_multi's silent
    DEFAULT_PAGE_SIZE=100 truncation. get_all() mirrors the real adapter's
    get_all: unpaginated, unaffected by clamp_page."""

    def __init__(self, machines: list[ProductionMachine]) -> None:
        self.machines = {m.id: m for m in machines}

    async def get_by_id(self, id: int) -> ProductionMachine | None:
        return self.machines.get(id)

    async def get_by_ids(self, ids: list[int]) -> list:
        found = [await self.get_by_id(i) for i in ids]
        return [item for item in found if item is not None]

    async def get_multi(self, filters) -> tuple[int, list[ProductionMachine]]:
        values = sorted(self.machines.values(), key=lambda m: m.id)
        skip, limit = clamp_page(filters.skip, filters.limit)
        return len(values), values[skip : skip + limit]

    async def get_all(self) -> list[ProductionMachine]:
        return sorted(self.machines.values(), key=lambda m: m.id)


class ClampingFakePoolRepo:
    """Pool twin of ClampingFakeMachineRepo, see its docstring."""

    def __init__(self, pools: list[MachinePool]) -> None:
        self.pools = {p.id: p for p in pools}

    async def get_by_id(self, id: int) -> MachinePool | None:
        return self.pools.get(id)

    async def get_by_ids(self, ids: list[int]) -> list:
        found = [await self.get_by_id(i) for i in ids]
        return [item for item in found if item is not None]

    async def get_multi(self, filters) -> tuple[int, list[MachinePool]]:
        values = sorted(self.pools.values(), key=lambda p: p.id)
        skip, limit = clamp_page(filters.skip, filters.limit)
        return len(values), values[skip : skip + limit]

    async def get_all(self) -> list[MachinePool]:
        return sorted(self.pools.values(), key=lambda p: p.id)


class FakeCalendarRepo:
    async def get_working_hours_by_machine_id(self, machine_id: int):
        return None

    async def get_working_hours_by_machine_ids(self, machine_ids: list[int]) -> list:
        # Additive stub for the batch port method. No machine
        # in these fixtures has a working-hours override row, mirroring
        # get_working_hours_by_machine_id's None above.
        return []

    async def get_exceptions_by_machine_id(self, machine_id: int) -> list:
        return []

    async def get_exceptions_by_machine_ids(self, machine_ids: list[int]) -> list:
        # Additive stub, see get_working_hours_by_machine_ids above.
        return []

    async def get_holidays(self) -> list:
        return []


class FakeSettingsRepo:
    """The production settings as given, and general settings that carry
    only the tenant's default timezone, which is all Auto-Plan reads of
    them."""

    def __init__(
        self, settings: AdminProductionSettings, default_timezone: str = TENANT_TIMEZONE
    ) -> None:
        self.settings = settings
        self.general = SimpleNamespace(default_timezone=default_timezone)

    async def get_production(self) -> AdminProductionSettings:
        return self.settings

    async def get_general(self) -> SimpleNamespace:
        return self.general
