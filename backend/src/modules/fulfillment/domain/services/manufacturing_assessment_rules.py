"""
Rules of the manufacturing assessment: how precise its minutes may be, and
when a new assessment replaces the order's active one.

An order has one active assessment, recorded at the final completion. A
reversal can take that completion back and send the order to work again, so
the assessment of its next final completion describes the run that actually
finished the order. That one replaces the earlier assessment, which is kept
as superseded history instead of being overwritten.
"""

import math
from collections.abc import Iterable
from datetime import datetime

from src.modules.fulfillment.domain.entities.manufacturing_assessment import ManufacturingAssessment
from src.modules.fulfillment.domain.entities.production_order_completion import (
    ProductionOrderCompletion,
)
from src.shared_kernel.domain.services.clock import as_utc

# Decimal places an assessment's minutes per piece may carry. Whole minutes
# distort short cycles, and finer values would be noise.
ASSESSED_MINUTE_DECIMALS = 2


def assessed_minutes_refusal(value: float) -> str | None:
    """Why `value` cannot be stored as minutes per piece, or None. It must be
    finite, not negative and carry at most two decimal places."""
    if not math.isfinite(value):
        return "Minutes per piece must be a finite number."
    if value < 0:
        return "Minutes per piece must not be negative."
    scaled = value * 10**ASSESSED_MINUTE_DECIMALS
    if not math.isclose(scaled, round(scaled), abs_tol=1e-6):
        return f"Minutes per piece take at most {ASSESSED_MINUTE_DECIMALS} decimal places."
    return None


def is_assessment_replaceable(
    active: ManufacturingAssessment, completions: Iterable[ProductionOrderCompletion]
) -> bool:
    """Whether a new assessment may replace the order's active one: true once
    a reversal of one of the order's completions was booked after the active
    assessment was recorded, since the order then went back to work and its
    next final completion ends a different run. Without such a reversal the
    active assessment stands."""
    return any(_is_reversal_after(completion, active.created) for completion in completions)


def _is_reversal_after(completion: ProductionOrderCompletion, moment: datetime) -> bool:
    return completion.reverses_completion_id is not None and as_utc(completion.created) > as_utc(
        moment
    )
