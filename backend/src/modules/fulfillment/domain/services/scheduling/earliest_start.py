"""Earliest-start resolution from predecessor, material and not-before dates.

Each resolver reduces the dates of one kind of upstream signal to a single
calendar day of the tenant's timezone, ignoring unknown dates, and
compute_earliest_start takes the latest of them.
"""

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


def resolve_external_predecessor_ready_at(
    delivery_date: date | datetime | None,
    ready_for_pickup_date: date | datetime | None,
    expected_delivery_date: date | None,
    *,
    zone: tzinfo,
) -> date | None:
    """An actual delivery always wins over estimates, then the
    ready-for-pickup event, then the expected delivery date. The two events
    are moments and count on their day in `zone`."""
    return (
        as_day(delivery_date, zone)
        or as_day(ready_for_pickup_date, zone)
        or as_day(expected_delivery_date, zone)
    )


def resolve_mixed_predecessor_ready_at(
    external_ready_at: date | None, internal_ready_at: date | None
) -> date | None:
    """A MIXED position is ready when both its external and internal
    shares are, so this takes the later known date."""
    candidates = [d for d in (external_ready_at, internal_ready_at) if d is not None]
    return max(candidates) if candidates else None


def resolve_input_material_ready_at(
    delivery_dates: list[date | datetime | None], *, zone: tzinfo
) -> date | None:
    """Position 1 needs every allocation covering the lot's input demand,
    so its material is ready on the latest known day. A line that arrived
    gives its delivery, a moment, and one still on order its expected day,
    so each is reduced to its day in `zone` before they are compared."""
    known = [day for d in delivery_dates if (day := as_day(d, zone)) is not None]
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
