"""The forward walk's per-order context and predecessor-chain readiness.

The calling use case flattens pre-fetched entities into
OrderSchedulingContext; the functions here derive predecessor readiness and
external forecasts from the earlier positions it carries, so the walk can
refresh them between passes without a repository.

EXTERNAL/MIXED positions without a typed or actual date are forecast
(pickup is the feeding chain's ready date plus the response-time buffer,
delivery is pickup plus the resolved lead days). A typed supplier date
earlier than the chain feeding it is never rewritten, only flagged as
EXTERNAL_DATE_BEFORE_PREDECESSOR on the next INTERNAL or MIXED position.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from dataclasses import field
from dataclasses import replace
from datetime import date
from datetime import datetime
from datetime import timedelta
from datetime import tzinfo
from typing import TYPE_CHECKING
from typing import Literal

from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.services.scheduling.earliest_start import (
    resolve_mixed_predecessor_ready_at,
)
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.shared_kernel.domain.services.clock import as_utc

if TYPE_CHECKING:
    from src.modules.fulfillment.domain.services.scheduling.placement_reason import PlacementReason


@dataclass(frozen=True)
class PredecessorPosition:
    """One earlier, still-open position of the same lot. Carrying these on
    the context lets schedule_all_propagated re-derive predecessor
    readiness every pass without a repository. Canceled positions are left
    out, and so are completed ones, except a completed position whose wait
    after it still runs (`completed`), since its pieces are not ready yet."""

    position_id: int
    sequence: int
    kind: str  # LotPositionKind value
    # Actual delivery, then ready-for-pickup, then typed expected delivery.
    external_ready_at: date | None
    # The tenant day of the latest persisted planned_end over this
    # position's own orders, plus the position's wait after it.
    stored_internal_ready_at: date | None
    lead_days: int | None = None
    # The supplier's typed promise. None once an actual delivery or pickup
    # event happened, since facts are never flagged as stale.
    typed_external_date: date | None = None
    # Raw-material readiness, set only for a sequence-1 position; it is the
    # forecast basis there because no earlier position feeds it.
    material_ready_at: date | None = None
    # The latest persisted planned_end over this position's own orders as a
    # moment, plus the position's wait after it, the floor a successor starts
    # from (predecessor_ready_moment).
    stored_internal_ready_moment: datetime | None = None
    # An UNASSIGNED position whose fabrication steps use a method that is
    # usually outsourced. It gets a forecast for display, but the forecast
    # never feeds the chain, so it moves no internal order.
    outsourced_unassigned: bool = False
    # The clock minutes the pieces wait after the position
    # (wait_after.position_wait_after_minutes), already in the ready values
    # above; the backward passes read it on its own.
    wait_after_minutes: int = 0
    # When the pieces of the position's completed orders are ready, the
    # latest actual_end plus the wait, as a day and a moment. Set only while
    # that is today or later, so a finished wait holds nothing back. A
    # position still running takes the later of these and its own end.
    completed_ready_at: date | None = None
    completed_ready_moment: datetime | None = None
    # The whole position is completed and only its wait still runs. It is
    # ready at completed_ready_*, is never undated, and has no work left
    # for a backward pass.
    completed: bool = False
    # The live order line of an EXTERNAL or MIXED position, and whether its
    # expected arrival has passed without the delivery, so it counts as
    # today; both only name the arrival to a planner.
    order_item_id: int | None = None
    arrival_late: bool = False


LeadDaysSource = Literal["supplier", "method", "default"]


def resolve_position_lead_days_with_source(
    steps: list[LotStep], supplier_override: int | None, default_external_lead_days: int
) -> tuple[int, LeadDaysSource]:
    """A position's lead time in calendar days and where it came from.

    The supplier's own lead time wins when set. Otherwise each step adds its
    fabrication method's lead time, or the admin default where that is
    unset; the source is "method" if at least one step had its own value.
    Inspection steps have no fabrication method and add nothing."""
    if supplier_override is not None:
        return supplier_override, "supplier"
    total = 0
    any_step_has_own_lead_time = False
    for step in steps:
        if step.role == StepRole.INSPECTION:
            continue
        if step.fabrication_method_lead_time_days is not None:
            any_step_has_own_lead_time = True
            total += step.fabrication_method_lead_time_days
        else:
            total += default_external_lead_days
    return total, ("method" if any_step_has_own_lead_time else "default")


def resolve_position_lead_days(
    steps: list[LotStep], supplier_override: int | None, default_external_lead_days: int
) -> int:
    """resolve_position_lead_days_with_source without the source."""
    return resolve_position_lead_days_with_source(
        steps, supplier_override, default_external_lead_days
    )[0]


@dataclass(frozen=True)
class ExternalForecast:
    """One EXTERNAL/MIXED position's forecast pickup and delivery dates,
    both None while the chain feeding it has no known ready date."""

    position_id: int
    planned_pickup_date: date | None
    planned_delivery_date: date | None
    # External work only: the latest day it can leave for the supplier,
    # counted back from the lot's target date (forecast_external_work).
    # None without a target date, and for a forecast that only the walk
    # wrote, which forecast_external_work then completes.
    latest_pickup_date: date | None = None
    # The latest pickup plus the position's lead days.
    latest_delivery_date: date | None = None


def resolve_external_forecast(
    pred: PredecessorPosition, chain_end_before: date | None, response_time_days: int
) -> ExternalForecast:
    """Pickup is the ready date of the chain before the position (raw
    material for sequence 1) plus the response-time buffer; delivery is
    pickup plus the lead days."""
    base = pred.material_ready_at if pred.sequence <= 1 else chain_end_before
    pickup = base + timedelta(days=response_time_days) if base is not None else None
    delivery = (
        pickup + timedelta(days=pred.lead_days)
        if pickup is not None and pred.lead_days is not None
        else None
    )
    return ExternalForecast(
        position_id=pred.position_id, planned_pickup_date=pickup, planned_delivery_date=delivery
    )


@dataclass(frozen=True)
class OrderSchedulingContext:
    """Everything the forward walk needs for one ProductionOrder,
    pre-fetched and flattened by the calling use case, no I/O here. Its
    dates are days of the tenant's timezone `zone`, in which the walk also
    reads the day of a planned end or of now."""

    order_id: int
    queue_sequence: int
    status: str  # ProductionOrderStatus
    pinned: bool
    estimated_duration_minutes: int
    not_before: date | None
    actual_start: datetime | None
    existing_planned_start: datetime | None
    existing_planned_end: datetime | None
    predecessor_ready_at: date | None
    material_ready_at: date | None
    target_date: date | None  # the lot's due date, for PAST_TARGET_DATE
    capability_mismatch: bool
    uncategorized_step: bool
    position_not_fully_queued: bool
    time_estimate_source: str  # "measured" | "budget" | "missing" | "not_applicable"
    # A queued order inside the frozen window keeps its planned window like
    # a pinned one, without being pinned (AdminProductionSettings).
    frozen: bool = False
    # Every step's fabrication method needs no machine, so the order is
    # walked against the admin default calendar instead of being flagged
    # NO_MACHINE_ASSIGNED.
    is_manual_step: bool = False
    # False when the upstream (predecessor step, or raw material for
    # sequence 1) has made nothing available beyond what this position
    # already completed, which is when Start/Resume is blocked. True lets
    # the walk date an order even when the rest of its chain is unknown,
    # because parts are already waiting here.
    upstream_input_available: bool = True
    position_sequence: int = 1
    # An open earlier position of the lot has no date signal of its own,
    # so the chain's finish is unknown and the walk leaves the order undated.
    predecessor_chain_unknown: bool = False
    # A pool-assigned order is a planner decision, so it is walked by the
    # pool queue and never flagged NO_MACHINE_ASSIGNED.
    machine_pool_id: int | None = None
    lot_id: int | None = None
    lot_position_id: int | None = None
    # Earlier open positions of the lot, in no guaranteed order. Empty for
    # sequence 1 or a caller not wired for propagation, in which case
    # refresh_predecessor_readiness leaves the context unchanged.
    predecessor_positions: tuple[PredecessorPosition, ...] = ()
    # Added to an external predecessor's or the raw material's ready day.
    response_time_days: int = 0
    # Added to the moment the in-house predecessors end
    # (predecessor_ready_moment).
    internal_handoff_minutes: int = 0
    # The clock minutes the pieces wait after this order's own position,
    # added to its planned end where a successor or the lot's target date
    # reads it.
    wait_after_minutes: int = 0
    # A running order's progress: its pieces, the pieces it processed so far
    # (accepted and rejected, a reversal netted out) and the minutes one
    # more piece takes, so an overrun stretches its planned end.
    quantity: float = 0.0
    pieces_processed: float = 0.0
    minutes_per_piece: float = 0.0
    # The pieces it had processed when it last resumed, the base of its
    # original end after that resume.
    pieces_processed_at_resume: float = 0.0
    # This is the first INTERNAL or MIXED position after an EXTERNAL or
    # MIXED position whose typed date is earlier than the chain feeding it.
    stale_external_predecessor: bool = False
    # The assigned machine has an open downtime; the walk still places the
    # order and only flags MACHINE_DOWN.
    machine_down: bool = False
    # The end of the order's latest closed interruption. actual_start keeps
    # the first start, so a resumed order is placed from this moment.
    last_resumed_at: datetime | None = None
    # When the internal work of the earlier open positions ends, as a moment,
    # so a queued order never starts before its predecessor ends, also on
    # the same day; predecessor_ready_at is the readiness as a day with the
    # response-time buffer.
    predecessor_ready_moment: datetime | None = None
    # The tenant's timezone. A day such as not_before starts at its local
    # midnight, and a moment counts on its local day against target_date.
    zone: tzinfo = field(kw_only=True)


@dataclass(frozen=True)
class ScheduledOrder:
    order_id: int
    planned_start: datetime | None
    planned_end: datetime | None
    conflicts: list[str]
    # The pool member a dated pool placement landed on. Informational for
    # read models such as the board's capacity rollup and never persisted,
    # because the concrete machine choice stays deferred.
    trial_machine_id: int | None = None
    # What set the start (placement_reason.py), never persisted.
    reason: "PlacementReason | None" = None


def _with_completed[T: (date, datetime)](
    pred: PredecessorPosition, internal_ready: T | None, completed: T | None
) -> T | None:
    """A position's in-house readiness, a day or a moment, with its
    completed orders' wait: a completed position is ready at that alone, an
    undated running one stays undated, and a dated one is ready at the later
    of both."""
    if pred.completed:
        return completed
    if internal_ready is None or completed is None:
        return internal_ready
    return max(internal_ready, completed)


def _internal_ready_day(
    pred: PredecessorPosition, placed_end_by_position: dict[int, date | None]
) -> date | None:
    """The day the in-house pieces of a position are ready: this run's
    placed end when the position has an order in the run, None included,
    else the stored one, either with the wait, and the completed orders'
    wait on top."""
    internal = placed_end_by_position.get(pred.position_id, pred.stored_internal_ready_at)
    return _with_completed(pred, internal, pred.completed_ready_at)


def position_ready_at_in_run(
    pred: PredecessorPosition, placed_end_by_position: dict[int, date | None]
) -> date | None:
    """One earlier position's contribution to a successor's readiness,
    preferring this run's placed end over the stored one. A position that
    appears in placed_end_by_position uses that value even when it is None,
    because an undated in-run result is more honest than a stale stored
    date; only a position with no order in this run falls back to storage.
    Both include the position's wait after it."""
    if pred.kind == LotPositionKind.EXTERNAL:
        return pred.external_ready_at
    if pred.kind == LotPositionKind.INTERNAL:
        return _internal_ready_day(pred, placed_end_by_position)
    if pred.kind == LotPositionKind.MIXED:
        return resolve_mixed_predecessor_ready_at(
            pred.external_ready_at, _internal_ready_day(pred, placed_end_by_position)
        )
    return None


