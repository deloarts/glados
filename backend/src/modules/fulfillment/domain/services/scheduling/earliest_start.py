"""Earliest-start resolution from predecessor, material and not-before dates.

Each resolver reduces the dates of one kind of upstream signal to a single
calendar day of the tenant's timezone, ignoring unknown dates, and
compute_earliest_start takes the latest of them. An expected arrival day
that has passed without the arrival counts as today, since the pieces can
arrive no earlier, so a late delivery pushes the steps after it.
"""

from collections.abc import Iterable
from datetime import date
from datetime import datetime
from datetime import tzinfo

from src.modules.fulfillment.domain.services.scheduling._shared import as_day
from src.modules.fulfillment.domain.services.scheduling._shared import day_of


def resolve_internal_predecessor_ready_at(
    planned_ends: list[datetime | None], *, zone: tzinfo
) -> date | None:
    """The day in `zone` of the latest planned_end over the predecessor
    position's orders. Partial quantities are not tracked, and undated
    orders are ignored, so a position with no dated order contributes no
    constraint."""
    known = [day_of(d, zone) for d in planned_ends if d is not None]
    return max(known) if known else None


def expected_arrival_day(expected: date | None, today: date) -> date | None:
    """The day an arrival that has not happened yet can be counted on: its
    expected day, or today once that day has passed."""
    if expected is None:
        return None
    return max(expected, today)


def resolve_external_predecessor_ready_at(
    delivery_date: date | datetime | None,
    ready_for_pickup_date: date | datetime | None,
    expected_delivery_date: date | None,
    *,
    zone: tzinfo,
    today: date,
) -> date | None:
    """An actual delivery always wins over estimates, then the
    ready-for-pickup event, then the expected delivery date, which counts
    as today once it has passed. The two events are moments and count on
    their day in `zone`, and `today` is a day of `zone` too."""
    return (
        as_day(delivery_date, zone)
        or as_day(ready_for_pickup_date, zone)
        or expected_arrival_day(expected_delivery_date, today)
    )


def resolve_mixed_predecessor_ready_at(
    external_ready_at: date | None, internal_ready_at: date | None
) -> date | None:
    """A MIXED position is ready when both its external and internal
    shares are, so this takes the later known date."""
    candidates = [d for d in (external_ready_at, internal_ready_at) if d is not None]
    return max(candidates) if candidates else None


def resolve_input_material_ready_at(
    lines: Iterable[tuple[date | datetime | None, date | None]], *, zone: tzinfo, today: date
) -> date | None:
    """Position 1 needs every allocation covering the lot's input demand,
    so its material is ready on the latest known day. Each line is its
    delivery and its expected day. A line that arrived gives its delivery,
    a moment reduced to its day in `zone`, and one still on order its
    expected day, or today once that day has passed."""
    known = [
        day
        for delivered, expected in lines
        if (
            day := as_day(delivered, zone)
            if delivered is not None
            else expected_arrival_day(expected, today)
        )
        is not None
    ]
    return max(known) if known else None


def compute_earliest_start(
    not_before: date | None,
    predecessor_ready_at: date | None,
    material_ready_at: date | None,
) -> date | None:
    """The latest of the known days. The resolvers above already reduced
    every moment to a tenant day, so all three are plain dates."""
    candidates = [d for d in (not_before, predecessor_ready_at, material_ready_at) if d is not None]
    return max(candidates) if candidates else None
