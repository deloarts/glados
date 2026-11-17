"""
Domain events emitted by machine downtime use cases.
Returned to the caller, the adapter decides what to do with them.
"""

from dataclasses import dataclass

from src.shared_kernel.domain.events.base import DomainEvent


@dataclass(frozen=True)
class MachineDowntimeStarted(DomainEvent):
    downtime_id: int
    machine_id: int
    reason: str
    actor_id: int


@dataclass(frozen=True)
class MachineDowntimeEnded(DomainEvent):
    downtime_id: int
    machine_id: int
    actor_id: int
