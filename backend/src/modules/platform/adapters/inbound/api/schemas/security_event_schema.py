"""
HTTP response schema for the security log.
"""

from datetime import datetime
from typing import Any

from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.domain.value_objects.security_event_type import SecurityEventOutcome
from src.modules.platform.domain.value_objects.security_event_type import SecurityEventType


class SecurityEventResponse(EntityResponse):
    occurred_at: datetime
    event_type: SecurityEventType
    outcome: SecurityEventOutcome
    actor_user_id: int | None
    actor_username: str | None
    target_user_id: int | None
    target_username: str | None
    # The token, key, group or session the event concerns, by event type.
    target_id: int | None
    client_ip: str | None
    user_agent: str | None
    # Small facts about the event, such as the login method, the refusal
    # reason or the permissions added and removed.
    detail: dict[str, Any]
