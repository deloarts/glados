"""
Deletes log and audit rows older than a cutoff, for the retention policy in
the admin settings. Kept apart from the per-table repositories because the
purge spans several tables and is only ever driven by the scheduler.
"""

from datetime import datetime
from typing import Protocol
from typing import runtime_checkable


@runtime_checkable
class IRetentionPurger(Protocol):
    async def purge_logs_before(self, cutoff: datetime) -> int:
        """Deletes application and request log rows older than `cutoff`
        and returns how many were removed."""
        ...

    async def purge_audit_before(self, cutoff: datetime) -> int:
        """Deletes credential usage and settings audit rows older than
        `cutoff` and returns how many were removed."""
        ...

    async def purge_idempotency_keys_before(self, cutoff: datetime) -> int:
        """Deletes idempotency keys created before `cutoff` and returns how
        many were removed."""
        ...
