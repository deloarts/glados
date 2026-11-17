"""
The latest scrap record of a lot: the newest production order completion
that scrapped pieces, or the newest order item delivery whose rejected
pieces were lost at receipt, across every position of the lot. Quality &
documents prints the lot's scrap tag from it.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.errors import LotNotFoundError
from src.modules.fulfillment.domain.value_objects.rejection_outcome import RejectionOutcome
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemDeliveryRepository,
)
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


class ScrapRecordKind(StrEnum):
    PRODUCTION_ORDER_COMPLETION = "production_order_completion"
    ORDER_ITEM_DELIVERY = "order_item_delivery"


@dataclass(frozen=True)
class ScrapRecord:
    kind: ScrapRecordKind
    id: int


class LotScrapRecords:
    def __init__(
        self,
        lot_repo: IProductionLotRepository,
        production_order_repo: IProductionOrderRepository,
        order_item_repo: IOrderItemRepository,
        order_item_delivery_repo: IOrderItemDeliveryRepository,
    ) -> None:
        self._lots = lot_repo
        self._orders = production_order_repo
        self._order_items = order_item_repo
        self._deliveries = order_item_delivery_repo

    async def latest(self, lot_id: int) -> ScrapRecord | None:
        """The lot's latest scrap record, or None when it has none. Raises
        LotNotFoundError for an unknown lot."""
        lot = found_or_raise(
            await self._lots.get_by_id(lot_id), LotNotFoundError, f"Lot #{lot_id} not found."
        )
        return await self._find_latest_scrap_record(lot)

    async def _find_latest_scrap_record(self, lot: ProductionLot) -> ScrapRecord | None:
        candidates: list[tuple[datetime, ScrapRecordKind, int]] = []
        for position in lot.positions:
            for order in await self._orders.get_by_lot_position_id(position.id):
                candidates.extend(
                    (completion.created, ScrapRecordKind.PRODUCTION_ORDER_COMPLETION, completion.id)
                    for completion in await self._orders.get_completions(order.id)
                    if completion.quantity_scrap > 0
                )

            item = await self._order_items.get_by_lot_position_id(position.id)
            if item is None:
                continue
            candidates.extend(
                (delivery.created, ScrapRecordKind.ORDER_ITEM_DELIVERY, delivery.id)
                for delivery in await self._deliveries.get_by_order_item_id(item.id)
                if delivery.quantity_rejected > 0
                and delivery.rejection_outcome == RejectionOutcome.LOST
            )

        if not candidates:
            return None
        candidates.sort(key=lambda c: c[0])
        _, kind, record_id = candidates[-1]
        return ScrapRecord(kind, record_id)
