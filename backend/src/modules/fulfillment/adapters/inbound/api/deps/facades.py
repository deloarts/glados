"""Planning & fulfillment's facades on the request's session, for the
factories of the modules above it that wire them into their use cases."""

from fastapi import Depends

from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_order_item_delivery_repo,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_order_item_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_production_lot_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_production_order_repo
from src.modules.fulfillment.application.facade.lot_scrap_records import LotScrapRecords
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


def get_lot_scrap_records(
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    production_order_repo: IProductionOrderRepository = Depends(get_production_order_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    order_item_delivery_repo: IOrderItemDeliveryRepository = Depends(get_order_item_delivery_repo),
) -> LotScrapRecords:
    return LotScrapRecords(
        lot_repo=lot_repo,
        production_order_repo=production_order_repo,
        order_item_repo=order_item_repo,
        order_item_delivery_repo=order_item_delivery_repo,
    )
