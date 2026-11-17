"""Releases the allocations held on an order line or by a source demand,
shared by the use cases that remove or cancel those rows and by the lot
cancel cascade (lot_cascades.py), so all of them release the same way.

The helpers delete allocation rows and record intents only. The caller holds
the rows locked, touches what they return with its lifecycle reconciler and
runs it, and nothing here commits.
"""

from datetime import datetime

from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.source_item_demand_item import SourceItemDemandItem
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemAllocationRepository,
)
from src.modules.platform.domain.entities.user import User
from src.shared_kernel.domain.services.changelog_service import append_changelog


async def deallocate_order_item(
    item: OrderItem, allocation_repo: IBoughtItemAllocationRepository
) -> set[int]:
    """Removes every BoughtItemAllocation pointing at this order item and
    returns the affected demand ids, for the caller to touch with its
    lifecycle reconciler."""
    affected_demand_ids: set[int] = set()
    for alloc in await allocation_repo.get_by_order_item_id(item.id):
        affected_demand_ids.add(alloc.demand_item_id)
        await allocation_repo.delete(alloc)
    return affected_demand_ids


async def deallocate_source_item_order_item(
    item: OrderItem, allocation_repo: ISourceItemAllocationRepository
) -> set[int]:
    """Same as deallocate_order_item, for SourceItemDemandAllocation rows."""
    affected_demand_ids: set[int] = set()
    for alloc in await allocation_repo.get_by_order_item_id(item.id):
        affected_demand_ids.add(alloc.demand_item_id)
        await allocation_repo.delete(alloc)
    return affected_demand_ids


async def release_source_demand(
    demand: SourceItemDemandItem,
    allocations: ISourceItemAllocationRepository,
    actor: User,
    now: datetime,
    note: str,
) -> int:
    """Records the cancel intent on a source demand the caller holds locked
    and releases its allocations; `note` starts the changelog line. The
    caller saves nothing else on the demand, touches it with its reconciler
    and runs it. Returns how many allocations were released."""
    released = await allocations.get_by_demand_item_id(demand.id)
    for allocation in released:
        await allocations.delete(allocation)
    demand.canceled_at = now
    demand.changed = now
    demand.changes = append_changelog(
        demand.changes,
        actor.full_name,
        f"{note} Released {len(released)} allocation(s).",
    )
    return len(released)
