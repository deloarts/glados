"""
Records the physical outbound dispatch of parts to a supplier for an
EXTERNAL LotPosition, optional; positions without provision rows
fall back to the plain available-input cap. Rules when used: provided <=
available input from the predecessor position (hard); delivered <=
provided (warning, some suppliers source input themselves).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from datetime import datetime
from typing import TYPE_CHECKING

from src.shared_kernel.domain.entities.base import Entity

if TYPE_CHECKING:
    from src.modules.platform.domain.entities.user import User


@dataclass
class LotPositionProvision(Entity):
    lot_position_id: int  # → LotPosition
    quantity: float
    # The business day the dispatch is reported for, picked from a date
    # picker, deliberately NOT a captured instant. `created` below is the
    # precise moment the record was written.
    provision_date: date
    note: str | None
    creator_id: int
    created: datetime

    # ── Denormalized (read-only, populated by repository mapper) ──────
    creator: User | None = None
