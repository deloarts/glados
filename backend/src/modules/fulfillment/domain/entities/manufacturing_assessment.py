"""
Post-manufacturing assessment prompted at a ProductionOrder's final
completion, the training dataset for AI-assisted time estimation. One
per completed production order (internal-only for now).

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
    production_order_id: int  # → ProductionOrder, unique, one assessment per order
    operator_id: int  # → User
    actual_minutes_per_piece: int
    actual_setup_minutes: int | None
    complexity: ComplexityClass
    note: str | None
    created: datetime

    # ── Denormalized (read-only, populated by repository mapper) ──────
    operator: User | None = None
