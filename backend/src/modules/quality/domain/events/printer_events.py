"""
Domain events emitted by printer use cases.
Returned to the caller, the adapter decides what to do with them.
"""

from dataclasses import dataclass

from src.shared_kernel.domain.events.base import DomainEvent


@dataclass(frozen=True)
class PrinterCreated(DomainEvent):
    printer_id: int
    name: str
    actor_id: int


@dataclass(frozen=True)
class PrinterUpdated(DomainEvent):
    printer_id: int
    name: str
    actor_id: int


@dataclass(frozen=True)
class PrinterArchived(DomainEvent):
    printer_id: int
    name: str
    actor_id: int


@dataclass(frozen=True)
class PrinterRestored(DomainEvent):
    printer_id: int
    name: str
    actor_id: int
