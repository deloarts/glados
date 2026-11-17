"""
Marker base class every published domain event derives from. It carries no
fields and no behaviour; its only purpose is to give the event bus port and
the outbox/registry code in src/modules/platform/infrastructure/events/ a real type to name
instead of `Any`.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DomainEvent:
    """Base of every event class in src/domain/events/*_events.py."""
