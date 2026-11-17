"""
A request a user sent with an Idempotency-Key header, kept so a retry of
the same request is answered from what the first one wrote instead of being
booked again. A row is written in the transaction of the request it guards,
so a request that fails leaves none; it is OPEN until the request's
response is settled and then COMPLETED with the resources it wrote.
"""

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime

from src.shared_kernel.domain.entities.base import Entity
from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


class IdempotencyKeyStatus(StrValueEnum):
    OPEN = "open"
    COMPLETED = "completed"


@dataclass(frozen=True)
class ResourceRef:
    """One resource a request wrote, as its kind and id, from which a
    replay rebuilds the response."""

    kind: str
    id: int


@dataclass(kw_only=True)
class IdempotencyKey(Entity):
    user_id: int
    key: str
    route: str
    request_hash: str
    status: IdempotencyKeyStatus
    created_at: datetime
    completed_at: datetime | None = None
    resources: list[ResourceRef] = field(default_factory=list)
