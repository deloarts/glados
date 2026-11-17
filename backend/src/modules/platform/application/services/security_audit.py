"""
Records security events in the durable security log. Every module records
through this service, which appends to the caller's transaction, so an
event commits with the change it describes and a rolled back change leaves
no event behind. A refused login writes nothing else, so the login use
cases commit its event themselves before raising.

The client address and user agent default to those of the current request
(request_context_middleware.py), so a use case only passes them when it
knows better, as the login commands do.

A use case built without the log, such as one a unit test constructs,
gets the disabled recorder, which records nothing.
"""

from typing import Any

from src.modules.platform.domain.entities.security_event import make_security_event
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.security_event_type import SecurityEventOutcome
from src.modules.platform.domain.value_objects.security_event_type import SecurityEventType
from src.modules.platform.infrastructure.logging.context import client_ip_var
from src.modules.platform.infrastructure.logging.context import user_agent_var
from src.modules.platform.ports.outbound.security_event_log_port import ISecurityEventLog


class SecurityAudit:
    def __init__(self, events: ISecurityEventLog | None) -> None:
        self._events = events

    @classmethod
    def disabled(cls) -> "SecurityAudit":
        """A recorder that records nothing."""
        return cls(None)

    @property
    def records(self) -> bool:
        """Whether this recorder writes anything, so a caller can skip work
        that only serves the log."""
        return self._events is not None

    async def record(
        self,
        event_type: SecurityEventType,
        *,
        actor: User | None,
        outcome: SecurityEventOutcome = SecurityEventOutcome.SUCCESS,
        target_user: User | None = None,
        target_user_id: int | None = None,
        target_id: int | None = None,
        detail: dict[str, Any] | None = None,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Appends one event to the caller's transaction; the caller
        commits. `actor` is whoever acted, or None when nobody could be
        identified, such as a login with an unknown name. A caller that
        has not loaded the target user passes `target_user_id` alone, and
        the entry then carries no target name."""
        if self._events is None:
            return
        await self._events.append(
            make_security_event(
                event_type,
                outcome=outcome,
                actor_user_id=actor.id if actor is not None else None,
                actor_username=actor.username if actor is not None else None,
                target_user_id=target_user.id if target_user is not None else target_user_id,
                target_username=target_user.username if target_user is not None else None,
                target_id=target_id,
                client_ip=client_ip or client_ip_var.get(),
                user_agent=user_agent or user_agent_var.get(),
                detail=detail,
            )
        )

    async def record_throttled(
        self,
        user: User | None,
        scopes: list[str],
        *,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """One throttle event per scope a failed attempt locked. Attempts
        refused while a lock holds are not recorded, so a flood of them
        cannot grow the log; the lock's own event marks where it began."""
        for scope in scopes:
            await self.record(
                SecurityEventType.LOGIN_THROTTLED,
                actor=user,
                outcome=SecurityEventOutcome.FAILURE,
                target_user=user,
                detail={"scope": scope},
                client_ip=client_ip,
                user_agent=user_agent,
            )
