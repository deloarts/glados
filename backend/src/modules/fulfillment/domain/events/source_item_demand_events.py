"""
Domain events for the raw material demands of lots: status changes.
"""

from dataclasses import dataclass

from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.shared_kernel.domain.events.base import DomainEvent


@dataclass(frozen=True)
class SourceItemDemandStatusChanged(DomainEvent):
    """The derived status of a lot's raw material demand changed.
    `material_name` names the material the way the lot detail does."""

    demand_id: int
    lot_id: int
    material_name: str
    old_status: SourceItemDemandStatus
    new_status: SourceItemDemandStatus
    actor_id: int
    notify_on_delivery: bool
    creator_id: int
