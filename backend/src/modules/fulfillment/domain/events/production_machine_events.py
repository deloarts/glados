"""
Domain events emitted by production machine use cases.
Returned to the caller, the adapter decides what to do with them.
"""

from dataclasses import dataclass

from src.shared_kernel.domain.events.base import DomainEvent


@dataclass(frozen=True)
class ProductionMachineCreated(DomainEvent):
    machine_id: int
    internal_name: str
    actor_id: int


@dataclass(frozen=True)
class ProductionMachineUpdated(DomainEvent):
    machine_id: int
    internal_name: str
    actor_id: int


@dataclass(frozen=True)
class ProductionMachineArchived(DomainEvent):
    machine_id: int
    internal_name: str
    actor_id: int


@dataclass(frozen=True)
class ProductionMachineRestored(DomainEvent):
    machine_id: int
    internal_name: str
    actor_id: int
