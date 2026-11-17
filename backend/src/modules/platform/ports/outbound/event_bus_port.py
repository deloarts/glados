"""
Abstract event bus interface. Use cases publish domain events through this,
never a broker client directly. Consumers (notification handler, webhook
dispatcher) read from the underlying transport, not from this port.
"""

from typing import Protocol
from typing import runtime_checkable

from src.shared_kernel.domain.events.base import DomainEvent


@runtime_checkable
class IEventBus(Protocol):
    async def publish(self, event: DomainEvent) -> None:
        """Publish a domain event. Best-effort, implementations must not raise."""
        ...
