"""How the three dates of a position of external work come about, as terms
the procurement list shows on hover: the ready date of the step before, or
of the raw material, counted as today once an expected arrival has
passed, plus the response time for "ready from"; the lot's
target date less the safety margin, the steps after it and its lead days
for the latest pickup, with the days its pieces wait after each of those
steps; the supplier's date, else the latest pickup plus the
lead days, for "back by". The arithmetic is the walk's (walk_context and
external_work), so a term list that does not end on the stored date means
the plan is still being updated."""

from dataclasses import dataclass
from dataclasses import field
from datetime import date
from datetime import timedelta
from datetime import tzinfo

from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.policies.wait_after import latest_ready_moment
from src.modules.fulfillment.domain.policies.wait_after import position_wait_after_minutes
from src.modules.fulfillment.domain.policies.wait_after import step_waits
from src.modules.fulfillment.domain.policies.wait_after import wait_days
from src.modules.fulfillment.domain.services.scheduling._shared import as_day
from src.modules.fulfillment.domain.services.scheduling.candidate_ordering import position_lead_days
from src.modules.fulfillment.domain.services.scheduling.earliest_start import expected_arrival_day
from src.modules.fulfillment.domain.services.scheduling.earliest_start import (
    resolve_external_predecessor_ready_at,
)
from src.modules.fulfillment.domain.services.scheduling.earliest_start import (
    resolve_internal_predecessor_ready_at,
)
from src.modules.fulfillment.domain.services.scheduling.earliest_start import (
    resolve_mixed_predecessor_ready_at,
)
from src.modules.fulfillment.domain.services.scheduling.external_work import (
    position_has_external_work,
)
from src.modules.fulfillment.domain.services.scheduling.walk_context import LeadDaysSource
from src.modules.fulfillment.domain.services.scheduling.walk_context import (
    resolve_position_lead_days_with_source,
)
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.production_status import (
    ACTIVE_PRODUCTION_ORDER_STATUSES,
)
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum

_CLOSED = frozenset({LotPositionStatus.COMPLETED, LotPositionStatus.CANCELED})

# DateTerm's field `date` shadows the type inside its class body, where the
# default is bound before the annotation is read.
Day = date


class DateTermKind(StrValueEnum):
    """One line of a date's explanation."""

    # The ready date of the step before, which `methods` names.
    AFTER_STEP = "after_step"
    # The raw material's delivery, or its expected delivery.
    RAW_MATERIAL = "raw_material"
    # The expected arrival above has passed, so it counts as today, `date`.
    LATE_ARRIVAL = "late_arrival"
    RESPONSE_TIME = "response_time"
    # The lot's own target date, or the desired date of demand `reference`.
    TARGET_LOT = "target_lot"
    TARGET_DEMAND = "target_demand"
    SAFETY_MARGIN = "safety_margin"
    # A step after this one, `minutes` of work in `days` days.
    LATER_STEP = "later_step"
    # The pieces wait `minutes` after that step, counted as `days` days.
    WAIT_AFTER = "wait_after"
    # The day it has to be back.
    BACK_BY = "back_by"
    # The lead days, from the supplier, the methods or the default.
    LEAD_TIME = "lead_time"
    LATEST_PICKUP = "latest_pickup"
    # The supplier's date on the line of order `reference`.
    SUPPLIER_DATE = "supplier_date"
    RESULT = "result"


@dataclass(frozen=True)
class DateTerm:
    kind: DateTermKind
    date: Day | None = None
    days: int | None = None
    minutes: int | None = None
    methods: tuple[dict[str, str], ...] = field(default_factory=tuple)
    source: LeadDaysSource | None = None
    reference: str = ""


@dataclass(frozen=True)
class ExternalWorkExplanation:
    ready_from: tuple[DateTerm, ...]
    latest_pickup: tuple[DateTerm, ...]
    back_by: tuple[DateTerm, ...]
    # The terms do not end on a stored date, since the walk has not caught
    # up with a change yet.
    stale: bool


@dataclass(frozen=True)
class ExplanationInputs:
    """What the explanation reads besides the lot: the target date with its
    source, the settings the walk used, the tenant's timezone and today in
    it."""

    target_date: date | None
    target_demand_id: int | None
    response_time_days: int
    safety_margin_days: int
    default_external_lead_days: int
    zone: tzinfo
    today: date


def remaining_minutes(position: LotPosition, orders: list[ProductionOrder]) -> int:
    """The minutes of work left on a position: its active orders' estimates,
    or, before it has any, its steps' setup plus their minutes per piece for
    the pieces not done yet."""
    active = [o for o in orders if o.status in ACTIVE_PRODUCTION_ORDER_STATUSES]
    if active:
        return sum(o.estimated_duration_minutes for o in active)
    pieces = max(position.quantity - position.quantity_completed, 0.0)
    minutes = 0.0
    for step in position.steps:
        per_piece = step.estimated_minutes_per_piece
        if per_piece is None:
            per_piece = step.time_budget_per_piece or 0.0
        minutes += (step.estimated_setup_minutes or 0) + per_piece * pieces
    return round(minutes)


