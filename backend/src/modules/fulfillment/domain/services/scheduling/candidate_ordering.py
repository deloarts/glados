"""Auto-Plan's due-date backward pass and the ordering of its candidates.

Each OrderingStrategy is one sort over AutoPlanCandidate; AutoPlanAlgorithm
is the user-facing name, mapped onto an ordering and a selection strategy by
machine_selection.resolve_algorithm_strategies.
"""

from dataclasses import dataclass
from datetime import date
from datetime import datetime
from datetime import timedelta
from datetime import tzinfo
from enum import Enum

from src.shared_kernel.domain.services.clock import as_utc

# Converts estimated minutes into rough days for the backward pass only.
_MINUTES_PER_WORKDAY = 480


def position_lead_days(
    kind: str, total_estimated_minutes: int, default_external_lead_days: int
) -> int:
    if kind == "external":
        return default_external_lead_days
    return max(1, -(-total_estimated_minutes // _MINUTES_PER_WORKDAY))  # ceil division


def compute_position_due_dates(
    position_sequences: list[int],
    lead_days_by_sequence: dict[int, int],
    lot_target_date: date | None,
) -> dict[int, date | None]:
    """Backward pass: the last position is due at the lot's target, each
    earlier one when its successor must start. Without a target every
    position is None."""
    if lot_target_date is None:
        return dict.fromkeys(position_sequences)
    due: dict[int, date | None] = {}
    next_due = lot_target_date
    for sequence in sorted(position_sequences, reverse=True):
        due[sequence] = next_due
        next_due = next_due - timedelta(days=lead_days_by_sequence.get(sequence, 0))
    return due


@dataclass(frozen=True)
class AutoPlanCandidate:
    """One QUEUED, unpinned ProductionOrder eligible for auto-planning."""

    order_id: int
    urgency_rank: int  # UrgencyClass as an int, higher = more urgent
    position_due_date: date | None
    created_order: int  # a stable tiebreaker (e.g. order id or creation timestamp ordinal)
    estimated_duration_minutes: int  # used by the SPT/Critical Ratio orderings only
    # The candidate's lot and its position's sequence there, so the orders of
    # one lot are placed in chain order (keep_chain_order).
    lot_id: int | None = None
    position_sequence: int = 0


class OrderingStrategy(str, Enum):
    """Internal candidate ordering; AutoPlanAlgorithm is the user-facing
    name that resolve_algorithm_strategies maps onto it."""

    PRIORITY_EDD = "priority_edd"
    EDD = "edd"
    FIFO = "fifo"
    CRITICAL_RATIO = "critical_ratio"
    SPT = "spt"


def sort_candidates_by_priority(candidates: list[AutoPlanCandidate]) -> list[AutoPlanCandidate]:
    """Urgency first, then due date (missing dates last), then creation.
    The default URGENT_FIRST algorithm."""
    return sorted(
        candidates,
        key=lambda c: (
            -c.urgency_rank,
            c.position_due_date is None,
            c.position_due_date or date.max,
            c.created_order,
        ),
    )


def sort_candidates_by_edd(candidates: list[AutoPlanCandidate]) -> list[AutoPlanCandidate]:
    """Earliest due date, ignoring urgency (STRICT_DEADLINE). Minimizes
    worst-case lateness."""
    return sorted(
        candidates,
        key=lambda c: (
            c.position_due_date is None,
            c.position_due_date or date.max,
            c.created_order,
        ),
    )


def sort_candidates_by_fifo(candidates: list[AutoPlanCandidate]) -> list[AutoPlanCandidate]:
    """Creation order only (FAIR_QUEUE)."""
    return sorted(candidates, key=lambda c: c.created_order)


def sort_candidates_by_spt(candidates: list[AutoPlanCandidate]) -> list[AutoPlanCandidate]:
    """Shortest processing time first (SHORTEST_PROCESSING_TIME). Maximizes
    throughput but can starve long jobs."""
    return sorted(candidates, key=lambda c: (c.estimated_duration_minutes, c.created_order))


def sort_candidates_by_critical_ratio(
    candidates: list[AutoPlanCandidate], today: date
) -> list[AutoPlanCandidate]:
    """Days until due divided by duration in days, lowest first
    (CRITICAL_RATIO). `today` is the current day in the tenant's timezone,
    the one due dates are days of. Candidates without a due date sort last,
    and the duration is floored to avoid division by zero."""

    def ratio(c: AutoPlanCandidate) -> float:
        if c.position_due_date is None:
            return float("inf")
        days_until_due = (c.position_due_date - today).days
        duration_days = max(
            c.estimated_duration_minutes / _MINUTES_PER_WORKDAY, 1 / _MINUTES_PER_WORKDAY
        )
        return days_until_due / duration_days

    return sorted(candidates, key=lambda c: (ratio(c), c.created_order))


def keep_chain_order(candidates: list[AutoPlanCandidate]) -> list[AutoPlanCandidate]:
    """The candidates with the orders of each lot in position order within
    the slots that lot holds. Auto-Plan appends to queues in candidate
    order, so a later step placed before its predecessor on one machine
    would wait on an order queued behind it, a cycle the walk cannot date.
    Every other candidate keeps its slot."""
    slots_by_lot: dict[int, list[int]] = {}
    for index, candidate in enumerate(candidates):
        if candidate.lot_id is not None:
            slots_by_lot.setdefault(candidate.lot_id, []).append(index)
    ordered = list(candidates)
    for slots in slots_by_lot.values():
        in_chain_order = sorted(slots, key=lambda i: (candidates[i].position_sequence, i))
        for slot, index in zip(slots, in_chain_order, strict=True):
            ordered[slot] = candidates[index]
    return ordered


def sort_candidates(
    candidates: list[AutoPlanCandidate], strategy: str, today: date
) -> list[AutoPlanCandidate]:
    """Dispatches on an OrderingStrategy value, falling back to
    PRIORITY_EDD for unknown values, and keeps each lot in chain order."""
    return keep_chain_order(_sorted_by_strategy(candidates, strategy, today))


def _sorted_by_strategy(
    candidates: list[AutoPlanCandidate], strategy: str, today: date
) -> list[AutoPlanCandidate]:
    if strategy == OrderingStrategy.EDD.value:
        return sort_candidates_by_edd(candidates)
    if strategy == OrderingStrategy.FIFO.value:
        return sort_candidates_by_fifo(candidates)
    if strategy == OrderingStrategy.SPT.value:
        return sort_candidates_by_spt(candidates)
    if strategy == OrderingStrategy.CRITICAL_RATIO.value:
        return sort_candidates_by_critical_ratio(candidates, today)
    return sort_candidates_by_priority(candidates)


def production_order_touches_date(
    planned_start: datetime | None,
    planned_end: datetime | None,
    target_date: date,
    *,
    zone: tzinfo,
) -> bool:
    """True when the planned window overlaps target_date, a calendar day in
    `zone`. The stored UTC start and end are converted to `zone` before
    their days are taken, so a window from 23:30 to 00:30 local time touches
    both local days. A naive value is read as UTC. Auto-Plan passes the
    tenant's default timezone and the tenant-local today, to leave today's
    planned orders alone so a worker's queue does not change mid-day."""
    if planned_start is None or planned_end is None:
        return False
    start_day = as_utc(planned_start).astimezone(zone).date()
    end_day = as_utc(planned_end).astimezone(zone).date()
    return start_day <= target_date <= end_day
