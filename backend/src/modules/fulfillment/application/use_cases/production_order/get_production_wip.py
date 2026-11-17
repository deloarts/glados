"""
Live WIP (work-in-progress) read model, no new tables, purely a
query/aggregation over existing ProductionLot/LotPosition data. "Active
lots" = PARTIALLY_PLANNED, PLANNED, IN_PROGRESS, or ON_HOLD (not yet
DRAFT/COMPLETED/CANCELED). The repository pages every read, so the lots
are walked page by page until every active lot is in.
"""

from src.modules.fulfillment.application.dto.production_order_dto import WipLotResult
from src.modules.fulfillment.application.dto.production_order_dto import WipStageResult
from src.modules.fulfillment.domain.services.production_wip_service import compute_wip_summary
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    LotFilterDto,
)
from src.modules.platform.application.services.paging import fetch_all
from src.modules.platform.const import MAX_PAGE_SIZE

_ACTIVE_STATUSES = (
    LotStatus.PARTIALLY_PLANNED,
    LotStatus.PLANNED,
    LotStatus.IN_PROGRESS,
    LotStatus.ON_HOLD,
)


class GetProductionWip:
    def __init__(self, lot_repo: IProductionLotRepository) -> None:
        self._lots = lot_repo

    async def execute(self) -> list[WipLotResult]:
        lots = await fetch_all(
            lambda skip, limit: self._lots.get_multi(
                LotFilterDto(statuses=list(_ACTIVE_STATUSES), skip=skip, limit=limit)
            ),
            MAX_PAGE_SIZE,
        )
        lots.sort(key=lambda lot: lot.id)

        results: list[WipLotResult] = []
        for lot in lots:
            summary = compute_wip_summary(lot)
            results.append(
                WipLotResult(
                    id=lot.id,
                    public_id=lot.public_id,
                    lot_number=lot.lot_number,
                    quantity=lot.quantity,
                    status=lot.status,
                    priority=lot.priority,
                    made_item_id=lot.made_item_id,
                    made_item_part_number=lot.made_item_part_number,
                    made_item_revision=lot.made_item_revision,
                    made_item_article_name=lot.made_item_article_name,
                    raw_count=summary.raw_count,
                    finished_count=summary.finished_count,
                    stages=[
                        WipStageResult(
                            position_id=s.position_id,
                            sequence=s.sequence,
                            kind=s.kind,
                            status=s.status,
                            quantity=s.quantity,
                            quantity_completed=s.quantity_completed,
                            machine_names=s.machine_names,
                            supplier_name=s.supplier_name,
                        )
                        for s in summary.stages
                    ],
                )
            )
        return results
