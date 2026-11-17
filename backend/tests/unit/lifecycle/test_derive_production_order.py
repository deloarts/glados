"""Table tests for the production order status derivation
(src/modules/fulfillment/domain/services/lifecycle/production_order.py): one or more cases per
row, then every fact combination of a small domain against a transcription
of the target table."""

from dataclasses import replace

import pytest

from src.modules.fulfillment.domain.services.lifecycle.facts import ProductionOrderFacts
from src.modules.fulfillment.domain.services.lifecycle.production_order import (
    PRODUCTION_ORDER_STATUS,
)
from src.modules.fulfillment.domain.services.lifecycle.production_order import (
    derive_production_order_status,
)
from src.modules.fulfillment.domain.value_objects.interruption_reason import InterruptionReason
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from tests.unit.lifecycle.small_domains import T0
from tests.unit.lifecycle.small_domains import production_order_facts

EPS = 1e-6

_QUEUED_ORDER = ProductionOrderFacts(
    quantity=10.0, processed=0.0, actual_start=None, canceled_at=None, open_interruption=None
)


def _facts(**changes: object) -> ProductionOrderFacts:
    return replace(_QUEUED_ORDER, **changes)


@pytest.mark.parametrize(
    ("facts", "status", "row"),
    [
        (
            _facts(canceled_at=T0, processed=10.0, actual_start=T0),
            ProductionOrderStatus.CANCELED,
            1,
        ),
        (_facts(processed=10.0, actual_start=T0), ProductionOrderStatus.COMPLETED, 2),
        (
            _facts(quantity=1.0, processed=0.7 + 0.2 + 0.1, actual_start=T0),
            ProductionOrderStatus.COMPLETED,
            2,
        ),
        (
            _facts(processed=10.0, actual_start=T0, open_interruption=InterruptionReason.MANUAL),
            ProductionOrderStatus.COMPLETED,
            2,
        ),
        (_facts(), ProductionOrderStatus.QUEUED, 3),
        (_facts(quantity=0.0), ProductionOrderStatus.QUEUED, 3),
        (
            _facts(actual_start=T0, processed=4.0, open_interruption=InterruptionReason.MANUAL),
            ProductionOrderStatus.PAUSED,
            4,
        ),
        (
            _facts(actual_start=T0, open_interruption=InterruptionReason.LOT_HOLD),
            ProductionOrderStatus.PAUSED,
            4,
        ),
        (_facts(actual_start=T0, processed=4.0), ProductionOrderStatus.IN_PROGRESS, 5),
        (_facts(actual_start=T0, quantity=0.0), ProductionOrderStatus.IN_PROGRESS, 5),
    ],
)
def test_derive_production_order_status_rows(facts, status, row):
    derivation = derive_production_order_status(facts)
    assert (derivation.value, derivation.rule) == (status, row)


def _transcribed(f: ProductionOrderFacts) -> tuple[ProductionOrderStatus, int]:
    """The target table, written out independently of the module."""
    if f.canceled_at is not None:
        return ProductionOrderStatus.CANCELED, 1
    if f.quantity > EPS and f.processed >= f.quantity - EPS:
        return ProductionOrderStatus.COMPLETED, 2
    if f.actual_start is None:
        return ProductionOrderStatus.QUEUED, 3
    if f.open_interruption is not None:
        return ProductionOrderStatus.PAUSED, 4
    return ProductionOrderStatus.IN_PROGRESS, 5


def test_derive_production_order_status_matches_the_table_on_every_small_case():
    reached = set()
    for facts in production_order_facts():
        derivation = derive_production_order_status(facts)
        assert isinstance(derivation.value, ProductionOrderStatus)
        assert (derivation.value, derivation.rule) == _transcribed(facts), facts
        reached.add(derivation.rule)
    assert reached == {row.number for row in PRODUCTION_ORDER_STATUS.rows}
