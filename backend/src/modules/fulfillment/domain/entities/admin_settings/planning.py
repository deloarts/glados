"""Domain entity for the planning settings singleton: how far ahead the
committed horizon reaches, how long recorded plans are kept, and from when
the booking quality view counts bookings."""

from dataclasses import dataclass
from datetime import datetime

from src.shared_kernel.domain.entities.base import Entity

# The committed horizon in working days. A week is the default; more than a
# month would commit work nobody can foresee.
DEFAULT_COMMIT_HORIZON_WORKING_DAYS = 5
MAX_COMMIT_HORIZON_WORKING_DAYS = 20

# How long recorded plans, the nightly baseline among them, are kept. A
# year and a bit keeps one full year of daily adherence comparable.
DEFAULT_PLAN_RETENTION_DAYS = 400
MIN_PLAN_RETENTION_DAYS = 30
MAX_PLAN_RETENTION_DAYS = 3650


@dataclass
class AdminPlanningSettings(Entity):
    """Settings of the planning features that work next to the scheduler:
    the nightly baseline, its retention and the booking quality view."""

    # Working days from today the baseline records, and later the horizon a
    # planner commits.
    commit_horizon_working_days: int
    # Recorded plans whose plan day is older than this many days are purged.
    plan_retention_days: int
    # The booking quality view counts bookings from this moment on, so
    # pauses booked before a cause could be picked are not counted as
    # missing one.
    booking_quality_since: datetime
