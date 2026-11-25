"""
Ends or shrinks a lot's raw material demand when the lot needs less of our
material: on a source switch, and when a supplier takes over all or part of
the lot's first position (lot_material_rules.py).

Settling ends a demand without losing what reached it. A demand nothing
reached yet is canceled and its allocations released. One that already got
pieces keeps them and is marked fulfilled, and its allocations on lines whose
pieces have not arrived are cut down to what did arrive, so the lines stay
with purchasing to cancel or close short. Resizing sets a new quantity, never
below what already reached the demand; a shrink releases the unarrived part
of its line allocations beyond the new quantity, newest lines first.

The caller holds the demand and the order lines it is allocated on locked
(`line_ids`), and touches the demand and those lines with its lifecycle
reconciler and runs it, which derives the demand and its neighbours.

`missing_material` says what a lot that gets a new demand still lacks, so an
approval or a restored material need never demands again what a settled
demand already brought; `demand_missing_material` creates that demand.
"""

from datetime import datetime
from typing import Protocol

from src.modules.fulfillment.application.services.allocation_release import release_source_demand
from src.modules.fulfillment.application.services.source_item_demand_factory import (
    build_source_item_demand,
)
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.source_item_demand_item import SourceItemDemandItem
from src.modules.fulfillment.domain.services.lifecycle.demand import SOURCE_FILL_RANK
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemDemandRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    SourceItemDemandFilterDto,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.quantities import quantity_eq
from src.modules.platform.domain.services.quantities import quantity_gt
from src.shared_kernel.domain.services.changelog_service import append_changelog


async def missing_material(
    lot: ProductionLot,
    demands: ISourceItemDemandRepository,
    allocations: ISourceItemAllocationRepository,
) -> tuple[float, str, float]:
    """What a new demand of the lot still has to bring, as (quantity, unit,
    items per unit). The lot's latest demand that was not canceled is one a
    settle ended at what arrived, whose allocations it cut down to those
    pieces, so the rest of it is what is missing. Without one, nothing
    arrived yet and the whole lot is."""
    _, latest = await demands.get_multi(
        SourceItemDemandFilterDto(
            lot_id=[lot.id], ignore_canceled=True, order_by="id", order_dir="desc", limit=1
        )
    )
    if not latest:
        return (lot.quantity, "pcs", 1.0)
    settled = latest[0]
    arrived = sum(a.quantity for a in await allocations.get_by_demand_item_id(settled.id))
    return (max(settled.quantity - arrived, 0.0), settled.unit, settled.items_per_unit)


async def demand_missing_material(
    actor: User,
    lot: ProductionLot,
    demands: ISourceItemDemandRepository,
    allocations: ISourceItemAllocationRepository,
    *,
    at_most: float | None = None,
) -> SourceItemDemandItem | None:
    """Creates and links a demand for what the lot still lacks
    (missing_material), at most `at_most` of it, and returns it, or None when
    nothing is missing. The caller saves the lot and touches the demand as
    created."""
    quantity, unit, items_per_unit = await missing_material(lot, demands, allocations)
    if at_most is not None:
        quantity = min(quantity, at_most)
    if not quantity_gt(quantity, 0.0):
        return None
    demand = await demands.save(
        build_source_item_demand(
            lot,
            actor,
            quantity=quantity,
            unit=unit,
            items_per_unit=items_per_unit,
            high_priority=False,
            notify_on_delivery=False,
            note=None,
            desired_delivery_date=None,
        )
    )
    lot.input_demand_id = demand.id
    lot.changes = append_changelog(
        lot.changes, actor.full_name, f"Linked source item demand #{demand.id}."
    )
    return demand


class LineRelease(Protocol):
    """The release of a demand's unarrived line allocations, which the
    source family's UnarrivedLineRelease provides."""

    async def line_ids(self, demand_id: int) -> set[int]: ...

    async def release(self, rank: int, demand_id: int, *, limit: float | None = None) -> float: ...


class LotMaterialDemand:
    """Settles and resizes source item demands; see the module docstring."""

    def __init__(
        self,
        demands: ISourceItemDemandRepository,
        allocations: ISourceItemAllocationRepository,
        line_release: LineRelease,
    ) -> None:
        self._demands = demands
        self._allocations = allocations
        self._line_release = line_release

    async def line_ids(self, demand_id: int) -> set[int]:
        """The order lines the demand holds allocations on, which the caller
        locks with the demand."""
        return await self._line_release.line_ids(demand_id)

    async def settle(
        self, actor: User, demand: SourceItemDemandItem, now: datetime, *, reason: str
    ) -> float:
        """Ends the demand and returns what arrived and stays with it, 0.0
        for a demand it canceled. `reason` names why, in the changelog."""
        if demand.status != SourceItemDemandStatus.OPEN:
            released = await self._line_release.release(SOURCE_FILL_RANK, demand.id)
            arrived = sum(
                a.quantity for a in await self._allocations.get_by_demand_item_id(demand.id)
            )
            if quantity_gt(arrived, 0.0):
                demand.fulfilled_manually_at = now
                demand.changed = now
                demand.changes = append_changelog(
                    demand.changes,
                    actor.full_name,
                    f"Demand settled ({reason}); kept the {arrived:.3f} {demand.unit} that "
                    f"arrived and released {released:.3f} {demand.unit} that had not.",
                )
                await self._demands.save(demand)
                return arrived
        await release_source_demand(
            demand, self._allocations, actor, now, f"Demand canceled ({reason})."
        )
        await self._demands.save(demand)
        return 0.0

    async def resize(
        self,
        actor: User,
        demand: SourceItemDemandItem,
        quantity: float,
        now: datetime,
        *,
        reason: str,
    ) -> float:
        """Sets the demand's quantity to `quantity`, or to what its
        allocations still hold when more already reached it, and returns the
        quantity it set."""
        allocated = sum(
            a.quantity for a in await self._allocations.get_by_demand_item_id(demand.id)
        )
        released = 0.0
        if quantity_gt(allocated, quantity):
            released = await self._line_release.release(
                SOURCE_FILL_RANK, demand.id, limit=allocated - quantity
            )
            allocated -= released
        new_quantity = max(quantity, allocated)
        if quantity_eq(new_quantity, demand.quantity):
            return demand.quantity
        note = (
            f"Quantity changed from {demand.quantity:g} to {new_quantity:g} {demand.unit} "
            f"({reason})"
        )
        if quantity_gt(released, 0.0):
            note += f"; released {released:.3f} {demand.unit} that had not arrived"
        demand.quantity = new_quantity
        demand.changed = now
        demand.changes = append_changelog(demand.changes, actor.full_name, f"{note}.")
        await self._demands.save(demand)
        return new_quantity