def _predecessor_shares_with_forecast(
    pred: PredecessorPosition,
    placed_end_by_position: dict[int, date | None],
    chain_end_before: date | None,
    response_time_days: int,
) -> tuple[date | None, date | None, ExternalForecast | None]:
    """The ready days of a predecessor's external and in-house shares, as
    position_ready_at_in_run reads them, except that an EXTERNAL/MIXED
    predecessor without a typed or actual date falls back to its forecast
    instead of leaving the chain unknown. The forecast is returned even when
    a typed date wins, because it is persisted regardless. An outsourced
    UNASSIGNED position is forecast as well, but contributes nothing to the
    chain, exactly as before it had a forecast. A completed position whose
    wait still runs gets no forecast, so the dates it keeps stay as they
    are."""
    if pred.completed:
        external = (
            pred.external_ready_at
            if pred.kind in (LotPositionKind.EXTERNAL, LotPositionKind.MIXED)
            else None
        )
        return external, _internal_ready_day(pred, placed_end_by_position), None
    if pred.kind == LotPositionKind.UNASSIGNED and pred.outsourced_unassigned:
        return None, None, resolve_external_forecast(pred, chain_end_before, response_time_days)
    if pred.kind == LotPositionKind.EXTERNAL:
        forecast = resolve_external_forecast(pred, chain_end_before, response_time_days)
        return pred.external_ready_at or forecast.planned_delivery_date, None, forecast
    if pred.kind == LotPositionKind.MIXED:
        forecast = resolve_external_forecast(pred, chain_end_before, response_time_days)
        return (
            pred.external_ready_at or forecast.planned_delivery_date,
            _internal_ready_day(pred, placed_end_by_position),
            forecast,
        )
    return None, position_ready_at_in_run(pred, placed_end_by_position), None


