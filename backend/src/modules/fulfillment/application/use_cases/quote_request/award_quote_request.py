"""
Awards lines of a quote request to the suppliers that won them, in one
transaction that puts each line on a draft or partially ordered order of its
supplier.

The award reads the request, checks its intent and edit version, plans which
lines go to which supplier row, and checks what the order paths check before
their locks: the bought and source items, and the projects, which it locks in
shared mode. It locks the existing orders it adds to, the lots of the
MADE lines, the demands the lines are for, with their neighbours, and the
request itself, last in the lock order, in one acquisition
(docs/reference/lifecycle.md section 2.3). Read again under its lock, the
request must still allow the award, carry the same edit version and give the
same plan, or the award is refused as a concurrent change; only then are the
numbers of the new orders drawn.

Under those locks each demand share is cut to what the demand still needs,
its quantity less everything allocated to it, and a demand that is fulfilled
or canceled takes nothing; the line keeps its quoted quantity, so what the
demands no longer need is free capacity on the line. A MADE line takes the
smaller of its quantity and what the position still has to give; a position
that can no longer be assigned, because it holds a live line, its lot ended
or nothing remains, keeps its request line open with a warning. The lines
are created through the same cores as Manage Orders (CreateOrderItem and
AssignExternalPosition), each carrying the request line it came from. A
line goes on with the alternative item its winner quoted, or the item of a
line that replaced another, and the substitution reason, so the order path
records the substitution against each demand whose item differs. Each
winning supplier's order takes the extra costs the award names for it, line
costs following their line, and the request records the award per line.
The reconciler then derives every status once, the request's among them,
the events are published, and everything commits together, so a failed
award leaves nothing behind.
"""

from collections import defaultdict
from dataclasses import dataclass
from dataclasses import field
from datetime import date
from datetime import datetime
from datetime import timedelta

