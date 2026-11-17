"""
Domain events emitted by project use cases.
Returned to the caller, the adapter decides what to do with them.
"""

from dataclasses import dataclass

from src.shared_kernel.domain.events.base import DomainEvent


@dataclass(frozen=True)
class ProjectCreated(DomainEvent):
    project_id: int
    project_number: str
    actor_id: int
    designated_user_id: int


@dataclass(frozen=True)
class ProjectUpdated(DomainEvent):
    project_id: int
    project_number: str
    actor_id: int
    designated_user_id: int
    old_designated_user_id: int


@dataclass(frozen=True)
class ProjectDeleted(DomainEvent):
    project_id: int
    project_number: str
    actor_id: int
