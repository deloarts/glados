"""
The piece balance of every position of a lot
(domain/services/position_reconciliation.py), from its production orders'
completions, its supplier lines' deliveries and losses, and for position 1
the raw material that arrived.
"""

from dataclasses import asdict

from src.modules.fulfillment.application.dto.production_lot_dto import LotPositionBalanceResult
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.errors import LotNotFoundError
from src.modules.fulfillment.domain.services.position_reconciliation import balance_positions
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    IProductionOrderRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise


class GetLotPositionBalances:
    def __init__(
        self,
        lot_repo: IProductionLotRepository,
        order_repo: IProductionOrderRepository,
        order_item_repo: IOrderItemRepository,
    ) -> None:
        self._lots = lot_repo
        self._orders = order_repo
        self._order_items = order_item_repo

    async def execute(self, lot_id: int) -> list[LotPositionBalanceResult]:
        lot = found_or_raise(
            await self._lots.get_by_id(lot_id), LotNotFoundError, f"Lot #{lot_id} not found."
        )
        position_ids = [p.id for p in lot.positions]
        orders_by_position: dict[int, list[ProductionOrder]] = {}
        for order in await self._orders.get_by_lot_position_ids(position_ids):
            orders_by_position.setdefault(order.lot_position_id, []).append(order)
        # Every live line of a position lost pieces of it, the lines closed
        # short beside the newest one included.
        lost_by_position: dict[int, float] = {}
        for line in await self._order_items.get_by_lot_position_ids(position_ids):
            if line.lot_position_id is not None and line.canceled_at is None:
                lost_by_position[line.lot_position_id] = (
                    lost_by_position.get(line.lot_position_id, 0.0) + line.quantity_rejected_lost
                )
        raw_material_arrived = (
            await self._lots.get_raw_material_arrived_quantity(lot.input_demand_id)
            if lot.input_demand_id is not None
            else None
        )
        return [
            LotPositionBalanceResult(**asdict(balance))
            for balance in balance_positions(
                lot.positions,
                lot.quantity,
                orders_by_position,
                lost_by_position,
                raw_material_arrived,
            )
        ]
