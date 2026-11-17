"""
Retrieves orders (one or paginated), hydrating items, delivery records, and item-level
substitution info from the allocations and their demands, all in batched reads.
"""

from src.modules.fulfillment.application.dto.order_dto import DemandSubstitutionInfo
from src.modules.fulfillment.application.dto.order_dto import OrderResult
from src.modules.fulfillment.application.mappers.order_mapper import OrderMapper
from src.modules.fulfillment.domain.entities.bought_item_allocation import (
    BoughtItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.bought_item_demand_item import BoughtItemDemandItem
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.order_item_delivery import OrderItemDelivery
from src.modules.fulfillment.domain.entities.source_item_allocation import (
    SourceItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.source_item_demand_item import SourceItemDemandItem
from src.modules.fulfillment.domain.errors import OrderNotFoundError
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemDemandItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemDeliveryRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import IOrderRepository
from src.modules.fulfillment.ports.outbound.repositories.order_repository import OrderFilterDto
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemDemandRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.infrastructure.label_languages import resolve_label


def _group_by_order_item_id(
    deliveries: list[OrderItemDelivery],
) -> dict[int, list[OrderItemDelivery]]:
    grouped: dict[int, list[OrderItemDelivery]] = {}
    for d in deliveries:
        grouped.setdefault(d.order_item_id, []).append(d)
    return grouped


def _bought_substitution(
    alloc: BoughtItemDemandAllocation, demand: BoughtItemDemandItem | None
) -> DemandSubstitutionInfo | None:
    """The substitution a bought allocation records, read off its demand's
    hydrated catalogue item, or None when the demand or its item is gone."""
    if demand is None or demand.item is None:
        return None
    original = demand.item
    return DemandSubstitutionInfo(
        demand_item_id=alloc.demand_item_id,
        original_item_id=demand.item_id,
        original_item_order_code_1=original.order_code_1,
        original_item_article_name=original.article_name,
        substitute_reason=alloc.substitute_reason,
        quantity=alloc.quantity,
    )


def _source_substitution(
    alloc: SourceItemDemandAllocation, demand: SourceItemDemandItem | None
) -> DemandSubstitutionInfo | None:
    """SOURCE-line counterpart of _bought_substitution. Label rules mirror
    order_repository/_mappers.py's SOURCE-line display identity (dimension,
    falling back to "Source item #id"; order_code_1, falling back to
    "material | type")."""
    if demand is None or demand.source_item is None:
        return None
    original = demand.source_item
    original_order_code_1 = original.order_code_1 or " | ".join(
        part for part in (original.material, resolve_label(original.type_name)) if part
    )
    return DemandSubstitutionInfo(
        demand_item_id=alloc.demand_item_id,
        original_item_id=original.id,
        original_item_order_code_1=original_order_code_1,
        original_item_article_name=original.dimension or f"Source item #{original.id}",
        substitute_reason=alloc.substitute_reason,
        quantity=alloc.quantity,
    )


class PaginatedOrders:
    def __init__(self, total: int, items: list[OrderResult]):
        self.total = total
        self.items = items


class GetOrders:
    def __init__(
        self,
        order_repo: IOrderRepository,
        order_item_repo: IOrderItemRepository,
        allocation_repo: IBoughtItemAllocationRepository,
        demand_repo: IBoughtItemDemandItemRepository,
        delivery_repo: IOrderItemDeliveryRepository,
        source_allocation_repo: ISourceItemAllocationRepository,
        source_demand_repo: ISourceItemDemandRepository,
    ) -> None:
        self._orders = order_repo
        self._order_items = order_item_repo
        self._allocations = allocation_repo
        self._demands = demand_repo
        self._deliveries = delivery_repo
        self._source_allocations = source_allocation_repo
        self._source_demands = source_demand_repo

    async def _substitutions_by_item(
        self, items: list[OrderItem]
    ) -> dict[int, list[DemandSubstitutionInfo]]:
        """Every line's demand substitutions, bought ones first, in a fixed
        number of queries however many lines and allocations there are."""
        result: dict[int, list[DemandSubstitutionInfo]] = {item.id: [] for item in items}
        bought = [
            a
            for a in await self._allocations.get_by_order_item_ids([item.id for item in items])
            if a.substitute_item_id is not None
        ]
        demands = {
            d.id: d
            for d in await self._demands.get_by_ids(sorted({a.demand_item_id for a in bought}))
        }
        for alloc in bought:
            sub = _bought_substitution(alloc, demands.get(alloc.demand_item_id))
            if sub is not None and alloc.order_item_id in result:
                result[alloc.order_item_id].append(sub)

        source_line_ids = [item.id for item in items if item.source_item_id is not None]
        source = [
            a
            for a in await self._source_allocations.get_by_order_item_ids(source_line_ids)
            if a.substitute_source_item_id is not None
        ]
        source_demands = {
            d.id: d
            for d in await self._source_demands.get_by_ids(
                sorted({a.demand_item_id for a in source})
            )
        }
        for source_alloc in source:
            sub = _source_substitution(
                source_alloc, source_demands.get(source_alloc.demand_item_id)
            )
            if sub is not None and source_alloc.order_item_id in result:
                result[source_alloc.order_item_id].append(sub)
        return result

    async def get_one(self, order_id: int) -> OrderResult:
        order = found_or_raise(
            await self._orders.get_by_id(order_id),
            OrderNotFoundError,
            f"Order #{order_id} not found.",
        )
        items = await self._order_items.get_by_order_id(order_id)
        subs_by_item = await self._substitutions_by_item(items)
        deliveries_by_item = _group_by_order_item_id(
            await self._deliveries.get_by_order_item_ids([item.id for item in items])
        )
        return OrderMapper.to_result(
            order,
            items=items,
            substitutions_by_item_id=subs_by_item,
            delivery_records_by_item_id=deliveries_by_item,
        )

    async def get_many(self, filters: OrderFilterDto) -> PaginatedOrders:
        total, orders = await self._orders.get_multi(filters)
        order_ids = [o.id for o in orders]
        all_items = await self._order_items.get_by_order_ids(order_ids)
        items_by_order: dict[int, list[OrderItem]] = {oid: [] for oid in order_ids}
        for item in all_items:
            items_by_order[item.order_id].append(item)

        subs_by_item = await self._substitutions_by_item(all_items)
        deliveries_by_item = _group_by_order_item_id(
            await self._deliveries.get_by_order_item_ids([item.id for item in all_items])
        )

        return PaginatedOrders(
            total=total,
            items=[
                OrderMapper.to_result(
                    o,
                    items=items_by_order[o.id],
                    substitutions_by_item_id=subs_by_item,
                    delivery_records_by_item_id=deliveries_by_item,
                )
                for o in orders
            ],
        )
