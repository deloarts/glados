"""
Pure functions turning plain, pre-fetched production data into the
production KPI numbers (schedule adherence, on-time delivery, throughput
time, utilization, availability, first pass yield, scrap/rework,
estimate accuracy, waiting time, OEE). No I/O and no framework types here,
only rows the repository layer has already queried and batched.

Every ratio is expressed as a Ratio: `value` is None whenever its
denominator is zero, so a caller never divides by zero and never has to
special-case an empty period itself.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
from datetime import tzinfo

from src.modules.fulfillment.domain.entities.production_order_interruption import (
    ProductionOrderInterruption,
)
from src.modules.fulfillment.domain.policies.scheduling import net_work_minutes
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.shared_kernel.domain.services.clock import start_of_iso_week

# ══════════════════════════════════════════════════════════════════════
# Ratio and small numeric helpers
# ══════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class Ratio:
    """A fraction 0..1 plus the raw counts it was built from. `value` is
    None when `denominator` is zero, the only case a KPI has no defined
    ratio, never a ZeroDivisionError."""

    value: float | None
    numerator: float
    denominator: float


def _ratio(numerator: float, denominator: float) -> Ratio:
    value = numerator / denominator if denominator else None
    return Ratio(value=value, numerator=numerator, denominator=denominator)


def ratio(numerator: float, denominator: float) -> Ratio:
    """Public entry point for building a Ratio outside this module (the
    use case's overall, cross-machine utilization/availability figures),
    same zero-denominator-is-None rule as every formula below."""
    return _ratio(numerator, denominator)


def percentile(values: Sequence[float], fraction: float) -> float | None:
    """Linear-interpolation percentile (fraction in [0, 1]), None for an
    empty input."""
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * fraction
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    if lower == upper:
        return ordered[lower]
    weight = rank - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * weight


def median(values: Sequence[float]) -> float | None:
    """The 50th percentile, None for an empty input."""
    return percentile(values, 0.5)


# ══════════════════════════════════════════════════════════════════════
# Rows: plain data the repository layer hands to this module
# ══════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class FabricationMethodRef:
    id: int
    name: LocalizedText


@dataclass(frozen=True)
class CompletedOrderRow:
    """One ProductionOrder with status=completed and actual_end inside the
    requested period. `interruptions` feeds net_work_minutes directly, so
    this module never re-derives that formula. `fabrication_methods` are
    the distinct fabrication-role methods of the order's own lot
    position (a position with several fabrication steps attributes its
    ratio to each one)."""

    order_id: int
    machine_id: int | None
    lot_id: int
    actual_start: datetime | None
    actual_end: datetime
    planned_end_at_start: datetime | None
    estimated_duration_minutes: int
    interruptions: tuple[ProductionOrderInterruption, ...]
    fabrication_methods: tuple[FabricationMethodRef, ...]


def _net_minutes(row: CompletedOrderRow) -> int | None:
    return net_work_minutes(row.actual_start, row.actual_end, row.interruptions)


@dataclass(frozen=True)
class CompletionRow:
    """One ProductionOrderCompletion with completion_date inside the
    requested period, denormalized with the made item it completes work
    on for the quality-by-item breakdown."""

    completion_id: int
    made_item_id: int
    made_item_part_number: str
    made_item_article_name: str
    quantity: float
    quantity_accepted: float
    quantity_rejected: float
    quantity_rework: float
    quantity_scrap: float


@dataclass(frozen=True)
class LotRow:
    """One ProductionLot with completed_at inside the requested period.
    `target_date` is resolved by the application layer (see
    _context.describe_lot_target_dates), this module only consumes it."""

    lot_id: int
    lot_number: str
    created: datetime
    completed_at: datetime | None
    target_date: date | None


@dataclass(frozen=True)
class CapacityRow:
    """One machine's available minutes for the requested period, from the
    existing calendar builder (build_machine_calendars), never SQL."""

    machine_id: int
    machine_internal_name: str
    available_minutes: int


@dataclass(frozen=True)
class DowntimeRow:
    machine_id: int
    minutes: int


@dataclass(frozen=True)
class WaitingRow:
    """One order started inside the requested period whose lot position
    has a predecessor position. `predecessor_ready` is None when neither
    an internal predecessor's actual_end nor an external predecessor's
    delivery date is known yet, such a row is excluded from the median,
    not treated as a zero wait."""

    order_id: int
    position_kind: str  # LotPositionKind of the STARTED order's own position
    actual_start: datetime
    predecessor_ready: date | None


@dataclass(frozen=True)
class ScrapReasonRow:
    """One scrapped-pieces event inside the requested period: a
    completion with quantity_scrap > 0, or a delivery rejection whose
    outcome is lost. `reason` is always present, an event recorded
    without a classified reason (a QA completion, where the reason stays
    optional) never reaches this row, see scrap_by_reason's docstring."""

    quantity: float
    reason: str


@dataclass(frozen=True)
class SupplierDeliveryRow:
    """One order item delivery record inside the requested period, with
    its line's supplier. `quantity` is the accepted portion of that
    event, `quantity_rejected` everything rejected in it regardless of
    outcome, `quantity_rejected_lost` the subset of that whose outcome
    was lost."""

    supplier_id: int
    supplier_name: str
    quantity: float
    quantity_rejected: float
    quantity_rejected_lost: float


# ══════════════════════════════════════════════════════════════════════
# Results
# ══════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class ThroughputResult:
    median_days: float | None
    p90_days: float | None
    count: int


@dataclass(frozen=True)
class UtilizationRow:
    """machine_id is None for the "manual" bucket: completed orders with
    no machine at all. Such a row has no calendar to divide by, so its
    ratio is always None."""

    machine_id: int | None
    machine_internal_name: str
    net_minutes: int
    ratio: Ratio


@dataclass(frozen=True)
class AvailabilityRow:
    machine_id: int
    machine_internal_name: str
    available_minutes: int
    downtime_minutes: int
    ratio: Ratio


@dataclass(frozen=True)
class EstimateAccuracyRow:
    fabrication_method_id: int
    fabrication_method_name: LocalizedText
    median_ratio: float | None
    count: int


@dataclass(frozen=True)
class WaitingTimeRow:
    position_kind: str
    median_days: float | None
    count: int


@dataclass(frozen=True)
class QualityByItemRow:
    made_item_id: int
    made_item_part_number: str
    made_item_article_name: str
    completed: float
    rejected: float
    rework: float
    scrap: float
    yield_ratio: Ratio


@dataclass(frozen=True)
class WeeklyKpiRow:
    iso_week: str  # "2026-W07"
    week_start: date  # that ISO week's Monday
    schedule_adherence: Ratio
    on_time_delivery: Ratio


@dataclass(frozen=True)
class ScrapByReasonRow:
    reason: str
    quantity: float
    share: Ratio  # quantity / total scrapped quantity across every reason


@dataclass(frozen=True)
class RejectedPerSupplierRow:
    supplier_id: int
    supplier_name: str
    delivered: float
    rejected: float
    rejected_ratio: Ratio  # rejected / (delivered + rejected)
    rejected_lost: float


# ══════════════════════════════════════════════════════════════════════
# Formulas
# ══════════════════════════════════════════════════════════════════════


def compute_schedule_adherence(orders: Sequence[CompletedOrderRow]) -> Ratio:
    """Completed orders with actual_end <= planned_end_at_start, over
    completed orders that have a baseline at all. An order started before
    the baseline existed (planned_end_at_start None) contributes to
    neither side."""
    with_baseline = [o for o in orders if o.planned_end_at_start is not None]
    on_time = [
        o
        for o in with_baseline
        if o.planned_end_at_start is not None and o.actual_end <= o.planned_end_at_start
    ]
    return _ratio(len(on_time), len(with_baseline))


def compute_on_time_delivery(lots: Sequence[LotRow], zone: tzinfo = UTC) -> Ratio:
    """Lots completed on or before their target date, over completed lots
    that have a target date at all. The completion counts on its day in
    `zone`, the tenant's timezone."""
    with_target = [
        lot for lot in lots if lot.target_date is not None and lot.completed_at is not None
    ]
    on_time = [
        lot
        for lot in with_target
        if lot.completed_at is not None
        and lot.target_date is not None
        and lot.completed_at.astimezone(zone).date() <= lot.target_date
    ]
    return _ratio(len(on_time), len(with_target))


def compute_throughput_time(lots: Sequence[LotRow]) -> ThroughputResult:
    """Median and p90 of completed_at - created, in days, over every
    completed lot in the period (a target date is not required here)."""
    days = [
        (lot.completed_at - lot.created).total_seconds() / 86400
        for lot in lots
        if lot.completed_at is not None
    ]
    return ThroughputResult(
        median_days=median(days), p90_days=percentile(days, 0.9), count=len(days)
    )


def compute_first_pass_yield(completions: Sequence[CompletionRow]) -> Ratio:
    total = sum(c.quantity for c in completions)
    accepted = sum(c.quantity_accepted for c in completions)
    return _ratio(accepted, total)


def compute_scrap_ratio(completions: Sequence[CompletionRow]) -> Ratio:
    total = sum(c.quantity for c in completions)
    scrap = sum(c.quantity_scrap for c in completions)
    return _ratio(scrap, total)


def compute_rework_ratio(completions: Sequence[CompletionRow]) -> Ratio:
    total = sum(c.quantity for c in completions)
    rework = sum(c.quantity_rework for c in completions)
    return _ratio(rework, total)


def compute_utilization(
    orders: Sequence[CompletedOrderRow], capacity: Sequence[CapacityRow]
) -> list[UtilizationRow]:
    """Net work minutes of completed orders overlapping the period, per
    machine, over that machine's available minutes. A machine present in
    `capacity` but with no completed orders still gets a 0-minute row (so
    the caller always sees every in-scope machine); a machine absent from
    `capacity` (e.g. archived mid-period) but present in `orders` still
    gets a row, with no denominator (ratio None). Orders with no machine
    at all are folded into one machine_id=None "manual" row, always
    present even when empty."""
    net_by_machine: dict[int | None, int] = {}
    for order in orders:
        minutes = _net_minutes(order)
        if minutes is None:
            continue
        net_by_machine[order.machine_id] = net_by_machine.get(order.machine_id, 0) + minutes

    rows: list[UtilizationRow] = []
    seen_machine_ids: set[int] = set()
    for cap in capacity:
        net = net_by_machine.get(cap.machine_id, 0)
        seen_machine_ids.add(cap.machine_id)
        rows.append(
            UtilizationRow(
                machine_id=cap.machine_id,
                machine_internal_name=cap.machine_internal_name,
                net_minutes=net,
                ratio=_ratio(net, cap.available_minutes),
            )
        )
    for machine_id, net in net_by_machine.items():
        if machine_id is None or machine_id in seen_machine_ids:
            continue
        rows.append(
            UtilizationRow(
                machine_id=machine_id,
                machine_internal_name="",
                net_minutes=net,
                ratio=_ratio(net, 0),
            )
        )
    manual_net = net_by_machine.get(None, 0)
    rows.append(
        UtilizationRow(
            machine_id=None,
            machine_internal_name="",
            net_minutes=manual_net,
            ratio=_ratio(manual_net, 0),
        )
    )
    return rows


def compute_availability(
    capacity: Sequence[CapacityRow], downtime: Sequence[DowntimeRow]
) -> list[AvailabilityRow]:
    """Available minutes minus downtime minutes overlapping the period,
    over available minutes, per machine in `capacity`."""
    downtime_by_machine = {d.machine_id: d.minutes for d in downtime}
    rows = []
    for cap in capacity:
        down = downtime_by_machine.get(cap.machine_id, 0)
        up_minutes = max(0, cap.available_minutes - down)
        rows.append(
            AvailabilityRow(
                machine_id=cap.machine_id,
                machine_internal_name=cap.machine_internal_name,
                available_minutes=cap.available_minutes,
                downtime_minutes=down,
                ratio=_ratio(up_minutes, cap.available_minutes),
            )
        )
    return rows


def compute_estimate_accuracy(orders: Sequence[CompletedOrderRow]) -> list[EstimateAccuracyRow]:
    """Median of net work minutes / estimated_duration_minutes, grouped by
    fabrication method, over completed orders with a positive estimate
    and a resolvable net work time. An order whose position has several
    fabrication-role steps contributes its one ratio to each of their
    methods."""
    ratios_by_method: dict[int, list[float]] = {}
    names_by_method: dict[int, LocalizedText] = {}
    for order in orders:
        minutes = _net_minutes(order)
        if minutes is None or order.estimated_duration_minutes <= 0:
            continue
        ratio_value = minutes / order.estimated_duration_minutes
        for method in order.fabrication_methods:
            ratios_by_method.setdefault(method.id, []).append(ratio_value)
            names_by_method[method.id] = method.name
    return [
        EstimateAccuracyRow(
            fabrication_method_id=method_id,
            fabrication_method_name=names_by_method[method_id],
            median_ratio=median(values),
            count=len(values),
        )
        for method_id, values in sorted(ratios_by_method.items())
    ]


def compute_waiting_time(rows: Sequence[WaitingRow], zone: tzinfo = UTC) -> list[WaitingTimeRow]:
    """Median days between a predecessor position becoming ready and this
    order's actual_start, grouped by the started order's own position
    kind. The start counts on its day in `zone`, the tenant's timezone. A
    row with no resolvable predecessor readiness is excluded."""
    days_by_kind: dict[str, list[float]] = {}
    for row in rows:
        if row.predecessor_ready is None:
            continue
        days = (row.actual_start.astimezone(zone).date() - row.predecessor_ready).days
        days_by_kind.setdefault(row.position_kind, []).append(float(days))
    return [
        WaitingTimeRow(position_kind=kind, median_days=median(values), count=len(values))
        for kind, values in sorted(days_by_kind.items())
    ]


def compute_quality_by_item(completions: Sequence[CompletionRow]) -> list[QualityByItemRow]:
    grouped: dict[int, list[CompletionRow]] = {}
    for completion in completions:
        grouped.setdefault(completion.made_item_id, []).append(completion)
    rows = []
    for made_item_id, items in sorted(grouped.items()):
        completed = sum(c.quantity for c in items)
        accepted = sum(c.quantity_accepted for c in items)
        rejected = sum(c.quantity_rejected for c in items)
        rework = sum(c.quantity_rework for c in items)
        scrap = sum(c.quantity_scrap for c in items)
        rows.append(
            QualityByItemRow(
                made_item_id=made_item_id,
                made_item_part_number=items[0].made_item_part_number,
                made_item_article_name=items[0].made_item_article_name,
                completed=completed,
                rejected=rejected,
                rework=rework,
                scrap=scrap,
                yield_ratio=_ratio(accepted, completed),
            )
        )
    return rows


def scrap_by_reason(rows: Sequence[ScrapReasonRow]) -> list[ScrapByReasonRow]:
    """Scrapped quantity grouped by reason, sorted descending (a Pareto
    ranking), each row carrying its share of the total scrapped quantity
    across every reason. Pieces scrapped during production and pieces
    lost at goods receipt are pooled into one ranking, since both are the
    same "left the lot without being delivered" event from the KPI's
    point of view, they only differ in where they happened."""
    totals: dict[str, float] = {}
    for row in rows:
        totals[row.reason] = totals.get(row.reason, 0.0) + row.quantity
    total = sum(totals.values())
    result = [
        ScrapByReasonRow(reason=reason, quantity=quantity, share=_ratio(quantity, total))
        for reason, quantity in totals.items()
    ]
    result.sort(key=lambda row: row.quantity, reverse=True)
    return result


def rejected_per_supplier(rows: Sequence[SupplierDeliveryRow]) -> list[RejectedPerSupplierRow]:
    """Delivered and rejected quantity per supplier, with the rejected
    ratio over everything received from that supplier (delivered plus
    rejected) and the subset of the rejected quantity whose outcome was
    lost for good. Sorted descending by the rejected ratio, a supplier
    with no ratio (nothing received at all in the period) sorts last."""
    delivered_by_supplier: dict[int, float] = {}
    rejected_by_supplier: dict[int, float] = {}
    rejected_lost_by_supplier: dict[int, float] = {}
    names: dict[int, str] = {}
    for row in rows:
        delivered_by_supplier[row.supplier_id] = (
            delivered_by_supplier.get(row.supplier_id, 0.0) + row.quantity
        )
        rejected_by_supplier[row.supplier_id] = (
            rejected_by_supplier.get(row.supplier_id, 0.0) + row.quantity_rejected
        )
        rejected_lost_by_supplier[row.supplier_id] = (
            rejected_lost_by_supplier.get(row.supplier_id, 0.0) + row.quantity_rejected_lost
        )
        names[row.supplier_id] = row.supplier_name

    result = []
    for supplier_id, name in names.items():
        delivered = delivered_by_supplier[supplier_id]
        rejected = rejected_by_supplier[supplier_id]
        result.append(
            RejectedPerSupplierRow(
                supplier_id=supplier_id,
                supplier_name=name,
                delivered=delivered,
                rejected=rejected,
                rejected_ratio=_ratio(rejected, delivered + rejected),
                rejected_lost=rejected_lost_by_supplier[supplier_id],
            )
        )
    result.sort(
        key=lambda row: (row.rejected_ratio.value is None, -(row.rejected_ratio.value or 0))
    )
    return result


def is_lot_late(
    effective_end: datetime | None, target_date: date | None, zone: tzinfo = UTC
) -> bool:
    """An open lot's projected finish (its latest order's actual_end when
    it already finished, else its planned_end) falling after the lot's
    target date, the finish read on its day in `zone`, the tenant's
    timezone. Neither value known yet means "not (yet) late", not an
    error."""
    return (
        effective_end is not None
        and target_date is not None
        and effective_end.astimezone(zone).date() > target_date
    )


def compute_performance(orders: Sequence[CompletedOrderRow]) -> Ratio:
    """OEE's performance factor: sum(estimated_duration_minutes) / sum(net
    work minutes) over completed orders with a resolvable net work time,
    capped at 1 (running faster than estimated never inflates OEE above
    what availability/quality alone would allow)."""
    total_estimated = 0
    total_net = 0
    for order in orders:
        minutes = _net_minutes(order)
        if minutes is None:
            continue
        total_estimated += order.estimated_duration_minutes
        total_net += minutes
    result = _ratio(total_estimated, total_net)
    if result.value is not None and result.value > 1:
        return Ratio(value=1.0, numerator=result.numerator, denominator=result.denominator)
    return result


def compute_oee(
    availability: Ratio, utilization: Ratio, yield_ratio: Ratio, performance: Ratio
) -> float | None:
    """Availability x performance x quality (first pass yield), shown only
    when availability, utilization and yield are all computable for the
    filter. Utilization itself does not multiply into the result; it is
    only a precondition that the filter has a machine-scoped, non-empty
    denominator to reason about at all."""
    if availability.value is None or utilization.value is None or yield_ratio.value is None:
        return None
    if performance.value is None:
        return None
    return availability.value * performance.value * yield_ratio.value


def _iso_week_key(d: date) -> str:
    iso = d.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def iso_weeks_in_period(date_from: date, date_to: date) -> list[tuple[str, date]]:
    """Every distinct ISO week [date_from, date_to] touches, oldest first,
    as (iso_week_key, that week's Monday)."""
    weeks: dict[str, date] = {}
    cursor = date_from
    while cursor <= date_to:
        key = _iso_week_key(cursor)
        weeks.setdefault(key, start_of_iso_week(cursor))
        cursor += timedelta(days=1)
    return sorted(weeks.items(), key=lambda entry: entry[1])


def compute_weekly_series(
    orders: Sequence[CompletedOrderRow],
    lots: Sequence[LotRow],
    date_from: date,
    date_to: date,
    zone: tzinfo = UTC,
) -> list[WeeklyKpiRow]:
    """Schedule adherence and on-time delivery, one point per ISO week
    inside [date_from, date_to], including weeks with no data (both
    ratios None then). An order or lot falls into the week of its day in
    `zone`, the tenant's timezone."""
    orders_by_week: dict[str, list[CompletedOrderRow]] = {}
    for order in orders:
        week = _iso_week_key(order.actual_end.astimezone(zone).date())
        orders_by_week.setdefault(week, []).append(order)
    lots_by_week: dict[str, list[LotRow]] = {}
    for lot in lots:
        if lot.completed_at is None:
            continue
        week = _iso_week_key(lot.completed_at.astimezone(zone).date())
        lots_by_week.setdefault(week, []).append(lot)

    return [
        WeeklyKpiRow(
            iso_week=key,
            week_start=week_start,
            schedule_adherence=compute_schedule_adherence(orders_by_week.get(key, [])),
            on_time_delivery=compute_on_time_delivery(lots_by_week.get(key, []), zone),
        )
        for key, week_start in iso_weeks_in_period(date_from, date_to)
    ]
