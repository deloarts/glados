"""Why the forward walk placed an order where it did, for the planner.

The walk places a queued order at the latest of the cursor its queue left,
the start of its earliest start day, the moment its in-house predecessors'
pieces are ready and now, snapped into working time. The reason names the
one of these that set the start, with the facts a planner needs to follow
it: the order ahead on the queue, the predecessor and its wait after, the
order line of an external step and whether it is late, or the raw material.
A running, pinned or frozen order and an undated one get a reason of their
own. The walk attaches the reason to every placement, so it always agrees
with the dates.
"""

from dataclasses import dataclass
from datetime import date
from datetime import datetime
from datetime import timedelta
from typing import Literal

from src.modules.fulfillment.domain.services.scheduling._shared import as_day
from src.modules.fulfillment.domain.services.scheduling._shared import day_start
from src.modules.fulfillment.domain.services.scheduling.walk_context import OrderSchedulingContext
from src.modules.fulfillment.domain.services.scheduling.walk_context import PredecessorPosition
from src.modules.fulfillment.domain.services.scheduling.walk_context import buffered_ready_day
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.shared_kernel.domain.services.clock import as_utc

PlacementReasonKind = Literal[
    # Nothing holds the order back beyond now.
    "ready_now",
    # The order ahead of it on its queue, `previous_order_id`, ends then.
    "queue",
    # The in-house predecessor `position_id` ends then, plus its wait.
    "predecessor",
    # The external predecessor `position_id` arrives on order line
    # `order_item_id`; `late` when its expected day has passed, `arrived`
    # once it did, and `forecast` when no supplier date exists yet.
    "order_line",
    "raw_material",
    "not_before",
    # A running order, `pieces_processed` of `quantity` done; `overrun`
    # when its progress stretched the end past the estimate.
    "in_progress",
    "pinned",
    "frozen",
    # No date: an earlier position or the raw material has none, or the
    # calendar holds no working time.
    "undated",
]


@dataclass(frozen=True)
class PlacementReason:
    """What set an order's start. `day` is the constraint's day and `moment`
    its moment where it has one; the other fields refer to what the kind
    names and are None otherwise."""

    kind: PlacementReasonKind
    day: date | None = None
    moment: datetime | None = None
    previous_order_id: int | None = None
    position_id: int | None = None
    order_item_id: int | None = None
    expected_date: date | None = None
    response_time_days: int = 0
    wait_after_minutes: int = 0
    late: bool = False
    arrived: bool = False
    forecast: bool = False
    pieces_processed: float | None = None
    quantity: float | None = None
    overrun: bool = False


def running_reason(ctx: OrderSchedulingContext, overrun: bool) -> PlacementReason:
    return PlacementReason(
        kind="in_progress",
        pieces_processed=ctx.pieces_processed,
        quantity=ctx.quantity,
        overrun=overrun,
    )


def queued_reason(
    ctx: OrderSchedulingContext,
    cursor: datetime | None,
    earliest_day: date | None,
    not_before: date | None,
    material_day: date | None,
    now: datetime | None,
) -> PlacementReason:
    """The constraint that set a queued order's start, the latest of the
    floors place_on_queue takes, `now` among them only where it floors the
    order. A tie goes to the queue, then to the predecessor's moment, then
    to the day constraint, so the reason names what a planner would change
    first."""
    day_floor = day_start(earliest_day, ctx.zone) if earliest_day is not None else None
    moment = as_utc(ctx.predecessor_ready_moment) if ctx.predecessor_ready_moment else None
    floors = [f for f in (day_floor, moment, as_utc(now) if now else None) if f is not None]
    if not floors:
        return PlacementReason(kind="ready_now")
    floor = max(floors)
    if cursor is not None and as_utc(cursor) >= floor:
        return PlacementReason(kind="queue", moment=as_utc(cursor))
    if moment is not None and moment >= floor:
        return _internal_predecessor_reason(ctx, moment)
    if day_floor is not None and day_floor >= floor and earliest_day is not None:
        return _day_reason(ctx, earliest_day, not_before, material_day)
    return PlacementReason(kind="ready_now", moment=as_utc(now) if now else None)


