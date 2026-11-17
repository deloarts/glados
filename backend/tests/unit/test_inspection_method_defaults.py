"""
InspectionMethod.default_setup_minutes / default_minutes_per_piece: the
durations a QA step starts life with.

How long an inspection takes is a property of the method (a visual check
is seconds a piece, a CMM run is minutes plus real setup), not of the
project, which is why it lives here rather than in a project budget or a
single global number. Both are optional, seeded at creation only, and
always overridable per step.

No database, no HTTP.
"""

from datetime import UTC
from datetime import datetime

from src.modules.catalogue.domain.entities.inspection_method import InspectionMethod
from src.modules.catalogue.domain.policies.inspection_method_rules import seed_inspection_estimates


def make_method(
    setup: int | None = None,
    per_piece: float | None = None,
) -> InspectionMethod:
    return InspectionMethod(
        id=1,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        archived=False,
        name="Measurement",
        label_color="#999999",
        label_font_color="#000000",
        description="",
        creator_id=1,
        default_setup_minutes=setup,
        default_minutes_per_piece=per_piece,
        requires_evidence=True,
    )


class TestSeedInspectionEstimates:
    def test_takes_both_defaults_when_the_caller_supplied_neither(self):
        assert seed_inspection_estimates(make_method(10, 5.0), None, None) == (10, 5.0)

    def test_a_caller_supplied_value_wins_over_the_default(self):
        """The method seeds; it never overrides a deliberate estimate."""
        assert seed_inspection_estimates(make_method(10, 5.0), 3, 1.5) == (3, 1.5)

    def test_each_side_falls_back_independently(self):
        """Setup given, per-piece not: only the missing half is seeded."""
        assert seed_inspection_estimates(make_method(10, 5.0), 3, None) == (3, 5.0)
        assert seed_inspection_estimates(make_method(10, 5.0), None, 1.5) == (10, 1.5)

    def test_a_method_with_no_defaults_leaves_the_step_unestimated(self):
        """Which estimate_time_source then reports as "not_applicable"
        rather than flagging the order as missing an estimate forever."""
        assert seed_inspection_estimates(make_method(), None, None) == (None, None)

    def test_a_zero_default_is_a_real_value_not_a_missing_one(self):
        """0 minutes setup is a legitimate answer for a visual check and
        must not be treated as "unset" and replaced."""
        assert seed_inspection_estimates(make_method(10, 5.0), 0, 0.0) == (0, 0.0)
