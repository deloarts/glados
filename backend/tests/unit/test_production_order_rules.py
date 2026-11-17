"""
Direct characterization tests for
src/modules/fulfillment/domain/services/production_order_rules.py's estimate_time_source.
"""

from datetime import datetime

from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.services.production_order_rules import estimate_time_source


def make_step(
    id: int = 1,
    role: StepRole = StepRole.FABRICATION,
    estimated_minutes_per_piece: float | None = None,
    time_budget_per_piece: float | None = None,
) -> LotStep:
    return LotStep(
        id=id,
        created=datetime(2026, 1, 1),
        note=None,
        estimated_setup_minutes=None,
        estimated_minutes_per_piece=estimated_minutes_per_piece,
        sequence=id,
        creator_id=1,
        fabrication_method_id=None if role == StepRole.INSPECTION.value else 1,
        lot_id=1,
        position_id=1,
        source_process_id=None,
        role=role,
        inspection_method_id=1 if role == StepRole.INSPECTION.value else None,
        time_budget_per_piece=time_budget_per_piece,
    )


class TestEstimateTimeSource:
    """estimate_time_source's inspection special-case: a
    "missing"-estimate inspection step is excluded from the verdict
    rather than dragging the whole order down to "missing" forever; QA
    isn't apportioned a project time budget, so it would never resolve
    otherwise. A fabrication step with no estimate still dominates as
    before."""

    def test_no_steps_is_missing(self):
        assert estimate_time_source([]) == "missing"

    def test_single_fabrication_step_with_estimate_is_measured(self):
        step = make_step(estimated_minutes_per_piece=5.0)
        assert estimate_time_source([step]) == "measured"

    def test_single_fabrication_step_without_estimate_is_missing(self):
        step = make_step()
        assert estimate_time_source([step]) == "missing"

    def test_inspection_only_step_without_estimate_is_not_applicable(self):
        step = make_step(role=StepRole.INSPECTION)
        assert estimate_time_source([step]) == "not_applicable"

    def test_multiple_inspection_steps_without_estimates_are_not_applicable(self):
        steps = [
            make_step(id=1, role=StepRole.INSPECTION),
            make_step(id=2, role=StepRole.INSPECTION),
        ]
        assert estimate_time_source(steps) == "not_applicable"

    def test_inspection_step_with_a_real_estimate_counts_as_measured(self):
        step = make_step(role=StepRole.INSPECTION, estimated_minutes_per_piece=3.0)
        assert estimate_time_source([step]) == "measured"

    def test_inspection_step_with_a_budget_fallback_counts_as_budget(self):
        step = make_step(role=StepRole.INSPECTION, time_budget_per_piece=2.0)
        assert estimate_time_source([step]) == "budget"

    def test_missing_fabrication_step_beside_missing_inspection_step_is_still_missing(self):
        steps = [
            make_step(id=1, role=StepRole.FABRICATION),
            make_step(id=2, role=StepRole.INSPECTION),
        ]
        assert estimate_time_source(steps) == "missing"

    def test_measured_fabrication_step_beside_missing_inspection_step_is_measured(self):
        steps = [
            make_step(id=1, role=StepRole.FABRICATION, estimated_minutes_per_piece=4.0),
            make_step(id=2, role=StepRole.INSPECTION),
        ]
        assert estimate_time_source(steps) == "measured"
