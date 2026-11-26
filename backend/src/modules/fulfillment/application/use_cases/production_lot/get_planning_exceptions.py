"""
The planner's exception list: the shortfalls and delays in the order and
lot cycle that need a decision, computed on read from the stored rows, with
no table of its own. Like the exception messages of an MRP run, it names
what is wrong and leaves the remedy to the planner.

- A bought or raw material demand whose order line lost pieces at receipt
  or was closed short, and which has a rest that no allocation covers any
  more (LOST_AT_RECEIPT, CLOSED_SHORT). The lines read are the most recent
  ones up to _LINE_LIMIT.
- A made demand whose lot was force-completed within _ENDED_WINDOW below
  what the demand needs, with a rest no allocation covers (LOT_ENDED_SHORT).
- A live lot whose raw material is partly covered by neither stock nor an
  order line, or waits on an open line without a delivery date, so its
  first step cannot be planned in full (MATERIAL_SHORT).
- A live lot past its target date, or whose production orders are planned
  to end after it (LATE). Today and the day a planned end falls on are days
  of the tenant's timezone.

A demand that is fulfilled or canceled is never listed. A sourceless lot
waits for its source by design and is not listed as short of material.
"""

from collections.abc import Iterable
from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import replace
from datetime import datetime
from datetime import timedelta
from typing import Any
from typing import Literal
from typing import Protocol

from src.modules.fulfillment.application.dto.production_lot_dto import PlanningExceptionResult
from src.modules.fulfillment.application.services.scheduling_context import SchedulingRepos
from src.modules.fulfillment.application.services.scheduling_context import (
    describe_lot_target_dates,
)
from src.modules.fulfillment.domain.entities.bought_item_demand_item import BoughtItemDemandItem
from src.modules.fulfillment.domain.entities.made_item_demand_item import MadeItemDemandItem
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.source_item_demand_item import SourceItemDemandItem
from src.modules.fulfillment.domain.services.scheduling import latest_ready_moment
from src.modules.fulfillment.domain.services.scheduling import position_wait_after_minutes
from src.modules.fulfillment.domain.services.scheduling import step_waits
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.planning_exception_kind import (
    PlanningExceptionKind,
)
from src.modules.fulfillment.domain.value_objects.production_status import (
    TERMINAL_PRODUCTION_ORDER_STATUSES,
)
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemDemandItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import IOrderRepository
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    LotFilterDto,
)
from src.modules.platform.application.services.paging import fetch_all
from src.modules.platform.application.services.tenant_timezone import tenant_zone
from src.modules.platform.const import MAX_PAGE_SIZE
from src.modules.platform.domain.services.quantities import quantity_ge
from src.modules.platform.domain.services.quantities import quantity_gt
from src.shared_kernel.domain.services.clock import as_utc
from src.shared_kernel.domain.services.clock import now_utc

_K = PlanningExceptionKind

_LINE_LIMIT = 500
_ENDED_WINDOW = timedelta(days=90)

_LIVE_LOT_STATUSES: list[str] = [
    LotStatus.PARTIALLY_PLANNED,
    LotStatus.PLANNED,
    LotStatus.IN_PROGRESS,
    LotStatus.ON_HOLD,
]
_OPEN_LINE_STATUSES = frozenset(
    {
        OrderItemStatus.PENDING,
        OrderItemStatus.REQUESTED,
        OrderItemStatus.ORDERED,
        OrderItemStatus.PARTIALLY_DELIVERED,
    }
)
_FINISHED_DEMAND_STATUSES = frozenset({"fulfilled", "canceled"})
_KIND_ORDER = {kind: i for i, kind in enumerate(PlanningExceptionKind)}


class _Allocation(Protocol):
    @property
    def demand_item_id(self) -> int: ...

    @property
    def quantity(self) -> float: ...


class _LineAllocation(_Allocation, Protocol):
    @property
    def order_item_id(self) -> int | None: ...


class _Demand(Protocol):
    @property
    def status(self) -> str: ...

    @property
    def canceled_at(self) -> datetime | None: ...

    @property
    def fulfilled_manually_at(self) -> datetime | None: ...


def _live(demand: _Demand) -> bool:
    return (
        demand.canceled_at is None
        and demand.fulfilled_manually_at is None
        and demand.status not in _FINISHED_DEMAND_STATUSES
    )


