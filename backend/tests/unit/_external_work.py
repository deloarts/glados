"""The fakes' version of IProductionLotRepository.get_ids_with_external_work,
built on the domain rule the SQL query mirrors."""

from collections.abc import Iterable

from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.services.scheduling.external_work import (
    position_has_external_work,
)
from src.modules.fulfillment.domain.value_objects.lot_status import TERMINAL_LOT_STATUSES


def external_work_lot_ids(lots: Iterable[ProductionLot | None]) -> list[int]:
    """The ids of the lots that are not terminal and have open external
    work, ascending."""
    return sorted(
        lot.id
        for lot in lots
        if lot is not None
        and lot.status not in TERMINAL_LOT_STATUSES
        and any(position_has_external_work(p) for p in lot.positions)
    )
