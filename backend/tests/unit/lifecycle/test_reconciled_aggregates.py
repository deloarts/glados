"""
RECONCILED_AGGREGATES may only hold aggregates whose derivations read
aggregates of the same set, since the reconciler derives a written aggregate
from inputs whose intents are kept. Lots and their positions read each other
and therefore join together; a demand joins after the lines and lots it
draws on. The integration suite's drift check reads the same set.
"""

import pytest

from src.modules.fulfillment.application.services import lifecycle_reconciler
from src.modules.fulfillment.application.services.lifecycle_reconciler import RECONCILED_AGGREGATES
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.services.lifecycle_reconciler import assert_reconcilable
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LIFECYCLE_INPUTS
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from tests.unit.fakes import FakeEventBus
from tests.unit.lifecycle.fake_world import FakeWorld


def test_the_reconciled_aggregates_are_closed_under_their_inputs() -> None:
    assert_reconcilable(RECONCILED_AGGREGATES)


def test_a_default_reconciler_writes_the_reconciled_aggregates() -> None:
    reconciler = LifecycleReconciler(FakeWorld().repositories, FakeEventBus())

    assert reconciler.aggregates == RECONCILED_AGGREGATES


def test_a_reconciler_reads_the_set_when_it_is_built(monkeypatch: pytest.MonkeyPatch) -> None:
    enabled = frozenset({LifecycleAggregate.ORDER_ITEMS})
    monkeypatch.setattr(lifecycle_reconciler, "RECONCILED_AGGREGATES", enabled)

    reconciler = LifecycleReconciler(FakeWorld().repositories, FakeEventBus())

    assert reconciler.aggregates == enabled


def test_every_aggregate_states_what_its_derivation_reads() -> None:
    assert set(LIFECYCLE_INPUTS) == set(LifecycleAggregate)
    assert LIFECYCLE_INPUTS[LifecycleAggregate.LOT_POSITIONS] >= {LifecycleAggregate.LOTS}
    assert LIFECYCLE_INPUTS[LifecycleAggregate.LOTS] == {LifecycleAggregate.LOT_POSITIONS}