@dataclass(frozen=True)
class _Subject:
    """The catalogue item and the project a row is about."""

    item_kind: Literal["made", "bought", "source"] | None = None
    item_id: int | None = None
    item_number: str = ""
    item_revision: str = ""
    item_name: str = ""
    project_id: int | None = None
    project_number: str = ""
    project_customer: str = ""

    def fields(self) -> dict[str, Any]:
        label = f"{self.item_number} {self.item_name}".strip()
        return {**asdict(self), "item_label": label}


def _bought_subject(demand: BoughtItemDemandItem) -> _Subject:
    return _Subject(
        item_kind="bought",
        item_id=demand.item_id,
        item_number=demand.item_order_code_1,
        item_name=demand.item_article_name,
        project_id=demand.project_id,
        project_number=demand.project_number,
        project_customer=demand.project_customer,
    )


def _source_subject(demand: SourceItemDemandItem) -> _Subject:
    """A raw material demand names either a raw material or a bought item."""
    subject = _Subject(
        project_id=demand.project_id,
        project_number=demand.project_number,
        project_customer=demand.project_customer,
    )
    if demand.source_item is not None:
        return replace(
            subject,
            item_kind="source",
            item_id=demand.source_item.id,
            item_number=demand.source_item.dimension or "",
            item_name=demand.source_item.material,
        )
    if demand.bought_item is not None:
        return replace(
            subject,
            item_kind="bought",
            item_id=demand.bought_item.id,
            item_number=demand.bought_item.order_code_1,
            item_name=demand.bought_item.article_name,
        )
    return subject


def _made_subject(demand: MadeItemDemandItem) -> _Subject:
    return _Subject(
        item_kind="made",
        item_id=demand.made_item_id,
        item_number=demand.item_part_number,
        item_revision=demand.item_revision,
        item_name=demand.item_article_name,
        project_id=demand.project_id,
        project_number=demand.project_number,
        project_customer=demand.project_customer,
    )


def _lot_subject(lot: ProductionLot) -> _Subject:
    return _Subject(
        item_kind="made",
        item_id=lot.made_item_id,
        item_number=lot.made_item_part_number,
        item_revision=lot.made_item_revision,
        item_name=lot.made_item_article_name,
        project_id=lot.project_id,
        project_number=lot.project_number,
        project_customer=lot.project_customer,
    )


def _allocated(allocations: Iterable[_Allocation], demand_id: int) -> float:
    return sum((a.quantity for a in allocations if a.demand_item_id == demand_id), 0.0)


