"""
The Hypothesis profiles of tests/conftest.py and the model settings built
on them: `dev` keeps Hypothesis' defaults at 100 examples, `ci` runs 400
derandomized examples without a database or a deadline, and a model's
example count follows the loaded profile scaled by its weight.
"""

from hypothesis import HealthCheck
from hypothesis import settings

from tests.unit.lifecycle._profiles import EXPENSIVE
from tests.unit.lifecycle._profiles import model_settings


def test_the_dev_profile_runs_a_hundred_random_examples() -> None:
    dev = settings.get_profile("dev")
    assert dev.max_examples == 100
    assert dev.derandomize is False


def test_the_ci_profile_runs_four_hundred_reproducible_examples() -> None:
    ci = settings.get_profile("ci")
    assert ci.max_examples == 400
    assert ci.derandomize is True
    assert ci.database is None
    assert ci.deadline is None
    assert ci.print_blob is True
    assert HealthCheck.too_slow in ci.suppress_health_check


def test_a_model_takes_its_example_count_from_the_loaded_profile() -> None:
    loaded = settings.default.max_examples
    full = model_settings(steps=30)
    assert full.max_examples == loaded
    assert full.stateful_step_count == 30
    assert full.deadline is None


def test_an_expensive_model_runs_its_weighted_share() -> None:
    weighted = model_settings(steps=40, weight=EXPENSIVE)
    assert weighted.max_examples == max(10, round(settings.default.max_examples * EXPENSIVE))
    assert model_settings(steps=1, weight=0.001).max_examples == 10
