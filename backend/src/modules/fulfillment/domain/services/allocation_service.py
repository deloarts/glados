"""
Pure domain logic for the allocation quantity maths and the allocation
guards of bought item demands. The demand's status is derived by the
lifecycle reconciler. No I/O. Takes plain values, returns plain values.
"""

from collections.abc import Mapping
from collections.abc import Sequence

from src.modules.catalogue.domain.value_objects.bought_item_status import AllocationSource
from src.modules.fulfillment.domain.entities.bought_item_allocation import (
    BoughtItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.bought_item_demand_item import BoughtItemDemandItem
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.errors import AllocationItemMismatchError
from src.modules.fulfillment.domain.services.allocation_coverage import DemandAllocationRules
from src.modules.fulfillment.domain.services.allocation_coverage import OrderItemCoverageSource
from src.modules.fulfillment.domain.services.allocation_coverage import compute_coverage_totals
from src.modules.fulfillment.domain.services.demand_terms import BOUGHT_DEMAND_TERMS
from src.modules.fulfillment.domain.services.lifecycle.demand import BOUGHT_FILL_RANK
from src.modules.fulfillment.domain.services.lifecycle.demand import FillEntry
from src.modules.fulfillment.domain.value_objects.demand_summary import DemandQuantitySummary


class AllocationQuantityService:
    """
    Computes quantity summaries from raw allocation + order item lists.
    Deliberately receives pre-fetched lists rather than repos, keeps
    this layer pure and easily testable.
    """

    @staticmethod
    def compute_summary(
        demand: BoughtItemDemandItem,
        allocations: list[BoughtItemDemandAllocation],
        order_items_by_id: dict[int, OrderItem],
        fill: Mapping[int, Sequence[FillEntry]],
    ) -> DemandQuantitySummary:
        """
        Computes the full quantity breakdown for a demand item.

        :param demand: the demand entity
        :param allocations: all BoughtItemDemandAllocation rows for this demand
        :param order_items_by_id: dict of order_item_id → OrderItem,
                                  used to check delivery status
        :param fill: the fill entries of those order items, from every
                     allocation on them (allocation_coverage.fill_by_reference)
        """
        allocated, ordered, delivered, fulfilled_from_stock = compute_coverage_totals(
            allocations,
            OrderItemCoverageSource(order_items_by_id),
            AllocationSource.STOCK,
            rank=BOUGHT_FILL_RANK,
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


class BoughtItemAllocationRules(DemandAllocationRules):
    """The shared allocation guards in bought item terms, and the item match
    only bought item demands check."""

    terms = BOUGHT_DEMAND_TERMS

    @staticmethod
    def assert_bought_item_matches(
        demand: BoughtItemDemandItem,
        order_item: OrderItem,
        substitute_item_id: int | None = None,
    ) -> None:
        """
        Demand and order item must reference the same catalogue item, unless the
        caller explicitly declares a substitution by passing substitute_item_id.
        substitute_item_id must equal order_item.bought_item_id, it acts as the
        caller's acknowledgement that the item mismatch is intentional.
        """
        if demand.item_id == order_item.bought_item_id:
            return
        if substitute_item_id is not None and substitute_item_id == order_item.bought_item_id:
            return
        raise AllocationItemMismatchError(
            f"Demand item #{demand.id} is for catalogue item #{demand.item_id}, "
            f"but order item #{order_item.id} is for catalogue item "
            f"#{order_item.bought_item_id}. Pass "
            f"substitute_item_id={order_item.bought_item_id} to declare this as a substitution."
        )
