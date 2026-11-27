"""
Post-manufacturing assessment prompted at a ProductionOrder's final
completion, the training dataset for AI-assisted time estimation. An
order has at most one active assessment. When a reversal takes back the
completion that completed the order, the assessment of its next final
completion replaces the earlier one, which is kept with `superseded_at`
set, so the data describes the run that actually finished the order.

`actual_minutes_per_piece` is asked explicitly rather than derived from
`actual_start`/`actual_end`, since elapsed time is a bad proxy (pauses,
preemption) and includes setup.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from src.modules.fulfillment.domain.value_objects.production_status import ComplexityClass
from src.shared_kernel.domain.entities.base import Entity

if TYPE_CHECKING:
    from src.modules.platform.domain.entities.user import User


@dataclass
class ManufacturingAssessment(Entity):
    production_order_id: int  # → ProductionOrder, one active assessment per order
    operator_id: int  # → User
    # Decimal minutes, at most two places, since whole minutes distort short
    # cycles.
    actual_minutes_per_piece: float
    actual_setup_minutes: int | None
    complexity: ComplexityClass
    note: str | None
    created: datetime
    # When a later assessment of the same order replaced this one; None
    # while it is the order's active assessment.
    superseded_at: datetime | None = None

    # ── Denormalized (read-only, populated by repository mapper) ──────
    operator: User | None = None
