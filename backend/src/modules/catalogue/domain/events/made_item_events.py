"""
Domain events for the made-item and demand lifecycle: creation and
status changes.
"""

from dataclasses import dataclass

from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.shared_kernel.domain.events.base import DomainEvent


@dataclass(frozen=True)
class MadeItemCreated(DomainEvent):
    item_id: int
    article_name: str
    creator_id: int


@dataclass(frozen=True)
class MadeItemStatusChanged(DomainEvent):
    item_id: int
    article_name: str
    old_status: MadeItemCatalogueStatus
    new_status: MadeItemCatalogueStatus
    actor_id: int


@dataclass(frozen=True)
class MadeItemDemandItemCreated(DomainEvent):
    demand_id: int
    made_item_id: int
    project_id: int
    creator_id: int


@dataclass(frozen=True)
class MadeItemDemandItemStatusChanged(DomainEvent):
    demand_id: int
    item_article_name: str
    old_status: MadeItemDemandStatus
    new_status: MadeItemDemandStatus
    actor_id: int
    notify_on_delivery: bool
    creator_id: int