class GetPlanningExceptions:
    """Lists the planning exceptions; see the module docstring."""

    def __init__(
        self,
        repos: SchedulingRepos,
        bought_demand_repo: IBoughtItemDemandItemRepository,
        bought_allocation_repo: IBoughtItemAllocationRepository,
        order_repo: IOrderRepository,
    ) -> None:
        self._repos = repos
        self._bought_demands = bought_demand_repo
        self._bought_allocations = bought_allocation_repo
        self._orders = order_repo

    async def execute(self) -> list[PlanningExceptionResult]:
        rows = await self._line_shortfalls()
        rows += await self._lots_ended_short()
        lots = await fetch_all(
            lambda skip, limit: self._repos.lots.get_multi(
                LotFilterDto(statuses=_LIVE_LOT_STATUSES, skip=skip, limit=limit)
            ),
            MAX_PAGE_SIZE,
        )
        rows += await self._material_short(lots)
        rows += await self._late(lots)
        return sorted(rows, key=_row_order)

    # ── Demands short after a line lost pieces or was closed short ───────

    async def _line_shortfalls(self) -> list[PlanningExceptionResult]:
        lines = await self._repos.order_items.get_settled_short(_LINE_LIMIT)
        if not lines:
            return []
        line_ids = [line.id for line in lines]
        lines_by_id = {line.id: line for line in lines}
        numbers = await self._order_numbers(lines)
        rows: list[PlanningExceptionResult] = []

        bought_on_lines = await self._bought_allocations.get_by_order_item_ids(line_ids)
        bought_ids = sorted({a.demand_item_id for a in bought_on_lines})
        bought_all = await self._bought_allocations.get_by_demand_item_ids(bought_ids)
        for demand in await self._bought_demands.get_by_ids(bought_ids):
            line = self._first_line(demand.id, bought_on_lines, lines_by_id)
            rest = demand.quantity - _allocated(bought_all, demand.id)
            if line is not None and _live(demand) and quantity_gt(rest, 0.0):
                rows.append(
                    self._line_row(
                        line,
                        numbers,
                        "bought",
                        demand.id,
                        _bought_subject(demand),
                        rest,
                        demand.unit,
                    )
                )

        source_on_lines = await self._repos.source_item_allocations.get_by_order_item_ids(line_ids)
        source_ids = sorted({a.demand_item_id for a in source_on_lines})
        source_all = await self._repos.source_item_allocations.get_by_demand_item_ids(source_ids)
        for source in await self._repos.source_item_demands.get_by_ids(source_ids):
            line = self._first_line(source.id, source_on_lines, lines_by_id)
            rest = source.quantity - _allocated(source_all, source.id)
            if line is not None and _live(source) and quantity_gt(rest, 0.0):
                row = self._line_row(
                    line,
                    numbers,
                    "source",
                    source.id,
                    _source_subject(source),
                    rest,
                    source.unit,
                )
                row.lot_id, row.lot_number = source.lot_id, source.lot_number or None
                rows.append(row)
        return rows

    @staticmethod
    def _first_line(
        demand_id: int, allocations: Iterable[_LineAllocation], lines_by_id: dict[int, OrderItem]
    ) -> OrderItem | None:
        for allocation in allocations:
            if allocation.demand_item_id != demand_id or allocation.order_item_id is None:
                continue
            line = lines_by_id.get(allocation.order_item_id)
            if line is not None:
                return line
        return None

    @staticmethod
    def _line_row(
        line: OrderItem,
        numbers: dict[int, str],
        family: Literal["bought", "source", "made"],
        demand_id: int,
        subject: _Subject,
        rest: float,
        unit: str,
    ) -> PlanningExceptionResult:
        lost = quantity_gt(line.quantity_rejected_lost, 0.0)
        return PlanningExceptionResult(
            kind=_K.LOST_AT_RECEIPT if lost else _K.CLOSED_SHORT,
            family=family,
            demand_id=demand_id,
            order_id=line.order_id,
            order_number=numbers.get(line.order_id),
            line_position=line.position,
            quantity_short=rest,
            unit=unit,
            since=line.closed_short_at if not lost and line.closed_short_at else line.changed,
            **subject.fields(),
        )

    async def _order_numbers(self, lines: Iterable[OrderItem]) -> dict[int, str]:
        orders = await self._orders.get_by_ids(sorted({line.order_id for line in lines}))
        return {order.id: order.order_number for order in orders}

    # ── Made demands short after their lot was force-completed ───────────

    async def _lots_ended_short(self) -> list[PlanningExceptionResult]:
        lots = await self._repos.lots.get_force_completed_since(now_utc() - _ENDED_WINDOW)
        if not lots:
            return []
        lots_by_id = {lot.id: lot for lot in lots}
        on_lots = await self._repos.made_item_allocations.get_by_lot_ids(list(lots_by_id))
        demand_ids = sorted({a.demand_item_id for a in on_lots})
        if not demand_ids:
            return []
        every = await self._repos.made_item_allocations.get_by_demand_item_ids(demand_ids)
        rows: list[PlanningExceptionResult] = []
        for demand in await self._repos.made_item_demands.get_by_ids(demand_ids):
            rest = demand.quantity - _allocated(every, demand.id)
            lot = next(
                (
                    lots_by_id[a.lot_id]
                    for a in on_lots
                    if a.demand_item_id == demand.id and a.lot_id in lots_by_id
                ),
                None,
            )
            if lot is None or not _live(demand) or not quantity_gt(rest, 0.0):
                continue
            rows.append(
                PlanningExceptionResult(
                    kind=_K.LOT_ENDED_SHORT,
                    family="made",
                    demand_id=demand.id,
                    lot_id=lot.id,
                    lot_number=lot.lot_number,
                    quantity_short=rest,
                    unit=demand.unit,
                    since=lot.force_completed_at,
                    **_made_subject(demand).fields(),
                )
            )
        return rows

    # ── Live lots short of raw material ──────────────────────────────────

    async def _material_short(self, lots: list[ProductionLot]) -> list[PlanningExceptionResult]:
        linked = {
            lot.input_demand_id: lot
            for lot in lots
            if lot.input_demand_id is not None and not _first_position_done(lot)
        }
        if not linked:
            return []
        demand_ids = sorted(linked)
        demands = await self._repos.source_item_demands.get_by_ids(demand_ids)
        allocations = await self._repos.source_item_allocations.get_by_demand_item_ids(demand_ids)
        line_ids = sorted({a.order_item_id for a in allocations if a.order_item_id is not None})
        lines = {line.id: line for line in await self._repos.order_items.get_by_ids(line_ids)}
        arrived = await self._repos.lots.get_raw_material_arrived_quantities(demand_ids)
        rows: list[PlanningExceptionResult] = []
        for demand in demands:
            if not _live(demand):
                continue
            mine = [a for a in allocations if a.demand_item_id == demand.id]
            unallocated = demand.quantity - sum(a.quantity for a in mine)
            undated = any(
                (line := lines.get(a.order_item_id)) is not None
                and line.status in _OPEN_LINE_STATUSES
                and line.expected_delivery_date is None
                for a in mine
                if a.order_item_id is not None
            )
            missing = demand.quantity - arrived.get(demand.id, 0.0)
            if not quantity_gt(missing, 0.0):
                continue
            if not quantity_gt(unallocated, 0.0) and not undated:
                continue
            lot = linked[demand.id]
            rows.append(
                PlanningExceptionResult(
                    kind=_K.MATERIAL_SHORT,
                    family="source",
                    demand_id=demand.id,
                    lot_id=lot.id,
                    lot_number=lot.lot_number,
                    quantity_short=missing,
                    unit=demand.unit,
                    unallocated=max(unallocated, 0.0),
                    undated=undated,
                    since=lot.changed,
                    **_lot_subject(lot).fields(),
                )
            )
        return rows

    # ── Live lots late against their target date ─────────────────────────

    async def _late(self, lots: list[ProductionLot]) -> list[PlanningExceptionResult]:
        if not lots:
            return []
        targets = await describe_lot_target_dates(lots, self._repos)
        position_ids = [p.id for lot in lots for p in lot.positions]
        orders = await self._repos.orders.get_by_lot_position_ids(position_ids)
        position_lot = {p.id: lot.id for lot in lots for p in lot.positions}
        wait_by_position = {
            p.id: position_wait_after_minutes(p.kind, step_waits(p.steps))
            for lot in lots
            for p in lot.positions
        }
        # A lot is finished once the pieces of its last step are ready: an
        # open order's planned end plus the wait after its position, and a
        # completed order's actual end plus that wait while it still runs.
        ends_by_lot: dict[int, list[tuple[datetime | None, int]]] = {}
        for order in orders:
            lot_id = position_lot.get(order.lot_position_id)
            if lot_id is None:
                continue
            wait = wait_by_position.get(order.lot_position_id, 0)
            if order.status not in TERMINAL_PRODUCTION_ORDER_STATUSES:
                ends_by_lot.setdefault(lot_id, []).append((order.planned_end, wait))
            elif order.status == ProductionOrderStatus.COMPLETED and wait > 0:
                ends_by_lot.setdefault(lot_id, []).append((order.actual_end, wait))
        planned_end: dict[int, datetime] = {
            lot_id: moment
            for lot_id, ends in ends_by_lot.items()
            if (moment := latest_ready_moment(ends)) is not None
        }
        zone = await tenant_zone(self._repos.settings)
        today = now_utc().astimezone(zone).date()
        rows: list[PlanningExceptionResult] = []
        for lot in lots:
            target = targets.get(lot.id, (None, None, None))[0]
            if target is None:
                continue
            end = planned_end.get(lot.id)
            past = target < today
            overrun = end is not None and as_utc(end).astimezone(zone).date() > target
            if not past and not overrun:
                continue
            rows.append(
                PlanningExceptionResult(
                    kind=_K.LATE,
                    lot_id=lot.id,
                    lot_number=lot.lot_number,
                    target_date=target,
                    planned_end=end,
                    **_lot_subject(lot).fields(),
                )
            )
        return rows


def _first_position_done(lot: ProductionLot) -> bool:
    """Whether the lot's first position used all the material it needs."""
    if not lot.positions:
        return True
    first = min(lot.positions, key=lambda p: p.sequence)
    return quantity_ge(first.quantity_completed, first.quantity)


def _row_order(row: PlanningExceptionResult) -> tuple[int, str, int]:
    """By kind, then the earliest target or the oldest cause first."""
    when = row.target_date.isoformat() if row.target_date else ""
    if not when and row.since is not None:
        when = row.since.isoformat()
    return _KIND_ORDER[row.kind], when, row.lot_id or row.demand_id or 0
