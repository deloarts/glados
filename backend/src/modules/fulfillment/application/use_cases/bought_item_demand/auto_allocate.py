"""
The automatic allocation of a bought item demand, through the one the
demand families share (_demand_family/auto_allocate.py). The demand draws on
the open order lines for its own catalogue item.
"""

from src.modules.fulfillment.application.dto.allocation_dto import AutoAllocateCommand
from src.modules.fulfillment.application.dto.allocation_dto import AutoAllocateResult
from src.modules.fulfillment.application.use_cases._demand_family.auto_allocate import (
    AutoAllocateOnOrderLines,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand._demand_spec import SPEC
from src.modules.fulfillment.domain.entities.bought_item_allocation import (
    BoughtItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.bought_item_demand_item import BoughtItemDemandItem
from src.modules.fulfillment.domain.entities.order_item import OrderItem


class AutoAllocate(
    AutoAllocateOnOrderLines[
        BoughtItemDemandItem,
        BoughtItemDemandAllocation,
        AutoAllocateCommand,
        AutoAllocateResult,
    ]
):
    _spec = SPEC
    _result = AutoAllocateResult

    async def _find_lines(self, demand: BoughtItemDemandItem) -> list[OrderItem]:
        return await self._order_items.get_by_bought_item_id(demand.item_id)

    def _line_matches(self, demand: BoughtItemDemandItem, line: OrderItem) -> bool:
        return line.bought_item_id == demand.item_id

    def _new_allocation(
        self, demand_id: int, order_item_id: int, quantity: float
    ) -> BoughtItemDemandAllocation:
        return BoughtItemDemandAllocation(
            demand_item_id=demand_id, order_item_id=order_item_id, quantity=quantity
        )
