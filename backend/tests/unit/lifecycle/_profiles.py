"""
The Hypothesis settings of the rule-based lifecycle models. A model takes
its example count from the loaded profile (`dev` or `ci`, registered in
tests/conftest.py) instead of a fixed number, so `--hypothesis-profile ci`
reaches it, scaled by a weight that keeps the expensive models within the
CI time budget. The pytest plugin loads the profile before any test module
is imported, so `settings.default` here is the profile of the run.
"""

from hypothesis import HealthCheck
from hypothesis import settings

# The share of the profile's examples an expensive model runs: the lot model
# and the cross-aggregate model take about half a second per example.
EXPENSIVE = 0.6


def model_settings(*, steps: int, weight: float = 1.0) -> settings:
    """The settings of a rule-based model of `steps` steps per example that
    runs `weight` times the profile's example count, at least ten."""
    return settings(
        settings.default,
        max_examples=max(10, round(settings.default.max_examples * weight)),
        stateful_step_count=steps,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