def _methods(position: LotPosition) -> tuple[dict[str, str], ...]:
    return tuple(
        step.fabrication_method_name.as_dict()
        for step in position.steps
        if step.role == StepRole.FABRICATION
    )


def _lead_days(position: LotPosition, default: int) -> tuple[int, LeadDaysSource]:
    """As the walk resolves them: a supplier line's lead time wins only for
    a position that has one."""
    override = (
        position.order_item_supplier_external_lead_time_days
        if position.kind in (LotPositionKind.EXTERNAL, LotPositionKind.MIXED)
        else None
    )
    return resolve_position_lead_days_with_source(position.steps, override, default)


def _wait(position: LotPosition) -> int:
    return position_wait_after_minutes(position.kind, step_waits(position.steps))


def _completed_ready_day(position: LotPosition, inputs: ExplanationInputs) -> date | None:
    """The day the pieces of the position's completed orders are ready, the
    latest actual end plus the wait, while that is today or later, as the
    walk reads it."""
    wait = _wait(position)
    if wait <= 0:
        return None
    moment = latest_ready_moment(
        (o.actual_end, wait)
        for o in position.production_orders
        if o.status == ProductionOrderStatus.COMPLETED
    )
    if moment is None:
        return None
    day = moment.astimezone(inputs.zone).date()
    return day if day >= inputs.today else None


def _counts_before(position: LotPosition, inputs: ExplanationInputs) -> bool:
    """Whether an earlier position still holds the pieces back: an open one,
    or a completed one whose wait after it still runs."""
    if position.status not in _CLOSED:
        return True
    return (
        position.status == LotPositionStatus.COMPLETED
        and _completed_ready_day(position, inputs) is not None
    )


def _internal_ready_day(position: LotPosition, inputs: ExplanationInputs) -> date | None:
    """The day the in-house pieces are ready, the latest planned end plus the
    wait, with the completed orders' wait on top, as the walk reads it."""
    completed = _completed_ready_day(position, inputs)
    if position.status == LotPositionStatus.COMPLETED:
        return completed
    wait = _wait(position)
    moment = latest_ready_moment((o.planned_end, wait) for o in position.production_orders)
    internal = resolve_internal_predecessor_ready_at([moment], zone=inputs.zone)
    if internal is None or completed is None:
        return internal
    return max(internal, completed)


def _ready_at(position: LotPosition, inputs: ExplanationInputs) -> tuple[date, date] | None:
    """An earlier position's ready day, as position_ready_at_in_run reads it
    with the walk's forecast for an undated external one, and the day to
    show for it: the passed expected delivery when that counts as today,
    else the ready day itself. None for a position without a ready day."""
    internal = _internal_ready_day(position, inputs)
    external = None
    expected = None
    if position.order_item_id is not None:
        external = resolve_external_predecessor_ready_at(
            position.order_item_delivery_date,
            position.order_item_ready_for_pickup_date,
            position.expected_delivery_date,
            zone=inputs.zone,
            today=inputs.today,
        )
        if (
            position.order_item_delivery_date is None
            and position.order_item_ready_for_pickup_date is None
        ):
            expected = position.expected_delivery_date
    external = external or position.planned_delivery_date
    ready: date | None = None
    if position.kind == LotPositionKind.INTERNAL:
        ready = internal
    elif position.kind == LotPositionKind.EXTERNAL:
        ready = external
    elif position.kind == LotPositionKind.MIXED:
        ready = resolve_mixed_predecessor_ready_at(external, internal)
    if ready is None:
        return None
    if expected is not None and expected < ready and ready == external:
        return ready, expected
    return ready, ready


def _explain_ready_from(
    position: LotPosition, lot: ProductionLot, inputs: ExplanationInputs
) -> tuple[DateTerm, ...]:
    earlier = [
        p for p in lot.positions if p.sequence < position.sequence and _counts_before(p, inputs)
    ]
    base: DateTerm | None = None
    ready: date | None = None
    if position.sequence <= 1:
        delivered = as_day(lot.source_delivery_date, inputs.zone)
        material = delivered or lot.source_expected_delivery_date
        if material is not None:
            base = DateTerm(DateTermKind.RAW_MATERIAL, date=material)
            ready = (
                material if delivered is not None else expected_arrival_day(material, inputs.today)
            )
    else:
        dated = [(days, p) for p in earlier if (days := _ready_at(p, inputs)) is not None]
        if dated:
            (ready, shown), source = max(dated, key=lambda pair: (pair[0][0], pair[1].sequence))
            base = DateTerm(DateTermKind.AFTER_STEP, date=shown, methods=_methods(source))
    if base is None or ready is None:
        return ()
    late = [DateTerm(DateTermKind.LATE_ARRIVAL, date=ready)] if base.date != ready else []
    return (
        base,
        *late,
        DateTerm(DateTermKind.RESPONSE_TIME, days=inputs.response_time_days),
        DateTerm(DateTermKind.RESULT, date=ready + timedelta(days=inputs.response_time_days)),
    )


