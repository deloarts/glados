"""
Maps a security log entry to its result DTO.
"""

from src.modules.platform.application.dto.security_event_dto import SecurityEventResult
from src.modules.platform.domain.entities.security_event import SecurityEvent


class SecurityEventMapper:
    @staticmethod
    def to_result(e: SecurityEvent) -> SecurityEventResult:
        return SecurityEventResult(
            id=e.id,
            public_id=e.public_id,
            occurred_at=e.occurred_at,
            event_type=e.event_type,
            outcome=e.outcome,
            actor_user_id=e.actor_user_id,
            actor_username=e.actor_username,
            target_user_id=e.target_user_id,
            target_username=e.target_username,
            target_id=e.target_id,
            client_ip=e.client_ip,
            user_agent=e.user_agent,
            detail=e.detail,
        )
