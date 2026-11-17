"""Use case for retrieving a production lot's event history."""

from src.modules.fulfillment.application.dto.production_lot_dto import LotEventResult
from src.modules.fulfillment.application.mappers.production_lot_mapper import LotEventMapper
from src.modules.fulfillment.domain.errors import LotNotFoundError
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise


class GetLotEvents:
    def __init__(self, lot_repo: IProductionLotRepository) -> None:
        self._lots = lot_repo

    async def execute(self, lot_id: int) -> list[LotEventResult]:
        found_or_raise(
            await self._lots.get_by_id(lot_id), LotNotFoundError, f"Lot #{lot_id} not found."
        )

        return [LotEventMapper.to_result(e) for e in await self._lots.get_events(lot_id)]
