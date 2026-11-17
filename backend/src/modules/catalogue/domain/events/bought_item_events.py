"""
Domain events for the bought-item and demand lifecycle: creation and
status changes.
"""

from dataclasses import dataclass

from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.shared_kernel.domain.events.base import DomainEvent


@dataclass(frozen=True)
class BoughtItemCreated(DomainEvent):
    item_id: int
    article_name: str
    creator_id: int


@dataclass(frozen=True)
class BoughtItemEdpPictureRequested(DomainEvent):
    """An item was created from, linked to, unlinked from or looked up in
    the EPLAN Data Portal; the picture worker brings the item's Data Portal
    picture in line with the part its own edp_part_id names, or removes it
    when there is none."""

    item_id: int


@dataclass(frozen=True)
class BoughtItemStatusChanged(DomainEvent):
    item_id: int
    article_name: str
    old_status: BoughtItemCatalogueStatus
    new_status: BoughtItemCatalogueStatus
    actor_id: int


@dataclass(frozen=True)
class DemandItemCreated(DomainEvent):
    demand_id: int
    item_id: int
    project_id: int
    creator_id: int


@dataclass(frozen=True)
class DemandItemStatusChanged(DomainEvent):
    demand_id: int
    item_article_name: str
    old_status: BoughtItemDemandStatus
    new_status: BoughtItemDemandStatus
    actor_id: int
    notify_on_delivery: bool
    creator_id: int
    # Set when the change was caused by an order item delivery
    order_id: int | None = None
    order_item_id: int | None = None
