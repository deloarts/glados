"""
One entry of the security log: a login, a throttle, or a change to who may
do what (accounts, permissions, groups, tokens, passwords, second factors).

The log is append-only and outlives the log retention, so an administrator
can still trace an incident months later. The actor's and the target
user's names are copied into the entry, so it still reads after a rename.
"""

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from typing import Any

from src.modules.platform.domain.value_objects.security_event_type import SecurityEventOutcome
from src.modules.platform.domain.value_objects.security_event_type import SecurityEventType
from src.shared_kernel.domain.entities.base import Entity
from src.shared_kernel.domain.services.clock import now_utc

# The stored length of a user agent. Browsers send far less, and a client
# that sends more must not be able to grow the log through it.
USER_AGENT_MAX_LENGTH = 255
CLIENT_IP_MAX_LENGTH = 64
USERNAME_MAX_LENGTH = 255


@dataclass
class SecurityEvent(Entity):
    occurred_at: datetime
    event_type: SecurityEventType
    outcome: SecurityEventOutcome
    actor_user_id: int | None
    actor_username: str | None
    target_user_id: int | None
    target_username: str | None
    # The token, key, group or session the event concerns. Its kind follows
    # from the event type.
    target_id: int | None
    client_ip: str | None
    user_agent: str | None
    # A few small facts about the event, such as the login method, the
    # refusal reason or the permissions added and removed.
    detail: dict[str, Any] = field(default_factory=dict)


def _bounded(value: str | None, length: int) -> str | None:
    if value is None:
        return None
    return value[:length]


def make_security_event(
    event_type: SecurityEventType,
    *,
    outcome: SecurityEventOutcome,
    actor_user_id: int | None,
    actor_username: str | None,
    target_user_id: int | None = None,
    target_username: str | None = None,
    target_id: int | None = None,
    client_ip: str | None = None,
    user_agent: str | None = None,
    detail: dict[str, Any] | None = None,
) -> SecurityEvent:
    """An unsaved event stamped now, with every free text bounded to its
    column."""
    return SecurityEvent(
        id=0,
        occurred_at=now_utc(),
        event_type=event_type,
        outcome=outcome,
        actor_user_id=actor_user_id,
        actor_username=_bounded(actor_username, USERNAME_MAX_LENGTH),
        target_user_id=target_user_id,
        target_username=_bounded(target_username, USERNAME_MAX_LENGTH),
        target_id=target_id,
        client_ip=_bounded(client_ip, CLIENT_IP_MAX_LENGTH),
        user_agent=_bounded(user_agent, USER_AGENT_MAX_LENGTH),
        detail=dict(detail or {}),
    )