def buffered_ready_day(
    external_ready_at: date | None, internal_ready_at: date | None, response_time_days: int
) -> date | None:
    """When a predecessor's pieces are ready for the next step, as a day:
    the external share's arrival plus the response time, since pieces that
    arrive on a day are not ready for the next step that day, and the
    in-house share's own end day, whose handoff counts in minutes on the
    moment (predecessor_ready_moment). The later of both when both are
    known."""
    buffered_external = (
        external_ready_at + timedelta(days=response_time_days)
        if external_ready_at is not None
        else None
    )
    return resolve_mixed_predecessor_ready_at(buffered_external, internal_ready_at)


def stale_external_predecessor(
    predecessor_positions: tuple[PredecessorPosition, ...],
    placed_end_by_position: dict[int, date | None] | None,
) -> bool:
    """True when the position these predecessors feed is the first
    INTERNAL or MIXED position after an EXTERNAL or MIXED predecessor whose
    typed date is earlier than the chain feeding it.

    A stale date sets a pending flag that the next INTERNAL or MIXED
    position consumes, so only the first position downstream is flagged.
    Whatever is still pending at the end belongs to the position right
    after the tuple. placed_end_by_position is None on the plain-read path,
    which uses the stored dates."""
    placed = placed_end_by_position if placed_end_by_position is not None else {}
    chain_end_so_far: date | None = None
    pending = False
    for pred in sorted(predecessor_positions, key=lambda p: p.sequence):
        ready_at = position_ready_at_in_run(pred, placed)
        # A completed position that only waits is no position to flag.
        if pred.kind in (LotPositionKind.INTERNAL, LotPositionKind.MIXED) and not pred.completed:
            pending = False
        if (
            pred.kind in (LotPositionKind.EXTERNAL, LotPositionKind.MIXED)
            and pred.typed_external_date is not None
            and chain_end_so_far is not None
            and pred.typed_external_date < chain_end_so_far
        ):
            pending = True
        if ready_at is not None:
            chain_end_so_far = (
                max(chain_end_so_far, ready_at) if chain_end_so_far is not None else ready_at
            )
    return pending


