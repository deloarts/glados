"""Status of a production order, derived from its processed pieces, its
actual start, its open interruption and its cancel intent.

Processed pieces count accepted and rejected ones alike, because a rejected
piece used up the order's capacity too. An order completes when it has
processed its quantity, whatever its interruptions, and it is paused exactly
while an interruption is open.
"""

from src.modules.fulfillment.domain.services.lifecycle.facts import ProductionOrderFacts
from src.modules.fulfillment.domain.services.lifecycle.rules import Derivation
from src.modules.fulfillment.domain.services.lifecycle.rules import DerivationTable
from src.modules.fulfillment.domain.services.lifecycle.rules import otherwise
from src.modules.fulfillment.domain.services.lifecycle.rules import rule
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.platform.domain.services.quantities import quantity_ge
from src.modules.platform.domain.services.quantities import quantity_gt

PRODUCTION_ORDER_STATUS = DerivationTable[ProductionOrderFacts, ProductionOrderStatus](
    key="production_order_status",
    rules=(
        rule(
            1,
            "canceled_at set",
            ProductionOrderStatus.CANCELED,
            lambda f: f.canceled_at is not None,
        ),
        rule(
            2,
            "quantity > 0 and processed >= quantity",
            ProductionOrderStatus.COMPLETED,
            lambda f: quantity_gt(f.quantity, 0.0) and quantity_ge(f.processed, f.quantity),
        ),
        rule(
            3, "actual_start unset", ProductionOrderStatus.QUEUED, lambda f: f.actual_start is None
        ),
        rule(
            4,
            "an interruption with resumed_at unset exists",
            ProductionOrderStatus.PAUSED,
            lambda f: f.open_interruption is not None,
        ),
    ),
    fallback=otherwise(5, ProductionOrderStatus.IN_PROGRESS),
)


def derive_production_order_status(
    facts: ProductionOrderFacts,
) -> Derivation[ProductionOrderStatus]:
    return PRODUCTION_ORDER_STATUS.derive(facts)
