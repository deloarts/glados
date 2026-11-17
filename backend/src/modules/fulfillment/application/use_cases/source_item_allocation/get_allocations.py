"""
Mirrors bought_item_demand/get_allocations.py: the order-item lookup and
demand-summary assembly are shared via
src.modules.fulfillment.application.services.allocation_lookup, and only the entity types and
substitution strategy differ here. Unlike bought's _build_substitutions,
this one does NOT hit a catalogue repository for the substitute's display
labels, because the order item IS the substitute by rule
(SourceItemAllocationRules.assert_material_matches), and it is already
loaded via order_items_by_id, so no extra repository dependency is needed
here.
"""

from src.modules.fulfillment.application.dto.source_item_allocation_dto import (
    SourceItemAllocationResult,
)
from src.modules.fulfillment.application.dto.source_item_allocation_dto import (
    SourceItemDemandSummaryResult,
)
from src.modules.fulfillment.application.dto.source_item_allocation_dto import (
    SourceItemSubstitutionDetail,
)
from src.modules.fulfillment.application.services.allocation_fill import line_fill
from src.modules.fulfillment.application.services.allocation_lookup import build_demand_summary
from src.modules.fulfillment.application.services.allocation_lookup import (
    build_demand_summary_batch,
)
from src.modules.fulfillment.application.services.allocation_lookup import get_enriched_allocations
from src.modules.fulfillment.application.services.allocation_lookup import group_substitutions
from src.modules.fulfillment.application.services.allocation_lookup import mark_unit_mismatches
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.source_item_allocation import (
    SourceItemDemandAllocation,
)
from src.modules.fulfillment.domain.errors import SourceItemDemandNotFoundError
from src.modules.fulfillment.domain.services.source_item_allocation_service import (
    SourceItemAllocationQuantityService,
)
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import IOrderRepository
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemDemandRepository,
)


def _build_result(
    allocation: SourceItemDemandAllocation,
    order_item: OrderItem | None,
    order: Order | None,
) -> SourceItemAllocationResult:
    return SourceItemAllocationResult(
        demand_item_id=allocation.demand_item_id,
        order_item_id=allocation.order_item_id,
        source=allocation.source,
        quantity=allocation.quantity,
        substitute_source_item_id=allocation.substitute_source_item_id,
        substitute_reason=allocation.substitute_reason,
        order_number=order.order_number if order else None,
        order_supplier_name=order_item.supplier_name if order_item else None,
        item_order_code_1=order_item.item_order_code_1 if order_item else None,
        item_specification=order_item.item_specification if order_item else None,
        item_article_name=order_item.item_article_name if order_item else None,
        project_number=order_item.project_number if order_item else None,
        order_item_quantity=order_item.quantity if order_item else None,
        order_item_unit=order_item.unit if order_item else None,
    )


def _build_substitutions(
    allocations: list[SourceItemDemandAllocation],
    order_items_by_id: dict[int, OrderItem],
) -> list[SourceItemSubstitutionDetail]:
    """Group by substitute_source_item_id, summing quantity and keeping the
    first non-null reason. Mirrors bought_item_demand/get_allocations.py's
    _build_substitutions. Deliberately different from it in one respect: no
    catalogue repository lookup for the substitute's display labels, since
    by SourceItemAllocationRules.assert_material_matches the order item a
    substituting allocation points at IS the substitute, and it is already
    available in order_items_by_id (no new repository dependency needed
    here, unlike bought's catalogue_repo)."""
    groups = group_substitutions(allocations, lambda a: a.substitute_source_item_id)
    # The first allocation of each substitute that points at a loaded order
    # item names it.
    order_item_by_sid: dict[int, OrderItem] = {}
    for alloc in allocations:
        sid = alloc.substitute_source_item_id
        if sid is None:
            continue
        if sid not in order_item_by_sid and alloc.order_item_id is not None:
            order_item = order_items_by_id.get(alloc.order_item_id)
            if order_item is not None:
                order_item_by_sid[sid] = order_item

    result = []
    for sid, (reason, qty) in groups.items():
        order_item = order_item_by_sid.get(sid)
        if order_item is None:
            continue
        result.append(
            SourceItemSubstitutionDetail(
                substitute_source_item_id=sid,
                substitute_item_article_name=order_item.item_article_name,
                substitute_item_order_code_1=order_item.item_order_code_1,
                substitute_item_specification=order_item.item_specification,
                substitute_reason=reason,
                quantity=qty,
            )
        )
    return result


async def _build_substitutions_async(
    allocations: list[SourceItemDemandAllocation],
    order_items_by_id: dict[int, OrderItem],
) -> list[SourceItemSubstitutionDetail]:
    """Awaitable adapter for build_demand_summary(_batch), which expects an
    async substitution builder; this one needs no I/O."""
    return _build_substitutions(allocations, order_items_by_id)


