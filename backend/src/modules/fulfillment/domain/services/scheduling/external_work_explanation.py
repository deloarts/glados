"""How the three dates of a position of external work come about, as terms
the procurement list shows on hover: the ready date of the step before, or
of the raw material, plus the response time for "ready from"; the lot's
target date less the safety margin, the steps after it and its lead days
for the latest pickup; the supplier's date, else the latest pickup plus the
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
from src.modules.fulfillment.domain.services.scheduling._shared import as_day
from src.modules.fulfillment.domain.services.scheduling.candidate_ordering import position_lead_days
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
    RESPONSE_TIME = "response_time"
    # The lot's own target date, or the desired date of demand `reference`.
    TARGET_LOT = "target_lot"
    TARGET_DEMAND = "target_demand"
    SAFETY_MARGIN = "safety_margin"
    # A step after this one, `minutes` of work in `days` days.
    LATER_STEP = "later_step"
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
    source, the settings the walk used and the tenant's timezone."""

    target_date: date | None
    target_demand_id: int | None
    response_time_days: int
    safety_margin_days: int
    default_external_lead_days: int
    zone: tzinfo


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


def _ready_at(position: LotPosition, zone: tzinfo) -> date | None:
    """An earlier position's ready day, as position_ready_at_in_run reads it
    with the walk's forecast for an undated external one."""
    internal = resolve_internal_predecessor_ready_at(
        [o.planned_end for o in position.production_orders], zone=zone
    )
    external = None
    if position.order_item_id is not None:
        external = resolve_external_predecessor_ready_at(
            position.order_item_delivery_date,
            position.order_item_ready_for_pickup_date,
            position.expected_delivery_date,
            zone=zone,
        )
    external = external or position.planned_delivery_date
    if position.kind == LotPositionKind.INTERNAL:
        return internal
    if position.kind == LotPositionKind.EXTERNAL:
        return external
    if position.kind == LotPositionKind.MIXED:
        return resolve_mixed_predecessor_ready_at(external, internal)
    return None


def _explain_ready_from(
    position: LotPosition, lot: ProductionLot, inputs: ExplanationInputs
) -> tuple[DateTerm, ...]:
    earlier = [
        p for p in lot.positions if p.sequence < position.sequence and p.status not in _CLOSED
    ]
    base: DateTerm | None = None
    if position.sequence <= 1:
        material = (
            as_day(lot.source_delivery_date, inputs.zone) or lot.source_expected_delivery_date
        )
        if material is not None:
            base = DateTerm(DateTermKind.RAW_MATERIAL, date=material)
    else:
        dated = [(ready, p) for p in earlier if (ready := _ready_at(p, inputs.zone)) is not None]
        if dated:
            ready, source = max(dated, key=lambda pair: (pair[0], pair[1].sequence))
            base = DateTerm(DateTermKind.AFTER_STEP, date=ready, methods=_methods(source))
    if base is None or base.date is None:
        return ()
    return (
        base,
        DateTerm(DateTermKind.RESPONSE_TIME, days=inputs.response_time_days),
        DateTerm(DateTermKind.RESULT, date=base.date + timedelta(days=inputs.response_time_days)),
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