def _closest_internal(ctx: OrderSchedulingContext) -> PredecessorPosition | None:
    """The in-house predecessor closest before the order. A chain runs in
    sequence, so its end, refreshed by the walk, is the one that counts;
    the stored values on the snapshot may lag the walk."""
    internal = [
        p
        for p in ctx.predecessor_positions
        if p.kind in (LotPositionKind.INTERNAL, LotPositionKind.MIXED)
    ]
    return max(internal, key=lambda p: p.sequence, default=None)


def _internal_predecessor_reason(ctx: OrderSchedulingContext, moment: datetime) -> PlacementReason:
    closest = _closest_internal(ctx)
    return PlacementReason(
        kind="predecessor",
        moment=moment,
        position_id=closest.position_id if closest is not None else None,
        wait_after_minutes=closest.wait_after_minutes if closest is not None else 0,
    )


def _day_reason(
    ctx: OrderSchedulingContext,
    day: date,
    not_before: date | None,
    material_day: date | None,
) -> PlacementReason:
    """The day constraint that is `day`: not_before, an external arrival
    plus the response time, an in-house predecessor, or the raw material."""
    if not_before == day:
        return PlacementReason(kind="not_before", day=day)
    if as_day(ctx.predecessor_ready_at, ctx.zone) == day:
        arrival = _arrival_on(ctx, day)
        if arrival is not None:
            arrived = arrival.typed_external_date is None
            return PlacementReason(
                kind="order_line",
                day=day,
                position_id=arrival.position_id,
                order_item_id=arrival.order_item_id,
                expected_date=arrival.external_ready_at if arrived else arrival.typed_external_date,
                response_time_days=ctx.response_time_days,
                late=arrival.arrival_late,
                arrived=arrived,
            )
        closest = _closest_predecessor(ctx)
        if closest is not None and _is_forecast(closest, day, ctx):
            return PlacementReason(
                kind="order_line",
                day=day,
                position_id=closest.position_id,
                order_item_id=closest.order_item_id,
                expected_date=day - timedelta(days=ctx.response_time_days),
                response_time_days=ctx.response_time_days,
                forecast=True,
            )
        closest = _closest_internal(ctx)
        return PlacementReason(
            kind="predecessor",
            day=day,
            position_id=closest.position_id if closest is not None else None,
            wait_after_minutes=closest.wait_after_minutes if closest is not None else 0,
        )
    if material_day == day:
        return PlacementReason(
            kind="raw_material", day=day, response_time_days=ctx.response_time_days
        )
    return PlacementReason(kind="ready_now", day=day)


def _closest_predecessor(ctx: OrderSchedulingContext) -> PredecessorPosition | None:
    """The earlier position closest before the order, of any kind."""
    return max(ctx.predecessor_positions, key=lambda p: p.sequence, default=None)


def _is_forecast(pred: PredecessorPosition, day: date, ctx: OrderSchedulingContext) -> bool:
    """Whether the day comes from the walk's forecast of an external share
    without any supplier date: an EXTERNAL position without one, or a MIXED
    one whose in-house share is not what is ready on the day."""
    if pred.external_ready_at is not None:
        return False
    if pred.kind == LotPositionKind.EXTERNAL:
        return True
    if pred.kind != LotPositionKind.MIXED:
        return False
    internal = as_day(pred.completed_ready_at or pred.stored_internal_ready_at, ctx.zone)
    return internal != day


def _arrival_on(ctx: OrderSchedulingContext, day: date) -> PredecessorPosition | None:
    """The external predecessor whose arrival plus the response time is
    `day`, the latest in the chain when several are."""
    for pred in sorted(ctx.predecessor_positions, key=lambda p: p.sequence, reverse=True):
        if pred.kind not in (LotPositionKind.EXTERNAL, LotPositionKind.MIXED):
            continue
        if buffered_ready_day(pred.external_ready_at, None, ctx.response_time_days) == day:
            return pred
    return None
