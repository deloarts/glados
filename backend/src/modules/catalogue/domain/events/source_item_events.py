"""
Domain events for the source item catalogue: status changes.
"""

from dataclasses import dataclass

from src.modules.catalogue.domain.value_objects.source_item_status import SourceItemCatalogueStatus
from src.shared_kernel.domain.events.base import DomainEvent


@dataclass(frozen=True)
class SourceItemStatusChanged(DomainEvent):
    item_id: int
    old_status: SourceItemCatalogueStatus
    new_status: SourceItemCatalogueStatus
    actor_id: int
