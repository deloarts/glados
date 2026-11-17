"""
Pieces a lot handed to a supplier for an external step are recorded as
provisions on the position. They are a physical fact: a position that holds
one keeps its supplier line, since without it the position reads unassigned
and a structure edit would delete the position with the record.
"""

from src.modules.fulfillment.domain.errors import LotPositionInUseError
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)


async def assert_no_provisions(lots: IProductionLotRepository, position_id: int) -> None:
    """Refuses a change that would lose the position's provisions."""
    if await lots.get_provisions(position_id):
        raise LotPositionInUseError(
            f"Position #{position_id} holds pieces handed to the supplier; settle them with "
            "the supplier first."
        )
