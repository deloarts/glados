"""
Resolves public UUIDs to their internal resource type and ID.
"""

from dataclasses import dataclass
from typing import Protocol
from typing import runtime_checkable
from uuid import UUID


@dataclass(frozen=True)
class ResolvedPublicId:
    resource: str
    id: int


@runtime_checkable
class IPublicIdResolver(Protocol):
    async def resolve(self, public_id: UUID) -> ResolvedPublicId | None: ...
