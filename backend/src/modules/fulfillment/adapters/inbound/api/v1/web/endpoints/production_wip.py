"""
Live work-in-progress read model. Prefix `/production-wip`, flat
kebab-case, matching this repo's established convention (see
production_lots.py's docstring). Read-only, no new tables, a pure
aggregation over existing ProductionLot/LotPosition data.
"""

from fastapi import Depends
from fastapi.routing import APIRouter

from src.modules.fulfillment.adapters.inbound.api.deps.production import get_production_wip_use_case
from src.modules.fulfillment.adapters.inbound.api.schemas.production_wip_schema import (
    WipLotResponse,
)
from src.modules.fulfillment.application.dto.production_order_dto import WipLotResult
from src.modules.fulfillment.application.use_cases.production_order.get_production_wip import (
    GetProductionWip,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.domain.entities.user import User

router = APIRouter()


# Unpaginated, but unlike the endpoints marked "Deliberately unpaginated"
# this list is not structurally bounded: it returns every in-progress lot
# across the whole shop and grows with production volume. Switching it to
# PageResponse would break the frontend, so it stays a plain list until a
# realistic ceiling for the number of lots in progress says otherwise.
@router.get("/", response_model=list[WipLotResponse])
async def read_production_wip(
    _: User = Depends(get_current_active_user),
    use_case: GetProductionWip = Depends(get_production_wip_use_case),
) -> list[WipLotResult]:
    return await use_case.execute()
