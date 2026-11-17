"""
Reads the answers of the idempotent production routes back from what their
first request recorded (services/idempotency.py): the production order or
the lot it booked on and the lots its disposition created, each a resource
of kind `created_lot:<disposition>`. The answers are built as the routes'
use cases build them.
"""

from src.modules.fulfillment.application.dto.production_lot_dto import ScrapPiecesResult
from src.modules.fulfillment.application.dto.production_order_dto import CreatedLotResult
from src.modules.fulfillment.application.dto.production_order_dto import ProductionOrderResult
from src.modules.fulfillment.application.mappers.production_lot_mapper import LotMapper
from src.modules.fulfillment.application.mappers.production_order_mapper import (
    ProductionOrderMapper,
)
from src.modules.fulfillment.domain.errors import LotNotFoundError
from src.modules.fulfillment.domain.errors import ProductionOrderNotFoundError
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    IProductionOrderRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.idempotency_key import ResourceRef

PRODUCTION_ORDER = "production_order"
LOT = "lot"
_CREATED_LOT = "created_lot:"


def created_lot_refs(created: list[CreatedLotResult]) -> list[ResourceRef]:
    return [ResourceRef(_CREATED_LOT + lot.disposition, lot.id) for lot in created]


def scrap_refs(result: ScrapPiecesResult) -> list[ResourceRef]:
    return [ResourceRef(LOT, result.lot.id), *created_lot_refs(result.created_lots)]


class ReplayReads:
    def __init__(self, orders: IProductionOrderRepository, lots: IProductionLotRepository) -> None:
        self._orders = orders
        self._lots = lots

    async def _created_lots(self, refs: tuple[ResourceRef, ...]) -> list[CreatedLotResult]:
        created: list[CreatedLotResult] = []
        for ref in refs:
            if not ref.kind.startswith(_CREATED_LOT):
                continue
            lot = await self._lots.get_by_id(ref.id)
            if lot is not None:
                created.append(
                    CreatedLotResult(
                        id=lot.id,
                        lot_number=lot.lot_number,
                        disposition=ref.kind.removeprefix(_CREATED_LOT),
                    )
                )
        return created

    async def production_order(self, refs: tuple[ResourceRef, ...]) -> ProductionOrderResult:
        order_id = next(r.id for r in refs if r.kind == PRODUCTION_ORDER)
        order = found_or_raise(
            await self._orders.get_by_id(order_id),
            ProductionOrderNotFoundError,
            f"Production order #{order_id} not found.",
        )
        result = ProductionOrderMapper.to_result(order)
        result.created_lots = await self._created_lots(refs)
        return result

    async def scrap(self, refs: tuple[ResourceRef, ...]) -> ScrapPiecesResult:
        lot_id = next(r.id for r in refs if r.kind == LOT)
        lot = found_or_raise(
            await self._lots.get_by_id(lot_id), LotNotFoundError, f"Lot #{lot_id} not found."
        )
        return ScrapPiecesResult(
            lot=LotMapper.to_summary(lot), created_lots=await self._created_lots(refs)
        )
