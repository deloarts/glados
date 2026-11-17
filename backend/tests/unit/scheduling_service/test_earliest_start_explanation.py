"""
Unit tests for explain_earliest_start and resolve_position_lead_days_with_source,
two pure read-model derivations on top of the existing scheduling
context/lead-day machinery. Builds OrderSchedulingContext values directly
via the shared make_context factory, no database, no application layer.
"""

from datetime import UTC
from datetime import date
from datetime import datetime

from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.services.scheduling import EarliestStartExplanation
from src.modules.fulfillment.domain.services.scheduling import explain_earliest_start
from src.modules.fulfillment.domain.services.scheduling import resolve_position_lead_days
from src.modules.fulfillment.domain.services.scheduling import (
    resolve_position_lead_days_with_source,
)
from tests.unit.scheduling_service._helpers import MONDAY
from tests.unit.scheduling_service._helpers import TUESDAY
from tests.unit.scheduling_service._helpers import make_context

WEDNESDAY = date(2026, 7, 29)
THURSDAY = date(2026, 7, 30)


def _step(
    role: StepRole = StepRole.FABRICATION,
    fabrication_method_lead_time_days: int | None = None,
) -> LotStep:
    """A minimal LotStep. Only role and fabrication_method_lead_time_days
    matter to resolve_position_lead_days_with_source, every other field is
    a placeholder."""
    return LotStep(
        id=0,
        created=date(2026, 1, 1),
        note=None,
        estimated_setup_minutes=None,
        estimated_minutes_per_piece=None,
        sequence=1,
        creator_id=1,
        fabrication_method_id=1 if role == StepRole.FABRICATION.value else None,
        lot_id=1,
        position_id=1,
        source_process_id=None,
        role=role,
        inspection_method_id=2 if role == StepRole.INSPECTION.value else None,
        fabrication_method_lead_time_days=fabrication_method_lead_time_days,
    )


def test_in_progress_reason_uses_actual_start_regardless_of_everything_else():
    ctx = make_context(actual_start=datetime(2026, 7, 27, 9, 0), pinned=False, not_before=THURSDAY)
    assert explain_earliest_start(ctx) == EarliestStartExplanation("in_progress", MONDAY)


def test_pinned_reason_uses_existing_planned_start():
    ctx = make_context(
        pinned=True,
        existing_planned_start=datetime(2026, 7, 28, 8, 0),
        existing_planned_end=datetime(2026, 7, 28, 9, 0),
    )
    assert explain_earliest_start(ctx) == EarliestStartExplanation("pinned", TUESDAY)


def test_pinned_without_an_existing_window_falls_through_to_the_normal_rules():
    """Pinned alone isn't enough: advance_machine_queue only honours the
    pin once a window already exists (a never-scheduled pinned order still
    needs placing)."""
    ctx = make_context(pinned=True, not_before=WEDNESDAY)
    assert explain_earliest_start(ctx) == EarliestStartExplanation("not_before", WEDNESDAY)


def test_unknown_chain_reason():
    ctx = make_context(
        position_sequence=2,
        predecessor_chain_unknown=True,
        upstream_input_available=False,
    )
    assert explain_earliest_start(ctx) == EarliestStartExplanation("unknown_chain", None)


def test_unknown_chain_does_not_apply_when_upstream_input_is_already_available():
    """A partial delivery already sitting at this step makes today an
    honest forecast even though the rest of the chain is unknowable,
    mirrors advance_machine_queue's own upstream_input_available escape
    hatch."""
    ctx = make_context(
        position_sequence=2,
        predecessor_chain_unknown=True,
        upstream_input_available=True,
    )
    assert explain_earliest_start(ctx) == EarliestStartExplanation("none", None)


def test_missing_material_reason():
    ctx = make_context(
        position_sequence=1,
        upstream_input_available=False,
        material_ready_at=None,
    )
    assert explain_earliest_start(ctx) == EarliestStartExplanation("missing_material", None)


def test_not_before_reason():
    ctx = make_context(not_before=WEDNESDAY)
    assert explain_earliest_start(ctx) == EarliestStartExplanation("not_before", WEDNESDAY)


