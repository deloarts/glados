"""
Pure function for building LotEvent records, the structured counterpart
to changelog_service.append_changelog. Keeps the ~20 call sites across
production_lot/ and production_order/ use cases to one short call each.
"""

from typing import Any

from src.modules.fulfillment.domain.entities.lot_event import LotEvent
from src.modules.fulfillment.domain.entities.lot_event import LotEventEntity
from src.modules.fulfillment.domain.value_objects.lot_event_type import LotEventType
from src.modules.platform.domain.entities.user import User
from src.shared_kernel.domain.services.clock import now_utc


def build_lot_event(
    lot_id: int,
    actor: User,
    event_type: LotEventType,
    entity: LotEventEntity,
    summary: str,
    entity_id: int | None = None,
    payload: dict[str, Any] | None = None,
) -> LotEvent:
    return LotEvent(
        id=0,
        lot_id=lot_id,
        occurred_at=now_utc(),
        actor_id=actor.id,
        actor_username=actor.username,
        actor_full_name=actor.full_name,
        event_type=event_type,
        entity=entity,
        entity_id=entity_id,
        summary=summary,
        payload=payload,
    )