class GetAllocationsForSourceItemDemand:
    """Returns all allocations for a demand, enriched with order number / supplier."""

    def __init__(
        self,
        allocation_repo: ISourceItemAllocationRepository,
        order_item_repo: IOrderItemRepository,
        order_repo: IOrderRepository,
        demand_repo: ISourceItemDemandRepository | None = None,
    ) -> None:
        self._allocations = allocation_repo
        self._order_items = order_item_repo
        self._orders = order_repo
        self._demands = demand_repo

    async def execute(self, demand_item_id: int) -> list[SourceItemAllocationResult]:
        allocations = await self._allocations.get_by_demand_item_id(demand_item_id)
        results = await get_enriched_allocations(
            allocations, self._order_items, self._orders, _build_result
        )
        if self._demands is None:
            return results
        return await mark_unit_mismatches(results, self._demands.get_by_ids)


class GetAllocationsForOrderItem:
    """Returns all source item demand allocations for a given order item."""

    def __init__(
        self,
        allocation_repo: ISourceItemAllocationRepository,
        order_item_repo: IOrderItemRepository,
        order_repo: IOrderRepository,
        demand_repo: ISourceItemDemandRepository | None = None,
    ) -> None:
        self._allocations = allocation_repo
        self._order_items = order_item_repo
        self._orders = order_repo
        self._demands = demand_repo

    async def execute(self, order_item_id: int) -> list[SourceItemAllocationResult]:
        allocations = await self._allocations.get_by_order_item_id(order_item_id)
        results = await get_enriched_allocations(
            allocations, self._order_items, self._orders, _build_result
        )
        if self._demands is None:
            return results
        return await mark_unit_mismatches(results, self._demands.get_by_ids)


class GetSourceItemDemandSummary:
    """
    Computes the full quantity breakdown for a source item demand:
    total, allocated, delivered, remaining, unallocated, in_transit.
    """

    def __init__(
        self,
        demand_repo: ISourceItemDemandRepository,
        allocation_repo: ISourceItemAllocationRepository,
        order_item_repo: IOrderItemRepository,
        order_repo: IOrderRepository,
        bought_allocation_repo: IBoughtItemAllocationRepository | None = None,
    ) -> None:
        """`bought_allocation_repo` reads the bought allocations on the same
        lines, which come before every source allocation in their fill."""
        self._demands = demand_repo
        self._allocations = allocation_repo
        self._order_items = order_item_repo
        self._orders = order_repo
        self._bought_allocations = bought_allocation_repo

    async def execute(self, demand_item_id: int) -> SourceItemDemandSummaryResult:
        return await build_demand_summary(
            demand_item_id=demand_item_id,
            get_demand=self._demands.get_by_id,
            not_found=lambda did: SourceItemDemandNotFoundError(
                f"Source item demand #{did} not found."
            ),
            get_allocations=self._allocations.get_by_demand_item_id,
            order_item_repo=self._order_items,
            order_repo=self._orders,
            compute_summary=SourceItemAllocationQuantityService.compute_summary,
            get_fill=lambda ids: line_fill(
                ids, bought=self._bought_allocations, source=self._allocations
            ),
            build_substitutions=_build_substitutions_async,
            result_cls=SourceItemDemandSummaryResult,
        )


class GetSourceItemDemandSummaryBatch:
    """
    Computes quantity summaries for multiple source item demands in one call.
    Used by list views to show remaining quantity per row without N+1 queries.
    See allocation_lookup.build_demand_summary_batch for the batching rationale.
    """

    def __init__(
        self,
        demand_repo: ISourceItemDemandRepository,
        allocation_repo: ISourceItemAllocationRepository,
        order_item_repo: IOrderItemRepository,
        order_repo: IOrderRepository,
        bought_allocation_repo: IBoughtItemAllocationRepository | None = None,
    ) -> None:
        """`bought_allocation_repo` reads the bought allocations on the same
        lines, which come before every source allocation in their fill."""
        self._demands = demand_repo
        self._allocations = allocation_repo
        self._order_items = order_item_repo
        self._orders = order_repo
        self._bought_allocations = bought_allocation_repo

    async def execute(self, demand_item_ids: list[int]) -> dict[int, SourceItemDemandSummaryResult]:
        return await build_demand_summary_batch(
            demand_item_ids=demand_item_ids,
            get_demands=self._demands.get_by_ids,
            get_allocations=self._allocations.get_by_demand_item_ids,
            order_item_repo=self._order_items,
            order_repo=self._orders,
            compute_summary=SourceItemAllocationQuantityService.compute_summary,
            get_fill=lambda ids: line_fill(
                ids, bought=self._bought_allocations, source=self._allocations
            ),
            build_substitutions=_build_substitutions_async,
            result_cls=SourceItemDemandSummaryResult,
        )
