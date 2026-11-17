"""
Immutable, append-only audit record for a ProductionLot and its positions,
steps and production orders: the structured counterpart to the free-text
ProductionLot.changes, with a real actor, timestamp and machine-readable
fields, so a lot's history holds up in an ISO 9001 audit. entity_id is not a
foreign key because it points at three tables and must keep its meaning after
the row it names is deleted.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from typing import Literal

from src.modules.fulfillment.domain.value_objects.lot_event_type import LotEventType
from src.shared_kernel.domain.entities.base import Entity

# What a lot event is about. The API answers with exactly these, so a row
# naming anything else could not be read back.
type LotEventEntity = Literal["lot", "position", "step", "order"]


@dataclass
class LotEvent(Entity):
    lot_id: int
    occurred_at: datetime
    actor_id: int | None
    actor_username: str | None
    # Snapshot like actor_username, so the row still names its actor after
    # the account is renamed or removed.
    actor_full_name: str
    event_type: LotEventType
    entity: LotEventEntity
    entity_id: int | None
    summary: str
    payload: dict[str, Any] | None = None