def _walk_predecessor_positions(
    predecessor_positions: tuple[PredecessorPosition, ...],
    placed_end_by_position: dict[int, date | None],
    response_time_days: int,
) -> tuple[date | None, bool, dict[int, ExternalForecast]]:
    """Walks the predecessors in sequence order so each forecast can use
    the chain before it. Returns the latest ready day with the response
    time added to every arrival (buffered_ready_day), whether any
    predecessor contributed nothing, and the forecasts by position id. The
    chain a forecast builds on is unbuffered, since the forecast pickup adds
    the response time itself."""
    contributed: list[date] = []
    chain_unknown = False
    chain_end_so_far: date | None = None
    forecasts: dict[int, ExternalForecast] = {}
    for pred in sorted(predecessor_positions, key=lambda p: p.sequence):
        external_ready_at, internal_ready_at, forecast = _predecessor_shares_with_forecast(
            pred, placed_end_by_position, chain_end_so_far, response_time_days
        )
        if forecast is not None:
            forecasts[pred.position_id] = forecast
        ready_at = resolve_mixed_predecessor_ready_at(external_ready_at, internal_ready_at)
        if ready_at is None:
            chain_unknown = True
            continue
        buffered = buffered_ready_day(external_ready_at, internal_ready_at, response_time_days)
        assert buffered is not None  # a known share gives a known buffered day
        contributed.append(buffered)
        chain_end_so_far = (
            max(chain_end_so_far, ready_at) if chain_end_so_far is not None else ready_at
        )
    predecessor_ready_at = max(contributed) if contributed else None
    return predecessor_ready_at, chain_unknown, forecasts