from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.fulfillment.application.dto.order_dto import CreateOrderCommand
from src.modules.fulfillment.application.dto.order_dto import CreateOrderItemCommand
from src.modules.fulfillment.application.dto.order_dto import OrderLineDemandAllocationInput
from src.modules.fulfillment.application.dto.production_lot_dto import AssignExternalPositionCommand
from src.modules.fulfillment.application.dto.quote_request_dto import AwardedOrderResult
from src.modules.fulfillment.application.dto.quote_request_dto import AwardQuoteRequestCommand
from src.modules.fulfillment.application.dto.quote_request_dto import AwardQuoteRequestResult
from src.modules.fulfillment.application.dto.quote_request_dto import AwardSupplierInput
from src.modules.fulfillment.application.dto.quote_request_dto import AwardWarningResult
from src.modules.fulfillment.application.dto.quote_request_dto import QuoteExtraCostInput
from src.modules.fulfillment.application.mappers.quote_request_mapper import QuoteRequestMapper
from src.modules.fulfillment.application.services.lifecycle_loader import AggregateIds
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.use_cases.order.create_order import CreateOrder
from src.modules.fulfillment.application.use_cases.order.create_order_item import CreateOrderItem
from src.modules.fulfillment.application.use_cases.order.create_order_item import LineIdentity
from src.modules.fulfillment.application.use_cases.production_lot.assign_external_position import (
    AssignExternalPosition,
)
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order_extra_cost import OrderExtraCost
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequest
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequestLine
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequestSupplier
from src.modules.fulfillment.domain.errors import OrderNotFoundError
from src.modules.fulfillment.domain.errors import QuoteRequestInvalidError
from src.modules.fulfillment.domain.errors import QuoteRequestLineNotOpenError
from src.modules.fulfillment.domain.errors import QuoteRequestNotFoundError
from src.modules.fulfillment.domain.events.lot_events import LotPositionAssigned
from src.modules.fulfillment.domain.services.extra_cost_rules import ExtraCostDraft
from src.modules.fulfillment.domain.services.extra_cost_rules import assert_valid_extra_costs
from src.modules.fulfillment.domain.services.extra_cost_rules import describe_extra_cost_change
from src.modules.fulfillment.domain.services.extra_cost_rules import normalized_label
from src.modules.fulfillment.domain.services.lot_rules import lot_position_context
from src.modules.fulfillment.domain.services.lot_rules import lot_position_refusal
from src.modules.fulfillment.domain.services.quote_request_rules import AwardedLine
from src.modules.fulfillment.domain.services.quote_request_rules import (
    allowed_quote_request_actions,
)
from src.modules.fulfillment.domain.services.quote_request_rules import (
    assert_can_write_quote_requests,
)
from src.modules.fulfillment.domain.services.quote_request_rules import assert_quote_request_action
from src.modules.fulfillment.domain.services.quote_request_rules import plan_award
from src.modules.fulfillment.domain.value_objects.extra_cost_kind import ExtraCostKind
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.quote_request_status import (
    QuoteRequestDemandFamily,
)
from src.modules.fulfillment.domain.value_objects.quote_request_status import QuoteRequestLineState
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.fulfillment.ports.outbound.fulfillment_settings_repository import (
    IFulfillmentSettingsRepository,
)
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
from src.modules.fulfillment.ports.outbound.repositories.quote_request_repository import (
    IQuoteRequestRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemDemandRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.services.schedule_recompute_port import ScheduleRecompute
from src.modules.platform.application.services.schedule_recompute_port import (
    recompute_schedule_after_commit,
)
from src.modules.platform.application.services.tenant_timezone import tenant_zone
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import ConcurrentModificationError
from src.modules.platform.domain.services.edit_version import assert_edit_version
from src.modules.platform.domain.services.edit_version import bump_edit_version
from src.modules.platform.domain.services.quantities import quantity_gt
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.domain.errors import ProjectNotFoundError
from src.modules.workspace.domain.policies.project_activity import assert_project_active
from src.modules.workspace.ports.outbound.workspace_queries import IProjectQueries
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc
from src.shared_kernel.domain.services.clock import today_in
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction

_TERMINAL_BOUGHT = (BoughtItemDemandStatus.FULFILLED, BoughtItemDemandStatus.CANCELED)
_TERMINAL_SOURCE = (SourceItemDemandStatus.FULFILLED, SourceItemDemandStatus.CANCELED)
# The orders that take a new line from anyone who may edit orders: a draft,
# and a partially ordered order, whose lines not yet with the supplier stay
# open to the buyer.
_AWARD_TARGET_STATUSES = (OrderStatus.DRAFT, OrderStatus.PARTIALLY_ORDERED)


@dataclass(frozen=True)
class AwardRepositories:
    requests: IQuoteRequestRepository
    orders: IOrderRepository
    order_items: IOrderItemRepository
    lots: IProductionLotRepository
    projects: IProjectQueries
    bought_demands: IBoughtItemDemandItemRepository
    bought_allocations: IBoughtItemAllocationRepository
    source_demands: ISourceItemDemandRepository
    source_allocations: ISourceItemAllocationRepository


@dataclass
class _Placement:
    """One awarded line as it will be placed: its plan, the identity of a
    bought, source or free-text line, the capped shares, and the quantity
    of a MADE line."""

    award: AwardedLine
    identity: LineIdentity | None = None
    bought: list[OrderLineDemandAllocationInput] = field(default_factory=list)
    source: list[OrderLineDemandAllocationInput] = field(default_factory=list)
    made_quantity: float | None = None


class AwardQuoteRequest:
    def __init__(
        self,
        repos: AwardRepositories,
        *,
        create_order: CreateOrder,
        create_order_item: CreateOrderItem,
        assign_external: AssignExternalPosition,
        event_bus: IEventBus,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
        recompute_schedule: ScheduleRecompute | None = None,
        settings_repo: IFulfillmentSettingsRepository | None = None,
    ) -> None:
        self._r = repos
        self._create_order = create_order
        self._create_line = create_order_item
        self._assign = assign_external
        self._bus = event_bus
        self._uow = uow
        self._reconciler = reconciler
        self._recompute = recompute_schedule
        # Gives the tenant's timezone, whose today a lead time counts from;
        # without it (unit tests) the day is UTC's.
        self._settings = settings_repo

    async def execute(
        self, actor: User, request_id: int, cmd: AwardQuoteRequestCommand
    ) -> AwardQuoteRequestResult:
        assert_can_write_quote_requests(actor)
        request = found_or_raise(
            await self._r.requests.get_by_id(request_id),
            QuoteRequestNotFoundError,
            f"Quote request #{request_id} not found.",
        )
        plan, inputs = self._plan(actor, request, cmd)
        targets = await self._target_orders(request, inputs)

        placements = {
            row_id: [_Placement(award=award) for award in awards] for row_id, awards in plan.items()
        }
        await self._check_before_locks(placements)
        await self._lock(request.id, placements, targets)
        await self._assert_unchanged_under_lock(actor, request, plan, inputs, cmd)
        targets = await self._targets_under_lock(targets)

        warnings: list[AwardWarningResult] = []
        for row_placements in placements.values():
            for placement in row_placements:
                await self._cap(actor, placement, warnings)

        now = now_utc()
        today = now.date()
        if self._settings is not None:
            today = today_in(await tenant_zone(self._settings))
        orders: list[AwardedOrderResult] = []
        assigned: list[LotPositionAssigned] = []
        awarded_text: list[str] = []
        for row_id, row_placements in placements.items():
            placeable = [p for p in row_placements if self._placeable(p)]
            if not placeable:
                continue
            row = next(r for r in request.suppliers if r.id == row_id)
            order, created = await self._order_for(actor, request, row, targets.get(row_id))
            line_map: dict[int, int] = {}
            for placement in placeable:
                order_line_id = await self._place(
                    actor, order, row, placement, now, today, assigned
                )
                line_map[placement.award.line.id] = order_line_id
                await self._record_award(actor, placement.award, row, now)
            await self._add_extra_costs(actor, order, inputs[row_id], line_map, created, now)
            orders.append(
                AwardedOrderResult(
                    order_id=order.id,
                    order_number=order.order_number,
                    supplier_id=row.supplier_id,
                    supplier_name=row.supplier_name,
                    created=created,
                    line_ids=list(line_map),
                )
            )
            positions = ", ".join(str(p.award.line.position) for p in placeable)
            awarded_text.append(f"lines {positions} to {row.supplier_name} ({order.order_number})")

        if not orders:
            raise QuoteRequestInvalidError(
                "None of the chosen lines can go onto an order: "
                + " ".join(w.message for w in warnings)
            )

        await self._finish_request(actor, request.id, awarded_text, now)
        await self._reconciler.run(actor, now, reason=f"award of {request.request_number}")
        refreshed = found_or_raise(
            await self._r.requests.get_by_id(request.id),
            QuoteRequestNotFoundError,
            f"Quote request #{request.id} not found.",
        )
        for event in assigned:
            await self._bus.publish(event)
        await self._uow.commit()

        if assigned or any(p.source for ps in placements.values() for p in ps):
            await recompute_schedule_after_commit(
                self._recompute,
                after=f"awarding quote request {request.request_number}; the award is committed.",
            )
        log.info(f"Awarded quote request {request.request_number}: {'; '.join(awarded_text)}.")
        return AwardQuoteRequestResult(
            request=QuoteRequestMapper.to_result(
                refreshed, allowed_quote_request_actions(refreshed, actor)
            ),
            orders=orders,
            warnings=warnings,
        )

    # ── Plan and checks before the locks ────────────────────────────────

    def _plan(
        self, actor: User, request: QuoteRequest, cmd: AwardQuoteRequestCommand
    ) -> tuple[dict[int, list[AwardedLine]], dict[int, AwardSupplierInput]]:
        """Checks the award against the request as read and plans it: the
        lines each supplier row wins and what each winner books."""
        assert_quote_request_action(LifecycleAction.AWARD, request, actor)
        assert_edit_version(
            request, cmd.expected_edit_version, what=f"Quote request {request.request_number}"
        )
        plan = plan_award(request, {a.line_id: a.supplier_row_id for a in cmd.awards})
        return plan, self._supplier_inputs(request, plan, cmd)

    async def _assert_unchanged_under_lock(
        self,
        actor: User,
        request: QuoteRequest,
        plan: dict[int, list[AwardedLine]],
        inputs: dict[int, AwardSupplierInput],
        cmd: AwardQuoteRequestCommand,
    ) -> None:
        """Reads the request again under its lock and refuses the award when
        a writer changed it since the first read: its edit version, a line,
        a supplier row or an offer the plan rests on. The locks were taken
        for the first plan, so the award goes on only with that plan."""
        locked = found_or_raise(
            await self._r.requests.get_by_id_for_update(request.id),
            QuoteRequestNotFoundError,
            f"Quote request #{request.id} not found.",
        )
        changed = ConcurrentModificationError(
            f"Quote request {request.request_number} changed while the award was prepared; "
            "reload it and award again."
        )
        if locked.edit_version != request.edit_version:
            raise changed
        try:
            locked_plan, locked_inputs = self._plan(actor, locked, cmd)
        except (QuoteRequestInvalidError, QuoteRequestLineNotOpenError) as exc:
            raise changed from exc
        if locked_plan != plan or locked_inputs != inputs:
            raise changed

    @staticmethod
    def _supplier_inputs(
        request: QuoteRequest,
        plan: dict[int, list[AwardedLine]],
        cmd: AwardQuoteRequestCommand,
    ) -> dict[int, AwardSupplierInput]:
        """What the award books per winning supplier row. A row the command
        leaves out gets a new order and its offer's extra costs in full; a
        row the command names but that wins nothing is refused."""
        given = {s.supplier_row_id: s for s in cmd.suppliers}
        stray = sorted(set(given) - set(plan))
        if stray:
            raise QuoteRequestInvalidError(
                f"Supplier entry #{stray[0]} wins no line of this award."
            )
        line_ids = {line.id for line in request.lines}
        inputs: dict[int, AwardSupplierInput] = {}
        for row_id in plan:
            row = next(r for r in request.suppliers if r.id == row_id)
            entry = given.get(row_id) or AwardSupplierInput(
                supplier_row_id=row_id,
                extra_costs=[
                    QuoteExtraCostInput(
                        kind=ExtraCostKind(c.kind),
                        amount=c.amount,
                        label=c.label,
                        note=c.note,
                        line_id=c.line_id,
                    )
                    for c in row.extra_costs
                ],
            )
            assert_valid_extra_costs(
                [
                    ExtraCostDraft(
                        kind=c.kind,
                        amount=c.amount,
                        label=normalized_label(c.label),
                        line_id=c.line_id,
                    )
                    for c in entry.extra_costs
                ],
                line_ids,
            )
            inputs[row_id] = entry
        return inputs

    async def _target_orders(
        self, request: QuoteRequest, inputs: dict[int, AwardSupplierInput]
    ) -> dict[int, Order]:
        """The existing orders the award adds to, by supplier row: an order
        of that supplier nobody canceled that still takes lines as a draft
        does, a draft or a partially ordered one."""
        targets: dict[int, Order] = {}
        for row_id, entry in inputs.items():
            if entry.target_order_id is None:
                continue
            row = next(r for r in request.suppliers if r.id == row_id)
            order = found_or_raise(
                await self._r.orders.get_by_id(entry.target_order_id),
                OrderNotFoundError,
                f"Order #{entry.target_order_id} not found.",
            )
            if order.supplier_id != row.supplier_id:
                raise QuoteRequestInvalidError(
                    f"Order {order.order_number} is for another supplier than {row.supplier_name}."
                )
            if order.status not in _AWARD_TARGET_STATUSES or order.canceled_at is not None:
                raise QuoteRequestInvalidError(
                    f"Order {order.order_number} is {order.status.value}; an award adds to a draft "
                    "or partially ordered order only."
                )
            targets[row_id] = order
        return targets

    async def _targets_under_lock(self, targets: dict[int, Order]) -> dict[int, Order]:
        """The target orders read again under their locks. One submitted or
        canceled since the first read no longer takes an award's lines, so
        the award is refused rather than putting a pending line on an
        ordered order."""
        # refresh, since the first read sits in the session's identity map.
        read = {
            o.id: o
            for o in await self._r.orders.get_by_ids(
                [order.id for order in targets.values()], refresh=True
            )
        }
        fresh: dict[int, Order] = {}
        for row_id, order in targets.items():
            locked = read.get(order.id)
            if (
                locked is None
                or locked.status not in _AWARD_TARGET_STATUSES
                or locked.canceled_at is not None
            ):
                raise ConcurrentModificationError(
                    f"Order {order.order_number} changed while the award was prepared; "
                    "reload the request and award again."
                )
            fresh[row_id] = locked
        return fresh

    async def _check_before_locks(self, placements: dict[int, list[_Placement]]) -> None:
        """The items the order paths check before their locks, and the
        projects, locked in shared mode as every writer of new work for a
        project takes them."""
        projects: set[int] = set()
        for row_placements in placements.values():
            for placement in row_placements:
                line = placement.award.line
                if line.project_id is not None:
                    projects.add(line.project_id)
                if line.line_type != OrderLineType.MADE:
                    placement.identity = await self._create_line.check_item(
                        bought_item_id=placement.award.bought_item_id,
                        source_item_id=placement.award.source_item_id,
                        virtual_name=line.virtual_name,
                    )
        await self._r.projects.lock_for_share(sorted(projects))
        for project_id in sorted(projects):
            assert_project_active(
                found_or_raise(
                    await self._r.projects.get_by_id(project_id),
                    ProjectNotFoundError,
                    f"Project #{project_id} not found.",
                ),
                work="new order lines",
            )

    async def _lock(
        self, request_id: int, placements: dict[int, list[_Placement]], targets: dict[int, Order]
    ) -> None:
        lots: set[int] = set()
        positions: set[int] = set()
        bought: set[int] = set()
        source: set[int] = set()
        for row_placements in placements.values():
            for placement in row_placements:
                line = placement.award.line
                if line.lot_id is not None:
                    lots.add(line.lot_id)
                if line.lot_position_id is not None:
                    positions.add(line.lot_position_id)
                for share in line.demands:
                    if share.family == QuoteRequestDemandFamily.BOUGHT:
                        bought.add(share.demand_item_id)
                    else:
                        source.add(share.demand_item_id)
        self._reconciler.touch_orders([order.id for order in targets.values()])
        # A MADE placement assigns its position, so the run derives the lot
        # and the made demands on it. They sort before the source demands a
        # share line locks here, so they are locked now or not at all.
        self._reconciler.touch_positions(positions)
        # The request comes last in the lock order; the run derives its
        # status from the awards recorded under these locks.
        self._reconciler.touch_quote_requests([request_id])
        await self._reconciler.lock_touched(
            also=AggregateIds.of(
                {
                    LifecycleAggregate.LOTS: lots,
                    LifecycleAggregate.BOUGHT_DEMANDS: bought,
                    LifecycleAggregate.SOURCE_DEMANDS: source,
                }
            )
        )

    # ── Under the locks ─────────────────────────────────────────────────

    async def _cap(
        self, actor: User, placement: _Placement, warnings: list[AwardWarningResult]
    ) -> None:
        line = placement.award.line
        if line.line_type == OrderLineType.MADE:
            await self._cap_made(actor, placement, warnings)
            return
        for share in line.demands:
            bought = share.family == QuoteRequestDemandFamily.BOUGHT
            open_quantity = await self._still_needed(bought, share.demand_item_id)
            take = min(share.quantity, open_quantity)
            if quantity_gt(share.quantity, take):
                warnings.append(
                    AwardWarningResult(
                        line_id=line.id,
                        kind="share_capped",
                        message=(
                            f"Line {line.position}: demand #{share.demand_item_id} still needed "
                            f"{take:g} of the {share.quantity:g} asked for, so it takes {take:g}."
                        ),
                    )
                )
            if not quantity_gt(take, 0.0):
                continue
            target = placement.bought if bought else placement.source
            target.append(
                OrderLineDemandAllocationInput(demand_item_id=share.demand_item_id, quantity=take)
            )

    async def _still_needed(self, bought: bool, demand_item_id: int) -> float:
        """What a demand still needs under its lock: its quantity less every
        allocation to it, stock included; nothing for a fulfilled, canceled
        or deleted demand."""
        if bought:
            demand = await self._r.bought_demands.get_by_id_for_update(demand_item_id)
            if demand is None or demand.status in _TERMINAL_BOUGHT:
                return 0.0
            allocated = await self._r.bought_allocations.get_allocated_quantity(demand.id)
            return max(demand.quantity - allocated, 0.0)
        source = await self._r.source_demands.get_by_id_for_update(demand_item_id)
        if source is None or source.status in _TERMINAL_SOURCE:
            return 0.0
        allocated = await self._r.source_allocations.get_allocated_quantity(source.id)
        return max(source.quantity - allocated, 0.0)

    async def _cap_made(
        self, actor: User, placement: _Placement, warnings: list[AwardWarningResult]
    ) -> None:
        line = placement.award.line
        lot = (
            await self._r.lots.get_by_id_for_update(line.lot_id)
            if line.lot_id is not None
            else None
        )
        position = (
            next((p for p in lot.positions if p.id == line.lot_position_id), None)
            if lot is not None
            else None
        )
        if lot is None or position is None:
            warnings.append(self._skipped(line, "its lot position no longer exists"))
            return
        linked = await self._r.order_items.get_by_lot_position_id(position.id)
        live = linked if linked is not None and linked.canceled_at is None else None
        context = lot_position_context(position, lot.status, live)
        refusal = lot_position_refusal(LifecycleAction.ASSIGN_EXTERNAL, position, context, actor)
        if refusal is not None:
            warnings.append(
                self._skipped(line, f"its lot position cannot be ordered ({refusal.value})")
            )
            return
        quantity = min(line.quantity, context.remaining)
        if not quantity_gt(quantity, 0.0):
            warnings.append(self._skipped(line, "its lot position has nothing left to order"))
            return
        if quantity_gt(line.quantity, quantity):
            warnings.append(
                AwardWarningResult(
                    line_id=line.id,
                    kind="share_capped",
                    message=(
                        f"Line {line.position}: the lot position has {quantity:g} of the "
                        f"{line.quantity:g} asked for left, so the order line takes {quantity:g}."
                    ),
                )
            )
        placement.made_quantity = quantity

    @staticmethod
    def _skipped(line: QuoteRequestLine, why: str) -> AwardWarningResult:
        return AwardWarningResult(
            line_id=line.id,
            kind="line_skipped",
            message=f"Line {line.position} stays open: {why}.",
        )

    @staticmethod
    def _placeable(placement: _Placement) -> bool:
        if placement.award.line.line_type == OrderLineType.MADE:
            return placement.made_quantity is not None
        return placement.identity is not None

    async def _order_for(
        self, actor: User, request: QuoteRequest, row: QuoteRequestSupplier, target: Order | None
    ) -> tuple[Order, bool]:
        if target is not None:
            return target, False
        order = await self._create_order.add(
            actor,
            CreateOrderCommand(supplier_id=row.supplier_id),
        )
        # Inserted here, so no other transaction holds it and it needs no lock.
        self._reconciler.touch_orders([order.id], created=True)
        return order, True

    async def _place(
        self,
        actor: User,
        order: Order,
        row: QuoteRequestSupplier,
        placement: _Placement,
        now: datetime,
        today: date,
        assigned: list[LotPositionAssigned],
    ) -> int:
        """Puts the line on the order and returns the new order line's id.
        A lead time counts from `today`, the tenant's day."""
        award = placement.award
        line = award.line
        delivery = (
            today + timedelta(days=award.lead_time_days)
            if award.lead_time_days is not None
            else None
        )
        if line.line_type == OrderLineType.MADE:
            if line.lot_id is None or line.lot_position_id is None or line.project_id is None:
                raise QuoteRequestInvalidError(f"Line #{line.id} names no lot position.")
            saved, _position = await self._assign.assign_under_lock(
                actor,
                line.lot_id,
                line.lot_position_id,
                AssignExternalPositionCommand(
                    order_id=order.id,
                    unit=line.unit,
                    price=award.unit_price,
                    expected_delivery_date=delivery,
                    quantity=placement.made_quantity,
                ),
                now,
                quote_request_line_id=line.id,
            )
            assigned.append(
                LotPositionAssigned(
                    lot_id=line.lot_id,
                    position_id=line.lot_position_id,
                    order_id=order.id,
                    order_item_id=saved.id,
                    actor_id=actor.id,
                )
            )
            return saved.id
        if placement.identity is None or line.project_id is None:
            raise QuoteRequestInvalidError(f"Line #{line.id} cannot go onto an order.")
        saved_line = await self._create_line.add_under_lock(
            actor,
            CreateOrderItemCommand(
                order_id=order.id,
                supplier_id=row.supplier_id,
                project_id=line.project_id,
                bought_item_id=award.bought_item_id,
                source_item_id=award.source_item_id,
                virtual_name=line.virtual_name,
                quantity=line.quantity,
                unit=line.unit,
                price=award.unit_price,
                note=line.note,
                expected_delivery_date=delivery,
                bought_demand_allocations=placement.bought,
                source_demand_allocations=placement.source,
                substitute_reason=award.substitute_reason,
            ),
            placement.identity,
            now,
            quote_request_line_id=line.id,
        )
        return saved_line.id

    async def _record_award(
        self, actor: User, award: AwardedLine, row: QuoteRequestSupplier, now: datetime
    ) -> None:
        line = award.line
        line.awarded_supplier_id = row.id
        line.awarded_price = award.unit_price
        line.awarded_at = now
        line.awarded_by_id = actor.id
        await self._r.requests.save_line(line)

    async def _add_extra_costs(
        self,
        actor: User,
        order: Order,
        entry: AwardSupplierInput,
        line_map: dict[int, int],
        created: bool,
        now: datetime,
    ) -> None:
        """Adds the extra costs the award names for the supplier to its
        order, after any it has. A cost of a request line that went onto the
        order names the order line; one of a line the supplier did not win
        is left out."""
        added = [c for c in entry.extra_costs if c.line_id is None or c.line_id in line_map]
        if not added:
            return
        fresh = found_or_raise(
            await self._r.orders.get_by_id(order.id),
            OrderNotFoundError,
            f"Order #{order.id} not found.",
        )
        existing = list(fresh.extra_costs)
        costs = [
            OrderExtraCost(
                id=0,
                order_id=fresh.id,
                kind=c.kind,
                amount=c.amount,
                position=c.position,
                label=c.label,
                note=c.note,
                order_item_id=c.order_item_id,
            )
            for c in existing
        ]
        for c in added:
            costs.append(
                OrderExtraCost(
                    id=0,
                    order_id=fresh.id,
                    kind=c.kind,
                    amount=c.amount,
                    position=len(costs) + 1,
                    label=normalized_label(c.label),
                    note=(c.note or "").strip() or None,
                    order_item_id=line_map.get(c.line_id) if c.line_id is not None else None,
                )
            )
        if not created:
            change = describe_extra_cost_change(
                [(c.kind, c.amount, c.label, c.note, c.order_item_id) for c in existing],
                [(c.kind, c.amount, c.label, c.note, c.order_item_id) for c in costs],
            )
            if change is not None:
                bump_edit_version(fresh)
                fresh.changed = now
                fresh.changes = append_changelog(fresh.changes, actor.full_name, change)
                await self._r.orders.save(fresh)
        await self._r.orders.set_extra_costs(fresh.id, costs)

    async def _finish_request(
        self, actor: User, request_id: int, awarded: list[str], now: datetime
    ) -> None:
        """Notes the award in the request's changelog and moves its edit
        version; the reconciler derives its status."""
        request = found_or_raise(
            await self._r.requests.get_by_id(request_id),
            QuoteRequestNotFoundError,
            f"Quote request #{request_id} not found.",
        )
        text = "Awarded " + "; ".join(awarded) + "."
        request.changes = append_changelog(request.changes, actor.full_name, text)
        request.changed = now
        bump_edit_version(request)
        await self._r.requests.save(request)


def awarded_orders(request: QuoteRequest) -> list[AwardedOrderResult]:
    """The orders the request's awarded lines went onto, as an award answers
    them, for a replay of an award."""
    by_order: dict[int, list[QuoteRequestLine]] = defaultdict(list)
    for line in request.lines:
        if line.order_id is not None and line.state is QuoteRequestLineState.AWARDED:
            by_order[line.order_id].append(line)
    rows = {row.id: row for row in request.suppliers}
    results = []
    for order_id, lines in by_order.items():
        row = rows.get(lines[0].awarded_supplier_id or 0)
        results.append(
            AwardedOrderResult(
                order_id=order_id,
                order_number=lines[0].order_number,
                supplier_id=row.supplier_id if row else 0,
                supplier_name=row.supplier_name if row else "",
                created=False,
                line_ids=[line.id for line in lines],
            )
        )
    return results
