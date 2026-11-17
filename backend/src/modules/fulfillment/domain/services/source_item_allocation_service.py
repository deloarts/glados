"""
Order-item-backed counterpart of allocation_service.py, the source-item
side of the coverage protocol defined in allocation_coverage.py. Source
item demands are order-item-backed (like bought items), not lot-backed
(like made items), so this mirrors allocation_service.py's shape rather
than made_item_allocation_service.py's. Shares allocation_coverage.py's
OrderItemCoverageSource with allocation_service.py rather than duplicating
it. The demand's status is derived by the lifecycle reconciler.
"""

from collections.abc import Mapping
from collections.abc import Sequence

from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.source_item_allocation import (
    SourceItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.source_item_demand_item import SourceItemDemandItem
from src.modules.fulfillment.domain.errors import AllocationItemMismatchError
from src.modules.fulfillment.domain.services.allocation_coverage import DemandAllocationRules
from src.modules.fulfillment.domain.services.allocation_coverage import OrderItemCoverageSource
from src.modules.fulfillment.domain.services.allocation_coverage import compute_coverage_totals
from src.modules.fulfillment.domain.services.demand_terms import SOURCE_DEMAND_TERMS
from src.modules.fulfillment.domain.services.lifecycle.demand import SOURCE_FILL_RANK
from src.modules.fulfillment.domain.services.lifecycle.demand import FillEntry
from src.modules.fulfillment.domain.value_objects.demand_summary import DemandQuantitySummary
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemAllocationSource,
)


class SourceItemAllocationQuantityService:
    """
    Computes quantity summaries from raw allocation + order item lists.
    Deliberately receives pre-fetched lists rather than repos, keeps
    this layer pure and easily testable.
    """

    @staticmethod
    def compute_summary(
        demand: SourceItemDemandItem,
        allocations: list[SourceItemDemandAllocation],
        order_items_by_id: dict[int, OrderItem],
        fill: Mapping[int, Sequence[FillEntry]],
    ) -> DemandQuantitySummary:
        allocated, ordered, delivered, fulfilled_from_stock = compute_coverage_totals(
            allocations,
            OrderItemCoverageSource(order_items_by_id),
            SourceItemAllocationSource.STOCK,
            rank=SOURCE_FILL_RANK,
            fill=fill,
        )

        order_ids = tuple(sorted({oi.order_id for oi in order_items_by_id.values()}))

        return DemandQuantitySummary(
            demand_item_id=demand.id,
            unit=demand.unit,
            total=demand.quantity,
            allocated=allocated,
            ordered=ordered,
            delivered=delivered,
            fulfilled_from_stock=fulfilled_from_stock,
            order_ids=order_ids,
        )


class SourceItemAllocationRules(DemandAllocationRules):
    """The shared allocation guards in source item demand terms, and the
    material match only source item demands check."""

    terms = SOURCE_DEMAND_TERMS

    @staticmethod
    def assert_material_matches(
        demand: SourceItemDemandItem,
        order_item: OrderItem,
        substitute_source_item_id: int | None = None,
    ) -> None:
        """
        The order item must reference the exact same catalogue entry the
        demand is sourced from (order_item.bought_item_id for a
        bought-item-sourced demand, order_item.source_item_id for a
        source-item-sourced demand), UNLESS the demand is source-item-sourced
        and the caller explicitly declares a substitution by passing
        substitute_source_item_id, which must equal order_item.source_item_id,
        it acts as the caller's acknowledgement that the material mismatch is
        intentional (mirrors BoughtItemAllocationRules.assert_bought_item_matches).
        Bought-item-sourced demands stay non-substitutable: the caller cannot
        wave through a mismatch for them.
        """
        if demand.bought_item_id is not None:
            if demand.bought_item_id == order_item.bought_item_id:
                return
        elif demand.source_item_id is not None:
            if demand.source_item_id == order_item.source_item_id:
                return
            if (
                substitute_source_item_id is not None
                and substitute_source_item_id == order_item.source_item_id
            ):
                return
        raise AllocationItemMismatchError(
            f"Source item demand #{demand.id} is not for the same material as "
            f"order item #{order_item.id}. Pass "
            f"substitute_source_item_id={order_item.source_item_id} to declare this as "
            f"a substitution, if the demand is source-sourced."
        )
