"""
Read-side use cases for demand allocations: fetching a demand item's
allocations, listing all allocations for a bought item, summarizing
allocation coverage for one demand, and batch-summarizing coverage for
many demands at once. The order-item lookup and demand-summary assembly
are shared with source_item_allocation/get_allocations.py via
src.modules.fulfillment.application.services.allocation_lookup; only the entity types and the
substitution-building strategy differ here.
"""

from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.ports.outbound.catalogue_queries import IBoughtItemQueries
from src.modules.fulfillment.application.dto.allocation_dto import AllocationResult
from src.modules.fulfillment.application.dto.allocation_dto import DemandSummaryResult
from src.modules.fulfillment.application.dto.allocation_dto import SubstitutionDetail
from src.modules.fulfillment.application.services.allocation_fill import line_fill
from src.modules.fulfillment.application.services.allocation_lookup import build_demand_summary
from src.modules.fulfillment.application.services.allocation_lookup import (
    build_demand_summary_batch,
)
from src.modules.fulfillment.application.services.allocation_lookup import get_enriched_allocations
from src.modules.fulfillment.application.services.allocation_lookup import group_substitutions
from src.modules.fulfillment.application.services.allocation_lookup import mark_unit_mismatches
from src.modules.fulfillment.domain.entities.bought_item_allocation import (
    BoughtItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.errors import DemandItemNotFoundError
from src.modules.fulfillment.domain.services.allocation_service import AllocationQuantityService
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemDemandItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import IOrderRepository


def _build_result(
    allocation: BoughtItemDemandAllocation,
    order_item: OrderItem | None,
    order: Order | None,
) -> AllocationResult:
    return AllocationResult(
        demand_item_id=allocation.demand_item_id,
        order_item_id=allocation.order_item_id,
        source=allocation.source,
        quantity=allocation.quantity,
        substitute_item_id=allocation.substitute_item_id,
        substitute_reason=allocation.substitute_reason,
        order_number=order.order_number if order else None,
        order_supplier_name=order_item.supplier_name if order_item else None,
        item_order_code_1=order_item.item_order_code_1 if order_item else None,
        item_article_name=order_item.item_article_name if order_item else None,
        project_number=order_item.project_number if order_item else None,
        order_item_quantity=order_item.quantity if order_item else None,
        order_item_unit=order_item.unit if order_item else None,
    )


async def _build_substitutions(
    allocations: list[BoughtItemDemandAllocation],
    catalogue_repo: IBoughtItemQueries,
    catalogue_cache: dict[int, BoughtItem | None] | None = None,
) -> list[SubstitutionDetail]:
    """catalogue_cache: optional, shared across a batch of calls (from
    GetDemandSummaryBatch) so a substitute item referenced by several
    demands is fetched at most once per batch instead of once per demand
    that substitutes it. None (the singular GetDemandSummary's caller)
    behaves exactly as before: a fresh, single-call-scoped lookup.
    `groups` below is always built from just this call's own
    `allocations`, never the cache, so a shared cache only dedupes the
    catalogue *fetch*, it never merges one demand's substitution totals
    into another's."""
    cache = catalogue_cache if catalogue_cache is not None else {}

    groups = group_substitutions(allocations, lambda a: a.substitute_item_id)

    result = []
    for sid, (reason, qty) in groups.items():
        if sid not in cache:
            cache[sid] = await catalogue_repo.get_by_id(sid)
        item = cache[sid]
        if item is None:
            continue
        result.append(
            SubstitutionDetail(
                substitute_item_id=sid,
                substitute_item_order_code_1=item.order_code_1,
                substitute_item_article_name=item.article_name,
                substitute_reason=reason,
                quantity=qty,
            )
        )
    return result


class GetAllocationsForDemand:
    """Returns all allocations for a demand item, enriched with order number / supplier."""

    def __init__(
        self,
        allocation_repo: IBoughtItemAllocationRepository,
        order_item_repo: IOrderItemRepository,
        order_repo: IOrderRepository,
        demand_repo: IBoughtItemDemandItemRepository | None = None,
    ) -> None:
        self._allocations = allocation_repo
        self._order_items = order_item_repo
        self._orders = order_repo
        self._demands = demand_repo

    async def execute(self, demand_item_id: int) -> list[AllocationResult]:
        allocations = await self._allocations.get_by_demand_item_id(demand_item_id)
        results = await get_enriched_allocations(
            allocations, self._order_items, self._orders, _build_result
        )
        if self._demands is None:
            return results
        return await mark_unit_mismatches(results, self._demands.get_by_ids)


class GetAllocationsForOrderItem:
    """Returns all demand allocations for a given order item, enriched with order number or
    supplier."""

    def __init__(
        self,
        allocation_repo: IBoughtItemAllocationRepository,
        order_item_repo: IOrderItemRepository,
        order_repo: IOrderRepository,
        demand_repo: IBoughtItemDemandItemRepository | None = None,
    ) -> None:
        self._allocations = allocation_repo
        self._order_items = order_item_repo
        self._orders = order_repo
        self._demands = demand_repo

    async def execute(self, order_item_id: int) -> list[AllocationResult]:
        allocations = await self._allocations.get_by_order_item_id(order_item_id)
        results = await get_enriched_allocations(
            allocations, self._order_items, self._orders, _build_result
        )
        if self._demands is None:
            return results
        return await mark_unit_mismatches(results, self._demands.get_by_ids)


class GetDemandSummary:
    """
    Computes the full quantity breakdown for a demand item:
    total, allocated, delivered, remaining, unallocated, in_transit.
    """

    def __init__(
        self,
        demand_repo: IBoughtItemDemandItemRepository,
        allocation_repo: IBoughtItemAllocationRepository,
        order_item_repo: IOrderItemRepository,
        order_repo: IOrderRepository,
        catalogue_repo: IBoughtItemQueries,
    ) -> None:
        self._demands = demand_repo
        self._allocations = allocation_repo
        self._order_items = order_item_repo
        self._orders = order_repo
        self._catalogue = catalogue_repo

    async def execute(self, demand_item_id: int) -> DemandSummaryResult:
        async def build_substitutions(
            allocations: list[BoughtItemDemandAllocation], _order_items_by_id: dict[int, OrderItem]
        ) -> list[SubstitutionDetail]:
            return await _build_substitutions(allocations, self._catalogue)

        return await build_demand_summary(
            demand_item_id=demand_item_id,
            get_demand=self._demands.get_by_id,
            not_found=lambda did: DemandItemNotFoundError(f"Demand item #{did} not found."),
            get_allocations=self._allocations.get_by_demand_item_id,
            order_item_repo=self._order_items,
            order_repo=self._orders,
            compute_summary=AllocationQuantityService.compute_summary,
            get_fill=lambda ids: line_fill(ids, bought=self._allocations),
            build_substitutions=build_substitutions,
            result_cls=DemandSummaryResult,
        )


class GetDemandSummaryBatch:
    """
    Computes quantity summaries for multiple demand items in one call.
    Used by list views to show remaining quantity per row without N+1 queries.
    See allocation_lookup.build_demand_summary_batch for the batching rationale.
    """

    def __init__(
        self,
        demand_repo: IBoughtItemDemandItemRepository,
        allocation_repo: IBoughtItemAllocationRepository,
        order_item_repo: IOrderItemRepository,
        order_repo: IOrderRepository,
        catalogue_repo: IBoughtItemQueries,
    ) -> None:
        self._demands = demand_repo
        self._allocations = allocation_repo
        self._order_items = order_item_repo
        self._orders = order_repo
        self._catalogue = catalogue_repo

    async def execute(self, demand_item_ids: list[int]) -> dict[int, DemandSummaryResult]:
        catalogue_cache: dict[int, BoughtItem | None] = {}

        async def build_substitutions(
            allocations: list[BoughtItemDemandAllocation], _order_items_by_id: dict[int, OrderItem]
        ) -> list[SubstitutionDetail]:
            return await _build_substitutions(allocations, self._catalogue, catalogue_cache)

        return await build_demand_summary_batch(
            demand_item_ids=demand_item_ids,
            get_demands=self._demands.get_by_ids,
            get_allocations=self._allocations.get_by_demand_item_ids,
            order_item_repo=self._order_items,
            order_repo=self._orders,
            compute_summary=AllocationQuantityService.compute_summary,
            get_fill=lambda ids: line_fill(ids, bought=self._allocations),
            build_substitutions=build_substitutions,
            result_cls=DemandSummaryResult,
        )
