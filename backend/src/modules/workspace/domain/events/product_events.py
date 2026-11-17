"""
Domain events emitted by product use cases.
"""

from dataclasses import dataclass

from src.shared_kernel.domain.events.base import DomainEvent


@dataclass(frozen=True)
class ProductCreated(DomainEvent):
    product_id: int
    product_number: str
    actor_id: int
    designated_user_id: int


@dataclass(frozen=True)
class ProductUpdated(DomainEvent):
    product_id: int
    product_number: str
    actor_id: int
    designated_user_id: int
    old_designated_user_id: int
