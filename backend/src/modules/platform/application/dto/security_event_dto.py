"""
Results for the security log.
"""

from datetime import datetime
from typing import Any

from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.domain.value_objects.security_event_type import SecurityEventOutcome
from src.modules.platform.domain.value_objects.security_event_type import SecurityEventType


class SecurityEventResult(ResultBase):
    occurred_at: datetime
    event_type: SecurityEventType
    outcome: SecurityEventOutcome
    actor_user_id: int | None
    actor_username: str | None
    target_user_id: int | None
    target_username: str | None
    target_id: int | None
    client_ip: str | None
    user_agent: str | None
    detail: dict[str, Any]