def _explain_latest_pickup(
    position: LotPosition, lot: ProductionLot, inputs: ExplanationInputs
) -> tuple[DateTerm, ...]:
    if inputs.target_date is None:
        return ()
    terms: list[DateTerm] = [
        DateTerm(
            DateTermKind.TARGET_DEMAND,
            date=inputs.target_date,
            reference=str(inputs.target_demand_id),
        )
        if inputs.target_demand_id is not None
        else DateTerm(DateTermKind.TARGET_LOT, date=inputs.target_date),
        DateTerm(DateTermKind.SAFETY_MARGIN, days=inputs.safety_margin_days),
    ]
    back_by = inputs.target_date - timedelta(days=inputs.safety_margin_days)
    later = sorted(
        (p for p in lot.positions if p.sequence > position.sequence and p.status not in _CLOSED),
        key=lambda p: p.sequence,
    )
    for step in later:
        if position_has_external_work(step):
            days, _source = _lead_days(step, inputs.default_external_lead_days)
            terms.append(DateTerm(DateTermKind.LATER_STEP, days=days, methods=_methods(step)))
        else:
            minutes = remaining_minutes(step, step.production_orders)
            days = position_lead_days("internal", minutes, 0)
            terms.append(
                DateTerm(
                    DateTermKind.LATER_STEP, days=days, minutes=minutes, methods=_methods(step)
                )
            )
        back_by -= timedelta(days=days)
        wait = _wait(step)
        if wait > 0:
            terms.append(
                DateTerm(
                    DateTermKind.WAIT_AFTER,
                    days=wait_days(wait),
                    minutes=wait,
                    methods=_methods(step),
                )
            )
            back_by -= timedelta(days=wait_days(wait))
    # The in-house share of a MIXED position waits before it is back too.
    own_wait = _wait(position)
    if own_wait > 0:
        terms.append(
            DateTerm(
                DateTermKind.WAIT_AFTER,
                days=wait_days(own_wait),
                minutes=own_wait,
                methods=_methods(position),
            )
        )
        back_by -= timedelta(days=wait_days(own_wait))
    lead, source = _lead_days(position, inputs.default_external_lead_days)
    terms += [
        DateTerm(DateTermKind.BACK_BY, date=back_by),
        DateTerm(DateTermKind.LEAD_TIME, days=lead, source=source),
        DateTerm(DateTermKind.RESULT, date=back_by - timedelta(days=lead)),
    ]
    return tuple(terms)


def _explain_back_by(position: LotPosition, inputs: ExplanationInputs) -> tuple[DateTerm, ...]:
    if position.expected_delivery_date is not None:
        return (
            DateTerm(
                DateTermKind.SUPPLIER_DATE,
                date=position.expected_delivery_date,
                reference=position.order_number,
            ),
        )
    if position.latest_pickup_date is None:
        return ()
    lead, source = _lead_days(position, inputs.default_external_lead_days)
    return (
        DateTerm(DateTermKind.LATEST_PICKUP, date=position.latest_pickup_date),
        DateTerm(DateTermKind.LEAD_TIME, days=lead, source=source),
        DateTerm(DateTermKind.RESULT, date=position.latest_pickup_date + timedelta(days=lead)),
    )


def _ends_on(terms: tuple[DateTerm, ...], stored: date | None) -> bool:
    """Whether a term list agrees with the stored date; an empty one agrees
    only with no date."""
    if not terms:
        return stored is None
    last = terms[-1]
    return last.kind != DateTermKind.RESULT or last.date == stored


def explain_external_work(
    position: LotPosition, lot: ProductionLot, inputs: ExplanationInputs, *, ready_now: bool
) -> ExternalWorkExplanation:
    """The terms of the position's three dates. A position whose pieces are
    there already needs no ready date, so it gets no terms for it."""
    ready_from = () if ready_now else _explain_ready_from(position, lot, inputs)
    latest_pickup = _explain_latest_pickup(position, lot, inputs)
    back_by = _explain_back_by(position, inputs)
    stale = not (
        (ready_now or _ends_on(ready_from, position.planned_pickup_date))
        and _ends_on(latest_pickup, position.latest_pickup_date)
    )
    return ExternalWorkExplanation(
        ready_from=ready_from, latest_pickup=latest_pickup, back_by=back_by, stale=stale
    )
