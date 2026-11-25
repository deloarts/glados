"""Domain entity for the production and scheduling settings singleton."""

from dataclasses import dataclass

from src.modules.fulfillment.domain.value_objects.work_interval import DayHours
from src.shared_kernel.domain.entities.base import Entity

# A frozen window of a month at most; a longer one would stop the schedule
# from following any change.
MAX_FROZEN_WINDOW_HOURS = 24 * 31


@dataclass
class AdminProductionSettings(Entity):
    """Settings for machines, production orders and scheduling.

    default_weekly_hours maps weekday (0 is Monday) to that day's working
    intervals, local to the tenant (value_objects/work_interval.py), and is
    the calendar for every machine without its own working hours.
    """

    production_order_number_format: str  # e.g. "PON-{yy}-{seq:05d}"; {seq} must be the last token
    default_weekly_hours: dict[int, DayHours]
    default_external_lead_days: int  # backward-pass lead time assumed for EXTERNAL successors
    # Days added to a predecessor's or the raw material's ready date before
    # it gates the next step, because finishing today does not mean the next
    # step starts today. Never applied to a manual not_before.
    response_time_days: int
    # New lots get a trailing inspection step unless the routing already ends
    # with one; it can be deleted afterwards.
    require_qa: bool
    # Lots sourced from a source item start with a pending approval instead
    # of an immediate demand. Toggling it backfills existing lots.
    require_source_item_approval: bool = False
    # Approving a source also makes it the made item's default material;
    # a bought-item source on the made item is never touched.
    assign_approved_material_to_item: bool = False
    # Whether that write-back may replace a different source item already
    # set on the made item; an empty slot is always filled.
    overwrite_item_material_on_approval: bool = False
    # A supplier who does a lot's first position brings the material, so such
    # a lot gets no raw material demand and needs no approval
    # (lot_material_rules.py). Off, every lot with a material source demands
    # its material whoever does position 1.
    external_first_step_needs_no_material: bool = True
    # Required while require_qa is on, so QA is never skipped for want of
    # a configured method.
    default_inspection_method_id: int | None = None
    # A schedule walk keeps the window of a queued order whose planned start
    # lies within this many hours from now, so the shop floor's next hours
    # do not shift under it; 0 freezes nothing.
    frozen_window_hours: int = 0
    # Days kept free before a lot's target date when the latest send-out day
    # of its external work is counted back, since that count assumes no
    # waiting at the machines.
    external_safety_margin_days: int = 2
