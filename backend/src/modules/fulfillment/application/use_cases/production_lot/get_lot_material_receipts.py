"""
The material genealogy of a lot: every receipt of the raw material it
consumes, read from the delivery rows of the order lines its raw material
demand is allocated to, with the supplier's batch or heat number, the
delivery note and the certificate each receipt recorded. A lot without a
raw material demand has none.
"""

from src.modules.fulfillment.application.dto.production_lot_dto import LotMaterialReceiptResult
from src.modules.fulfillment.domain.errors import LotNotFoundError
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemDeliveryRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import IOrderRepository
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemAllocationRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise


class GetLotMaterialReceipts:
    def __init__(
        self,
        lot_repo: IProductionLotRepository,
        source_allocation_repo: ISourceItemAllocationRepository,
        order_item_repo: IOrderItemRepository,
        order_repo: IOrderRepository,
        delivery_repo: IOrderItemDeliveryRepository,
    ) -> None:
        self._lots = lot_repo
        self._source_allocations = source_allocation_repo
        self._order_items = order_item_repo
        self._orders = order_repo
        self._deliveries = delivery_repo

    async def execute(self, lot_id: int) -> list[LotMaterialReceiptResult]:
        lot = found_or_raise(
            await self._lots.get_by_id(lot_id), LotNotFoundError, f"Lot #{lot_id} not found."
        )
        if lot.input_demand_id is None:
            return []
        line_ids = sorted(
            {
                a.order_item_id
                for a in await self._source_allocations.get_by_demand_item_id(lot.input_demand_id)
                if a.order_item_id is not None
            }
        )
        if not line_ids:
            return []
        lines = {line.id: line for line in await self._order_items.get_by_ids(line_ids)}
        orders = {
            order.id: order
            for order in await self._orders.get_by_ids(
                sorted({line.order_id for line in lines.values()})
            )
        }
        receipts = [
            LotMaterialReceiptResult(
                delivery_id=d.id,
                order_item_id=d.order_item_id,
                order_id=lines[d.order_item_id].order_id,
                order_number=orders[lines[d.order_item_id].order_id].order_number,
                delivery_date=d.delivery_date,
                quantity=d.quantity,
                supplier_batch=d.supplier_batch,
                delivery_note_number=d.delivery_note_number,
                certificate_reference=d.certificate_reference,
                corrects_delivery_id=d.corrects_delivery_id,
            )
            for d in await self._deliveries.get_by_order_item_ids(line_ids)
            if d.order_item_id in lines and lines[d.order_item_id].order_id in orders
        ]
        return sorted(receipts, key=lambda r: (r.delivery_date, r.delivery_id))
