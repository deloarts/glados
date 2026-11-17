"""
Unit tests for time_budget_service.py: apportioning
Project.production_time_budget across a project's not-yet-estimated
INTERNAL/MIXED LotSteps. Pure functions only, no database, no HTTP.
"""

from src.modules.fulfillment.domain.services.time_budget_service import StepBudgetInput
from src.modules.fulfillment.domain.services.time_budget_service import apportion_time_budget
from src.modules.fulfillment.domain.services.time_budget_service import is_eligible_for_budget


def _step(step_id, lot_quantity, position_kind, estimated_minutes_per_piece=None):
    return StepBudgetInput(
        step_id=step_id,
        lot_quantity=lot_quantity,
        position_kind=position_kind,
        estimated_minutes_per_piece=estimated_minutes_per_piece,
    )


def test_no_budget_set_yields_none_for_every_step():
    steps = [
        _step(1, 10, "internal"),
        _step(2, 5, "internal"),
    ]
    result = apportion_time_budget(steps, production_time_budget=None)
    assert result == {1: None, 2: None}


def test_zero_denominator_yields_none_for_every_step():
    # Only step is EXTERNAL (excluded) or already measured -> nothing eligible.
    steps = [
        _step(1, 10, "external"),
        _step(2, 5, "internal", estimated_minutes_per_piece=12.0),
    ]
    result = apportion_time_budget(steps, production_time_budget=1000)
    assert result == {1: None, 2: None}


def test_budget_apportioned_evenly_across_eligible_steps_by_quantity():
    steps = [
        _step(1, 10, "internal"),
        _step(2, 5, "mixed"),
        # Already measured -> excluded from both numerator and denominator.
        _step(3, 20, "internal", estimated_minutes_per_piece=7.0),
        # EXTERNAL -> excluded regardless of estimate.
        _step(4, 20, "external"),
    ]
    result = apportion_time_budget(steps, production_time_budget=1500)
    # denominator = 10 (step 1) + 5 (step 2) = 15 -> 1500/15 = 100 per piece
    assert result[1] == 100.0
    assert result[2] == 100.0
    assert result[3] is None
    assert result[4] is None


def test_is_eligible_for_budget_excludes_measured_and_external():
    measured = _step(1, 1, "internal", estimated_minutes_per_piece=5.0)
    external = _step(2, 1, "external")
    eligible_internal = _step(3, 1, "internal")
    eligible_mixed = _step(4, 1, "mixed")
    unassigned = _step(5, 1, "unassigned")

    assert not is_eligible_for_budget(measured)
    assert not is_eligible_for_budget(external)
    assert is_eligible_for_budget(eligible_internal)
    assert is_eligible_for_budget(eligible_mixed)
    assert not is_eligible_for_budget(unassigned)
