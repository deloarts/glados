"""
Stores the idempotency keys of the requests that carried one. Writes only
flush; the request's own transaction commits them.
"""

from datetime import datetime
from typing import Protocol
from typing import runtime_checkable

from src.modules.platform.domain.entities.idempotency_key import IdempotencyKey
from src.modules.platform.domain.entities.idempotency_key import ResourceRef


@runtime_checkable
class IIdempotencyKeyRepository(Protocol):
    async def claim(self, record: IdempotencyKey) -> bool:
        """Inserts the key and returns True, or returns False without
        changing anything when the user already has a row for the key. A
        concurrent insert of the same key waits for the other transaction
        to end first."""
        ...

    async def get_by_user_and_key(self, user_id: int, key: str) -> IdempotencyKey | None: ...

    async def mark_completed(
        self, record_id: int, resources: list[ResourceRef], completed_at: datetime
    ) -> None:
        """Marks the key COMPLETED with the resources its request wrote."""
        ...
