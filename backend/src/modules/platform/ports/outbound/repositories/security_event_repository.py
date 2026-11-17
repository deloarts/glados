"""
Repository interface for the security log: appending through the
ISecurityEventLog port and reading pages of it for the admin settings tab.
Nothing updates or deletes an entry, and the log retention leaves the table
alone.
"""

from dataclasses import dataclass
from datetime import date
from typing import Protocol
from typing import runtime_checkable

from src.modules.platform.domain.entities.security_event import SecurityEvent
from src.modules.platform.domain.value_objects.security_event_type import SecurityEventOutcome
from src.modules.platform.domain.value_objects.security_event_type import SecurityEventType
from src.modules.platform.ports.outbound.security_event_log_port import ISecurityEventLog


@dataclass
class SecurityEventFilterDto:
    skip: int | None = None
    limit: int | None = None
    event_type: SecurityEventType | None = None
    outcome: SecurityEventOutcome | None = None
    user_id: int | None = None  # the acting or the target user
    occurred_from: date | None = None  # inclusive calendar day
    occurred_to: date | None = None  # inclusive calendar day


@runtime_checkable
class ISecurityEventRepository(ISecurityEventLog, Protocol):
    async def list_page(self, filters: SecurityEventFilterDto) -> tuple[int, list[SecurityEvent]]:
        """The total and one page of the matching events, newest first."""
        ...