def predecessor_ready_moment(
    predecessor_positions: tuple[PredecessorPosition, ...],
    placed_moment_by_position: dict[int, datetime | None] | None,
    handoff_minutes: int = 0,
) -> datetime | None:
    """When the pieces of the earlier positions' internal work are ready
    for the next order: each internal or mixed position's latest planned
    end in this run, or its stored one when the position has no order in
    the run, each with the position's wait after it, plus the handoff
    minutes. None when none of them is dated.
    External shares, and the response time after them in whole days, count
    through predecessor_ready_at."""
    placed = placed_moment_by_position or {}
    ends: list[datetime] = []
    for pred in predecessor_positions:
        if pred.kind not in (LotPositionKind.INTERNAL, LotPositionKind.MIXED):
            continue
        # A position in the run counts with its in-run end, None included.
        end = _with_completed(
            pred,
            placed.get(pred.position_id, pred.stored_internal_ready_moment),
            pred.completed_ready_moment,
        )
        if end is not None:
            ends.append(as_utc(end))
    return max(ends) + timedelta(minutes=handoff_minutes) if ends else None


def stored_predecessor_readiness(
    predecessor_positions: tuple[PredecessorPosition, ...], response_time_days: int
) -> tuple[date | None, bool]:
    """The read path's predecessor readiness from the stored dates, with the
    response time after every arrival (buffered_ready_day): the latest
    ready day and whether an earlier position has no date signal. Unlike
    the walk, an undated external position is not forecast, so it leaves
    the chain unknown."""
    contributed: list[date] = []
    chain_unknown = False
    for pred in predecessor_positions:
        external_ready_at = (
            pred.external_ready_at
            if pred.kind in (LotPositionKind.EXTERNAL, LotPositionKind.MIXED)
            else None
        )
        internal_ready_at = (
            _internal_ready_day(pred, {})
            if pred.kind in (LotPositionKind.INTERNAL, LotPositionKind.MIXED)
            else None
        )
        buffered = buffered_ready_day(external_ready_at, internal_ready_at, response_time_days)
        if buffered is None:
            chain_unknown = True
            continue
        contributed.append(buffered)
    return (max(contributed) if contributed else None), chain_unknown


def refresh_predecessor_readiness(
    ctx: OrderSchedulingContext,
    placed_end_by_position: dict[int, date | None],
    placed_moment_by_position: dict[int, datetime | None] | None = None,
) -> OrderSchedulingContext:
    """Re-derives the context's predecessor readiness fields from this
    run's placed ends, for schedule_all_propagated's refresh between
    passes. Unlike the plain-read version, an undated EXTERNAL/MIXED
    predecessor falls back to its forecast."""
    if ctx.position_sequence <= 1 or not ctx.predecessor_positions:
        return ctx
    predecessor_ready_at, chain_unknown, _forecasts = _walk_predecessor_positions(
        ctx.predecessor_positions, placed_end_by_position, ctx.response_time_days
    )
    return replace(
        ctx,
        predecessor_ready_at=predecessor_ready_at,
        predecessor_chain_unknown=chain_unknown,
        stale_external_predecessor=stale_external_predecessor(
            ctx.predecessor_positions, placed_end_by_position
        ),
        predecessor_ready_moment=predecessor_ready_moment(
            ctx.predecessor_positions, placed_moment_by_position, ctx.internal_handoff_minutes
        ),
    )


def resolve_chain_external_forecasts(
    positions: tuple[PredecessorPosition, ...],
    placed_end_by_position: dict[int, date | None],
    response_time_days: int,
) -> dict[int, ExternalForecast]:
    """The forecast of every external position in one lot's chain of open
    positions, by position id. It walks the chain exactly as an order's
    predecessors are walked, so a position that feeds a later order gets
    the same forecast either way, and a position that feeds none, such as
    the last one of a lot, gets one too."""
    return _walk_predecessor_positions(positions, placed_end_by_position, response_time_days)[2]


def resolve_external_forecasts(
    contexts: Iterable[OrderSchedulingContext], placed_end_by_position: dict[int, date | None]
) -> dict[int, ExternalForecast]:
    """The forecast of every EXTERNAL/MIXED position described across the
    contexts. A forecast depends only on the positions before it, so two
    contexts describing the same position agree and merging is safe."""
    forecasts: dict[int, ExternalForecast] = {}
    for ctx in contexts:
        if not ctx.predecessor_positions:
            continue
        _ready_at, _chain_unknown, ctx_forecasts = _walk_predecessor_positions(
            ctx.predecessor_positions, placed_end_by_position, ctx.response_time_days
        )
        forecasts.update(ctx_forecasts)
    return forecasts
