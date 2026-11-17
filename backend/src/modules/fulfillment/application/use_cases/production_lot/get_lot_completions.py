"""Use case for retrieving the completion status of all positions in a lot."""

from src.modules.fulfillment.application.dto.production_lot_dto import LotPositionCompletionResult
from src.modules.fulfillment.domain.errors import LotNotFoundError
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise


class GetLotPositionCompletions:
    def __init__(self, lot_repo: IProductionLotRepository) -> None:
        self._lots = lot_repo

    async def execute(self, lot_id: int) -> list[LotPositionCompletionResult]:
        lot = found_or_raise(
            await self._lots.get_by_id(lot_id), LotNotFoundError, f"Lot #{lot_id} not found."
        )

        return [
            LotPositionCompletionResult(
                position_id=position.id,
                sequence=position.sequence,
                kind=position.kind,
                status=position.status,
                quantity=position.quantity,
                quantity_completed=position.quantity_completed,
            )
            for position in lot.positions
        ]
