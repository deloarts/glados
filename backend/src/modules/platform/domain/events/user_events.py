"""
Domain events emitted by user administration use cases.
"""

from dataclasses import dataclass

from src.shared_kernel.domain.events.base import DomainEvent


@dataclass(frozen=True)
class UserPermissionsChanged(DomainEvent):
    user_id: int
    actor_id: int


@dataclass(frozen=True)
class UserDeactivated(DomainEvent):
    user_id: int
    actor_id: int


@dataclass(frozen=True)
class UserForcedLogout(DomainEvent):
    user_id: int
    actor_id: int
