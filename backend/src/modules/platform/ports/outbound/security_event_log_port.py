"""
The write side of the security log, the port every module records its
security events through (application/services/security_audit.py). An
append flushes without committing, so the event commits or rolls back with
the change it records.
"""

from typing import Protocol
from typing import runtime_checkable

from src.modules.platform.domain.entities.security_event import SecurityEvent


@runtime_checkable
class ISecurityEventLog(Protocol):
    async def append(self, event: SecurityEvent) -> None:
        """Adds the event to the caller's transaction. Flushes without
        committing."""
        ...
