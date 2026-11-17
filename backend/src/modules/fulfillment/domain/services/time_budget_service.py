"""
Apportions Project.production_time_budget (minutes of manufacturing time
sold to the customer, entered by hand) across the project's not-yet-
estimated INTERNAL/MIXED LotSteps, producing a stored, per-step fallback
(LotStep.time_budget_per_piece) for the scheduler to use in place of a
bare 0 before any real per-step estimates exist. A manual, low-tech
stand-in for a future statistical/ML TimeEstimationPort, once
assessment data exists, real estimates gradually crowd this fallback
out.

Pure, no I/O, mirrors lot_rules.py / production_order_rules.py's shape.
"""

from dataclasses import dataclass

from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind

# Positions whose steps draw from the shared time budget pool, EXTERNAL
# steps are excluded entirely (their cost/time is the supplier's concern,
# not internal capacity); UNASSIGNED positions have no ProductionOrder yet
# so there's nothing for the fallback to feed.
_ELIGIBLE_POSITION_KINDS = {LotPositionKind.INTERNAL, LotPositionKind.MIXED}


@dataclass(frozen=True)
class StepBudgetInput:
    """One LotStep's contribution to a project-wide apportionment pass,
    pre-fetched by the caller (position kind comes from the step's owning
    LotPosition, lot_quantity from its owning ProductionLot)."""

    step_id: int
    lot_quantity: float
    position_kind: str  # LotPositionKind
    estimated_minutes_per_piece: float | None


def is_eligible_for_budget(step: StepBudgetInput) -> bool:
    """Only steps still missing a real measured estimate, on an
    INTERNAL/MIXED position, draw from (or count toward) the shared pool."""
    return (
        step.position_kind in _ELIGIBLE_POSITION_KINDS and step.estimated_minutes_per_piece is None
    )


def apportion_time_budget(
    steps: list[StepBudgetInput], production_time_budget: int | None
) -> dict[int, float | None]:
    """Returns step_id -> time_budget_per_piece for every given step.

    pool = production_time_budget
    denominator = sum(lot_quantity) over eligible steps
    time_budget_per_piece = pool / denominator, identical for every
    eligible step regardless of which lot it belongs to.

    None on every step when there's no budget set or nothing left to
    apportion to (denominator is 0), callers then fall through to the
    plain 0 + MISSING_TIME_ESTIMATE scheduler behavior.
    """
    if production_time_budget is None:
        return {s.step_id: None for s in steps}

    eligible_ids = {s.step_id for s in steps if is_eligible_for_budget(s)}
    denominator = sum(s.lot_quantity for s in steps if s.step_id in eligible_ids)
    if denominator <= 0:
        return {s.step_id: None for s in steps}

    per_piece = production_time_budget / denominator
    return {s.step_id: (per_piece if s.step_id in eligible_ids else None) for s in steps}