def test_predecessor_reason():
    ctx = make_context(position_sequence=2, predecessor_ready_at=WEDNESDAY)
    assert explain_earliest_start(ctx) == EarliestStartExplanation("predecessor", WEDNESDAY)


def test_material_reason():
    ctx = make_context(position_sequence=1, material_ready_at=THURSDAY)
    assert explain_earliest_start(ctx) == EarliestStartExplanation("material", THURSDAY)


def test_queue_reason_when_the_machine_queue_pushed_the_start_later():
    ctx = make_context(
        not_before=MONDAY,
        existing_planned_start=datetime(2026, 7, 30, 8, 0),
        existing_planned_end=datetime(2026, 7, 30, 9, 0),
    )
    assert explain_earliest_start(ctx) == EarliestStartExplanation("queue", MONDAY)


def test_none_reason_when_nothing_constrains_the_order():
    ctx = make_context()
    assert explain_earliest_start(ctx) == EarliestStartExplanation("none", None)


def test_not_before_wins_a_tie_against_predecessor_ready_at():
    ctx = make_context(position_sequence=2, not_before=WEDNESDAY, predecessor_ready_at=WEDNESDAY)
    assert explain_earliest_start(ctx) == EarliestStartExplanation("not_before", WEDNESDAY)


def test_lead_days_supplier_override_wins_regardless_of_steps():
    days, source = resolve_position_lead_days_with_source(
        [_step(fabrication_method_lead_time_days=1)],
        supplier_override=5,
        default_external_lead_days=2,
    )
    assert (days, source) == (5, "supplier")


def test_lead_days_sums_fabrication_method_lead_times():
    steps = [_step(fabrication_method_lead_time_days=2), _step(fabrication_method_lead_time_days=3)]
    days, source = resolve_position_lead_days_with_source(
        steps, supplier_override=None, default_external_lead_days=1
    )
    assert (days, source) == (5, "method")


def test_lead_days_inspection_step_contributes_nothing():
    steps = [
        _step(role=StepRole.INSPECTION, fabrication_method_lead_time_days=99),
        _step(fabrication_method_lead_time_days=4),
    ]
    days, source = resolve_position_lead_days_with_source(
        steps, supplier_override=None, default_external_lead_days=1
    )
    assert (days, source) == (4, "method")


def test_lead_days_falls_back_to_admin_default_per_step_without_its_own_value():
    steps = [_step(), _step()]
    days, source = resolve_position_lead_days_with_source(
        steps, supplier_override=None, default_external_lead_days=3
    )
    assert (days, source) == (6, "default")


def test_lead_days_mixed_steps_report_method_source_even_if_one_step_fell_back():
    steps = [_step(fabrication_method_lead_time_days=2), _step()]
    days, source = resolve_position_lead_days_with_source(
        steps, supplier_override=None, default_external_lead_days=3
    )
    assert (days, source) == (5, "method")


def test_lead_days_no_steps_at_all_is_zero_default():
    days, source = resolve_position_lead_days_with_source(
        [], supplier_override=None, default_external_lead_days=3
    )
    assert (days, source) == (0, "default")


def test_resolve_position_lead_days_wrapper_matches_the_days_from_with_source():
    steps = [_step(fabrication_method_lead_time_days=2), _step()]
    assert resolve_position_lead_days(steps, None, 3) == 5


def test_material_delivered_timestamp_is_reduced_to_its_day() -> None:
    """An actual delivery contributes a full timestamp as material_ready_at.
    The explanation must still compare and report calendar days."""
    delivered = datetime(2026, 7, 28, 9, 55, tzinfo=UTC)
    ctx = make_context(material_ready_at=delivered, existing_planned_start=None)
    assert explain_earliest_start(ctx) == EarliestStartExplanation("material", TUESDAY)


def test_queue_push_is_detected_against_a_delivered_timestamp() -> None:
    delivered = datetime(2026, 7, 28, 9, 55, tzinfo=UTC)
    ctx = make_context(
        material_ready_at=delivered,
        existing_planned_start=datetime(2026, 7, 29, 8, 0, tzinfo=UTC),
    )
    assert explain_earliest_start(ctx) == EarliestStartExplanation("queue", TUESDAY)
