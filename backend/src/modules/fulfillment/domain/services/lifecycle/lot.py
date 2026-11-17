"""Status and completed count of a production lot, derived from its quantity,
the derived statuses of its positions and its three intents.

A lot completes only when every position is complete, not when its last one
is, because a reordered or shrunk lot can finish its last position before an
earlier one. Hold is an overlay: a held lot shows ON_HOLD while its positions
alone would put it in DRAFT, PARTIALLY_PLANNED, PLANNED or IN_PROGRESS, and a
terminal result wins over the hold, so a held lot whose positions all
complete is COMPLETED. A lot whose quantity has shrunk to zero is SCRAPPED.
Force-completing records `force_completed_at`, which completes the lot even
while a position stays short.
"""

from collections.abc import Sequence

from src.modules.fulfillment.domain.services.lifecycle.facts import LotFacts
from src.modules.fulfillment.domain.services.lifecycle.rules import Derivation
from src.modules.fulfillment.domain.services.lifecycle.rules import DerivationTable
from src.modules.fulfillment.domain.services.lifecycle.rules import otherwise
from src.modules.fulfillment.domain.services.lifecycle.rules import rule
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.platform.domain.services.quantities import is_zero_quantity

_STARTED = (
    LotPositionStatus.IN_PROGRESS,
    LotPositionStatus.PARTIALLY_COMPLETED,
    LotPositionStatus.COMPLETED,
)


def _completed(facts: LotFacts) -> bool:
    if facts.force_completed_at is not None:
        return True
    statuses = facts.position_statuses
    return bool(statuses) and all(s == LotPositionStatus.COMPLETED for s in statuses)


LOT_STATUS = DerivationTable[LotFacts, LotStatus](
    key="lot_status",
    rules=(
        rule(1, "canceled_at set", LotStatus.CANCELED, lambda f: f.canceled_at is not None),
        rule(2, "quantity is zero", LotStatus.SCRAPPED, lambda f: is_zero_quantity(f.quantity)),
        rule(
            3,
            "force_completed_at set, or positions non-empty and every position COMPLETED",
            LotStatus.COMPLETED,
            _completed,
        ),
        rule(4, "held_at set", LotStatus.ON_HOLD, lambda f: f.held_at is not None),
        rule(
            5,
            "any position IN_PROGRESS, PARTIALLY_COMPLETED or COMPLETED",
            LotStatus.IN_PROGRESS,
            lambda f: lot_has_started(f.position_statuses),
        ),
        rule(
            6,
            "positions non-empty and none PENDING",
            LotStatus.PLANNED,
            lambda f: (
                bool(f.position_statuses)
                and all(s != LotPositionStatus.PENDING for s in f.position_statuses)
            ),
        ),
        rule(
            7,
            "any position not PENDING",
            LotStatus.PARTIALLY_PLANNED,
            lambda f: any(s != LotPositionStatus.PENDING for s in f.position_statuses),
        ),
    ),
    fallback=otherwise(8, LotStatus.DRAFT),
)


def lot_has_started(position_statuses: Sequence[str]) -> bool:
    """Whether any position of a lot has started production, the same test
    that makes a lot IN_PROGRESS, so it also holds while the lot is held or
    after it ended."""
    return any(s in _STARTED for s in position_statuses)


def derive_lot_status(facts: LotFacts) -> Derivation[LotStatus]:
    return LOT_STATUS.derive(facts)


def derive_lot_quantity_completed(completed_by_sequence: Sequence[float]) -> float:
    """The lot's completed count: its last position's, from the positions'
    completed counts in sequence order, or 0 without positions."""
    if not completed_by_sequence:
        return 0.0
    return completed_by_sequence[-1]
