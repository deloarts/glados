"""Fills the `actions` of lifecycle results: the user actions the reading
user may take on an order, an order item, a lot, a lot position, a production
order or a demand right now. A project's actions are filled by
project_actions.py.

Every value comes from `IntentTable.allowed_actions` of the aggregate's
intent table (src/modules/fulfillment/domain/services/lifecycle/intents.py), the table whose
`check` the use cases run before they act, so a client that offers exactly
these actions offers nothing the backend refuses on state grounds. Orders,
order items and lots also carry `blocked_actions` from
`IntentTable.blocked_actions`: the actions their state allows but the
reader lacks the extra permission for, such as manage:lots, which the
client shows disabled and names. The base permission of each action, such
as write:orders, stays with the client's own permission check, as it does
with the use cases.

The service runs after a use case, on its results, for reads and mutation
responses alike, and reads only what a result does not carry: the lot status
of MADE order lines, the order of a single order item, the lot of a
position, whether a demand holds allocations, and the scheduling context of
production orders that no read path computed.
"""

from collections.abc import Iterable
from collections.abc import Sequence
from dataclasses import dataclass

from src.modules.fulfillment.application.dto.bought_item_demand_dto import DemandItemResult
from src.modules.fulfillment.application.dto.made_item_demand_dto import MadeItemDemandItemResult
from src.modules.fulfillment.application.dto.order_dto import OrderItemResult
from src.modules.fulfillment.application.dto.order_dto import OrderResult
from src.modules.fulfillment.application.dto.production_lot_dto import LotPositionResult
from src.modules.fulfillment.application.dto.production_lot_dto import LotResult
from src.modules.fulfillment.application.dto.production_lot_dto import LotSummaryResult
from src.modules.fulfillment.application.dto.production_order_dto import ProductionOrderResult
from src.modules.fulfillment.application.dto.source_item_demand_dto import SourceItemDemandResult
from src.modules.fulfillment.application.services.scheduling_context import SchedulingRepos
from src.modules.fulfillment.application.services.scheduling_context import (
    compute_conflicts_for_orders,
)
from src.modules.fulfillment.domain.services.lifecycle.intents import DEMAND_INTENTS
from src.modules.fulfillment.domain.services.lifecycle.intents import LOT_INTENTS
from src.modules.fulfillment.domain.services.lifecycle.intents import LOT_POSITION_INTENTS
from src.modules.fulfillment.domain.services.lifecycle.intents import ORDER_INTENTS
from src.modules.fulfillment.domain.services.lifecycle.intents import ORDER_ITEM_INTENTS
from src.modules.fulfillment.domain.services.lifecycle.intents import DemandContext
from src.modules.fulfillment.domain.services.lifecycle.intents import LotContext
from src.modules.fulfillment.domain.services.lifecycle.intents import LotPositionContext
from src.modules.fulfillment.domain.services.lifecycle.lot import lot_has_started
from src.modules.fulfillment.domain.services.lot_rules import parse_live_line_status
from src.modules.fulfillment.domain.services.order_rules import order_item_context
from src.modules.fulfillment.domain.value_objects.lot_status import TERMINAL_LOT_STATUSES
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.machine_pool_repository import (
    IMachinePoolRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    IMadeItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import IOrderRepository
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_machine_repository import (
    IProductionMachineRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    IProductionOrderRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemAllocationRepository,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.intent_table import HasStatus
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction

# The position statuses that hold completed good pieces, which keep a lot
# from being canceled.
_WORKED_POSITION_STATUSES = frozenset(
    {LotPositionStatus.PARTIALLY_COMPLETED, LotPositionStatus.COMPLETED}
)


def _values(actions: Iterable[LifecycleAction]) -> list[str]:
    return [action.value for action in actions]


def _blocked(blocked: dict[LifecycleAction, str]) -> dict[str, str]:
    return {action.value: permission for action, permission in blocked.items()}


@dataclass(frozen=True)
class _PositionView:
    """A lot position as the lot position intent table reads it, for results
    that carry its kind and status under other names."""

    kind: str
    status: str


def position_actions(
    kind: str,
    status: str,
    live_line_status: str | None,
    remaining: float,
    lot_status: str,
    actor: User,
    *,
    live_line_closed_short: bool = False,
) -> list[str]:
    """The actions of a lot position, from its kind and status, its newest
    live line's status ("" or None without one) and whether that line was
    closed short, its remaining quantity and its lot's status."""
    context = LotPositionContext(
        live_line_status=parse_live_line_status(live_line_status),
        live_line_closed_short=live_line_closed_short,
        remaining=remaining,
        lot_terminal=lot_status in TERMINAL_LOT_STATUSES,
    )
    return _values(
        LOT_POSITION_INTENTS.allowed_actions(_PositionView(kind, status), context, actor)
    )


def fill_order_item(
    item: OrderItemResult, order: HasStatus, lot_status: str | None, actor: User
) -> None:
    """Fills the allowed and the blocked actions of an order line on `order`;
    `lot_status` is the status of a MADE line's lot and None for every other
    line."""
    context = order_item_context(order, lot_status)
    item.actions = _values(ORDER_ITEM_INTENTS.allowed_actions(item, context, actor))
    item.blocked_actions = _blocked(ORDER_ITEM_INTENTS.blocked_actions(item, context, actor))


class LifecycleActions:
    """Fills `actions` on results for one actor. Each repository is needed
    only by the methods that read it."""

    def __init__(
        self,
        *,
        order_repo: IOrderRepository | None = None,
        lot_repo: IProductionLotRepository | None = None,
        production_order_repo: IProductionOrderRepository | None = None,
        scheduling: SchedulingRepos | None = None,
        machine_repo: IProductionMachineRepository | None = None,
        pool_repo: IMachinePoolRepository | None = None,
        bought_allocations: IBoughtItemAllocationRepository | None = None,
        made_allocations: IMadeItemAllocationRepository | None = None,
        source_allocations: ISourceItemAllocationRepository | None = None,
    ) -> None:
        self._orders = order_repo
        self._lots = lot_repo
        self._production_orders = production_order_repo
        self._scheduling = scheduling
        self._machines = machine_repo
        self._pools = pool_repo
        self._bought_allocations = bought_allocations
        self._made_allocations = made_allocations
        self._source_allocations = source_allocations

    # ── Orders and order items ─────────────────────────────────────────

    async def orders(self, results: Sequence[OrderResult], actor: User) -> None:
        """Each order's actions and those of the lines it carries."""
        lot_statuses = await self._lot_statuses(
            item.lot_id
            for order in results
            for item in order.items
            if item.line_type == OrderLineType.MADE
        )
        for order in results:
            order.actions = _values(ORDER_INTENTS.allowed_actions(order, None, actor))
            order.blocked_actions = _blocked(ORDER_INTENTS.blocked_actions(order, None, actor))
            for item in order.items:
                fill_order_item(item, order, self._lot_status_of(item, lot_statuses), actor)

    async def order_items(self, results: Sequence[OrderItemResult], actor: User) -> None:
        """The actions of lines returned without their order, which is read
        here."""
        if not results:
            return
        if self._orders is None:
            raise RuntimeError("LifecycleActions.order_items needs an order repository.")
        orders = {
            o.id: o for o in await self._orders.get_by_ids(sorted({i.order_id for i in results}))
        }
        lot_statuses = await self._lot_statuses(
            i.lot_id for i in results if i.line_type == OrderLineType.MADE
        )
        for item in results:
            order = orders.get(item.order_id)
            if order is None:
                item.actions = []
                item.blocked_actions = {}
                continue
            fill_order_item(item, order, self._lot_status_of(item, lot_statuses), actor)

    @staticmethod
    def _lot_status_of(item: OrderItemResult, lot_statuses: dict[int, str]) -> str | None:
        if item.line_type != OrderLineType.MADE or item.lot_id is None:
            return None
        return lot_statuses.get(item.lot_id)

    # ── Lots, positions and production orders ──────────────────────────

    async def lots(
        self, results: Sequence[LotResult], actor: User, *, production_orders: bool = False
    ) -> None:
        """Each lot's actions and those of its positions. With
        `production_orders`, the production orders of the positions are
        filled too, for results no read path computed them on."""
        for lot in results:
            context = LotContext(
                produced=lot.quantity_completed,
                has_good_pieces=any(p.quantity_completed > 0 for p in lot.positions),
                source_approval_status=lot.source_approval_status,
            )
            lot.actions = _values(LOT_INTENTS.allowed_actions(lot, context, actor))
            lot.blocked_actions = _blocked(LOT_INTENTS.blocked_actions(lot, context, actor))
            for position in lot.positions:
                position.actions = self._position_result_actions(position, lot.status, actor)
        if production_orders:
            await self.production_orders(
                [o for lot in results for p in lot.positions for o in p.production_orders], actor
            )

    async def lot_summaries(self, results: Sequence[LotSummaryResult], actor: User) -> None:
        """Each listed lot's actions and those of its positions, which the
        list carries on every step of the position."""
        for lot in results:
            context = LotContext(
                produced=lot.quantity_completed,
                has_good_pieces=any(
                    step.position_status in _WORKED_POSITION_STATUSES for step in lot.steps
                ),
                source_approval_status=lot.source_approval_status,
            )
            lot.actions = _values(LOT_INTENTS.allowed_actions(lot, context, actor))
            lot.blocked_actions = _blocked(LOT_INTENTS.blocked_actions(lot, context, actor))
            live_lines = {p.id: p for p in lot.positions}
            for step in lot.steps:
                line = live_lines.get(step.position_id)
                step.actions = position_actions(
                    step.position_kind,
                    step.position_status,
                    line.order_item_status if line is not None else None,
                    step.position_quantity_remaining,
                    lot.status,
                    actor,
                    live_line_closed_short=line is not None and line.order_item_closed_short,
                )

    async def positions(self, results: Sequence[LotPositionResult], actor: User) -> None:
        """The actions of positions returned without their lot, which is read
        here, and of their production orders."""
        if not results:
            return
        statuses = await self._lot_statuses(p.lot_id for p in results)
        for position in results:
            lot_status = statuses.get(position.lot_id)
            position.actions = (
                self._position_result_actions(position, lot_status, actor)
                if lot_status is not None
                else []
            )
        await self.production_orders([o for p in results for o in p.production_orders], actor)

    @staticmethod
    def _position_result_actions(
        position: LotPositionResult, lot_status: str, actor: User
    ) -> list[str]:
        return position_actions(
            position.kind,
            position.status,
            position.order_item_status,
            position.quantity_remaining,
            lot_status,
            actor,
            live_line_closed_short=position.order_item_closed_short,
        )

    async def production_orders(
        self, results: Sequence[ProductionOrderResult], actor: User
    ) -> None:
        """The actions and can_start of production orders, from the same
        scheduling context the read paths compute."""
        if not results:
            return
        if self._production_orders is None or self._scheduling is None or self._machines is None:
            raise RuntimeError(
                "LifecycleActions.production_orders needs the production order, scheduling "
                "and machine repositories."
            )
        orders = await self._production_orders.get_by_ids(sorted({r.id for r in results}))
        await compute_conflicts_for_orders(
            orders, self._scheduling, self._machines, pool_repo=self._pools, actor=actor
        )
        by_id = {o.id: o for o in orders}
        for result in results:
            order = by_id.get(result.id)
            if order is None:
                result.actions = []
                continue
            result.actions = list(order.actions)
            result.can_start = order.can_start

    async def _lot_statuses(self, lot_ids: Iterable[int | None]) -> dict[int, str]:
        ids = sorted({i for i in lot_ids if i is not None})
        if not ids:
            return {}
        if self._lots is None:
            raise RuntimeError("LifecycleActions needs a lot repository to read lot statuses.")
        return {lot.id: lot.status for lot in await self._lots.get_by_ids(ids)}

    # ── Demands ────────────────────────────────────────────────────────

    async def bought_demands(self, results: Sequence[DemandItemResult], actor: User) -> None:
        if not results:
            return
        if self._bought_allocations is None:
            raise RuntimeError("LifecycleActions.bought_demands needs the allocation repository.")
        allocations = await self._bought_allocations.get_by_demand_item_ids([r.id for r in results])
        _fill_demands(results, {a.demand_item_id for a in allocations}, actor)

    async def made_demands(self, results: Sequence[MadeItemDemandItemResult], actor: User) -> None:
        if not results:
            return
        if self._made_allocations is None:
            raise RuntimeError("LifecycleActions.made_demands needs the allocation repository.")
        allocations = await self._made_allocations.get_by_demand_item_ids([r.id for r in results])
        _fill_demands(results, {a.demand_item_id for a in allocations}, actor)

    async def source_demands(self, results: Sequence[SourceItemDemandResult], actor: User) -> None:
        if not results:
            return
        if self._source_allocations is None:
            raise RuntimeError("LifecycleActions.source_demands needs the allocation repository.")
        allocations = await self._source_allocations.get_by_demand_item_ids([r.id for r in results])
        if self._lots is None:
            raise RuntimeError("LifecycleActions.source_demands needs a lot repository.")
        lots = await self._lots.get_by_ids(sorted({r.lot_id for r in results}))
        started = {lot.id for lot in lots if lot_has_started([p.status for p in lot.positions])}
        by_lot = {r.id for r in results if r.lot_id in started}
        _fill_demands(results, {a.demand_item_id for a in allocations}, actor, lot_started=by_lot)


def _fill_demands(
    results: Sequence[DemandItemResult | MadeItemDemandItemResult | SourceItemDemandResult],
    with_allocations: set[int],
    actor: User,
    *,
    lot_started: set[int] | None = None,
) -> None:
    """`lot_started` names the raw material demands whose lot has started
    production."""
    for demand in results:
        context = DemandContext(
            has_allocations=demand.id in with_allocations,
            lot_started=demand.id in (lot_started or set()),
        )
        demand.actions = _values(DEMAND_INTENTS.allowed_actions(demand, context, actor))
