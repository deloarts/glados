"""The orders the walk after an Auto-Plan run re-dated without the run
placing them, so the planner sees what else moved and why.

An order counts as re-dated when the tenant day of its planned start or of
its planned end changed. A move within the same day, such as the "never
before now" floor or a small overrun, is only counted, since it would
drown the list in minutes. The reason comes from the walk's placement
(scheduling.PlacementReason), its references resolved here: the order ahead
on the queue, the earlier position with its latest order and the method of
its last step, and the order line of an external step.
"""

from collections.abc import Iterable
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import tzinfo

from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.application.dto.production_schedule_dto import BoardColumn
from src.modules.fulfillment.application.dto.production_schedule_dto import RedatedOrder
from src.modules.fulfillment.application.dto.production_schedule_dto import RedatedOrderReason
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.services.production_order_rules import position_is_manual
from src.modules.fulfillment.domain.services.scheduling import ScheduleWalkResult
from src.modules.fulfillment.domain.services.scheduling.placement_reason import PlacementReason
from src.shared_kernel.domain.services.clock import as_utc

Window = tuple[datetime | None, datetime | None]


def window_of(order: ProductionOrder) -> Window:
    return order.planned_start, order.planned_end


def _day(moment: datetime | None, zone: tzinfo) -> date | None:
    return as_utc(moment).astimezone(zone).date() if moment is not None else None


def moved_day(before: Window | None, after: Window, zone: tzinfo) -> bool:
    """Whether the tenant day of the start or of the end changed. An order
    without a window before counts as moved once it has one."""
    if before is None:
        return after != (None, None)
    return any(_day(b, zone) != _day(a, zone) for b, a in zip(before, after, strict=True))


def _column(order: ProductionOrder, position: LotPosition | None) -> BoardColumn:
    """The board column of the order, as the queue board groups it."""
    if order.machine_id is not None:
        return "machine"
    if order.machine_pool_id is not None:
        return "pool"
    steps = position.steps if position is not None else []
    if steps and any(step.role == StepRole.INSPECTION for step in steps):
        return "inspection"
    if steps and position_is_manual(steps):
        return "manual"
    return "unassigned"


def _last_method_name(position: LotPosition) -> dict[str, str]:
    """The name of the method of the position's last step, whose wait the
    position takes."""
    if not position.steps:
        return {}
    last = max(position.steps, key=lambda step: step.sequence)
    name = (
        last.inspection_method_name
        if last.role == StepRole.INSPECTION and last.inspection_method_name is not None
        else last.fabrication_method_name
    )
    return name.as_dict()


def _resolve(
    reason: PlacementReason,
    orders_by_id: dict[int, ProductionOrder],
    orders_by_position: dict[int, list[ProductionOrder]],
    positions_by_id: dict[int, LotPosition],
    reasons: dict[int, PlacementReason | None],
) -> RedatedOrderReason:
    previous = orders_by_id.get(reason.previous_order_id) if reason.previous_order_id else None
    previous_reason = reasons.get(reason.previous_order_id) if reason.previous_order_id else None
    running = previous_reason is not None and previous_reason.kind == "in_progress"
    position = positions_by_id.get(reason.position_id) if reason.position_id else None
    position_orders = orders_by_position.get(reason.position_id, []) if reason.position_id else []
    latest = max(
        (o for o in position_orders if o.planned_end is not None),
        key=lambda o: as_utc(o.planned_end),  # type: ignore[arg-type]
        default=None,
    )
    return RedatedOrderReason(
        kind=reason.kind,
        day=reason.day,
        moment=reason.moment,
        previous_order_id=reason.previous_order_id,
        previous_order_number=previous.production_order_number if previous else None,
        previous_running=running,
        previous_overrun=bool(running and previous_reason and previous_reason.overrun),
        previous_pieces_processed=previous_reason.pieces_processed
        if running and previous_reason
        else None,
        previous_quantity=previous_reason.quantity if running and previous_reason else None,
        predecessor_sequence=position.sequence if position else None,
        predecessor_order_number=latest.production_order_number if latest else None,
        method_name=_last_method_name(position) if position and reason.wait_after_minutes else {},
        wait_after_minutes=reason.wait_after_minutes,
        order_item_id=reason.order_item_id,
        expected_date=reason.expected_date,
        late=reason.late,
        response_time_days=reason.response_time_days,
        pieces_processed=reason.pieces_processed,
        quantity=reason.quantity,
        overrun=reason.overrun,
    )


def redated_orders(
    before: dict[int, Window],
    after_orders: Iterable[ProductionOrder],
    placed_ids: set[int],
    walk: ScheduleWalkResult,
    lots: Iterable[ProductionLot],
    zone: tzinfo,
) -> tuple[list[RedatedOrder], int]:
    """The open orders the walk moved to another day, the run's own
    placements left out, ordered by their new start with the undated last,
    and how many other open orders kept their day."""
    after = list(after_orders)
    orders_by_id = {o.id: o for o in after}
    orders_by_position: dict[int, list[ProductionOrder]] = {}
    for order in after:
        orders_by_position.setdefault(order.lot_position_id, []).append(order)
    positions_by_id = {p.id: p for lot in lots for p in lot.positions}
    reasons = {s.order_id: s.reason for s in walk.all_orders()}

    rows: list[RedatedOrder] = []
    kept = 0
    for order in after:
        if order.id in placed_ids:
            continue
        if not moved_day(before.get(order.id), window_of(order), zone):
            kept += 1
            continue
        start, end = before.get(order.id, (None, None))
        reason = reasons.get(order.id)
        rows.append(
            RedatedOrder(
                order_id=order.id,
                production_order_number=order.production_order_number,
                lot_id=order.lot_id or None,
                lot_number=order.lot_number,
                made_item_part_number=order.made_item_part_number,
                made_item_revision=order.made_item_revision,
                column=_column(order, positions_by_id.get(order.lot_position_id)),
                machine_id=order.machine_id,
                machine_pool_id=order.machine_pool_id,
                before_planned_start=start,
                before_planned_end=end,
                after_planned_start=order.planned_start,
                after_planned_end=order.planned_end,
                reason=(
                    _resolve(reason, orders_by_id, orders_by_position, positions_by_id, reasons)
                    if reason is not None
                    else None
                ),
            )
        )
    rows.sort(
        key=lambda r: (
            r.after_planned_start is None,
            as_utc(r.after_planned_start)
            if r.after_planned_start
            else datetime.min.replace(tzinfo=UTC),
            r.order_id,
        )
    )
    return rows, kept
