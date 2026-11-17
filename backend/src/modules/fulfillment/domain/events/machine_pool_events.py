"""
Domain events emitted by machine pool use cases.
Returned to the caller, the adapter decides what to do with them.
"""

from dataclasses import dataclass

from src.shared_kernel.domain.events.base import DomainEvent


@dataclass(frozen=True)
class MachinePoolCreated(DomainEvent):
    pool_id: int
    name: str
    actor_id: int


@dataclass(frozen=True)
class MachinePoolUpdated(DomainEvent):
    pool_id: int
    name: str
    actor_id: int


@dataclass(frozen=True)
class MachinePoolArchived(DomainEvent):
    pool_id: int
    name: str
    actor_id: int


@dataclass(frozen=True)
class MachinePoolRestored(DomainEvent):
    pool_id: int
    name: str
    actor_id: int
