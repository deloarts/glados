"""
Selectable-operator dropdown. Prefix `/production-operators`,
flat kebab-case, matching this repo's established convention (see
production_lots.py's docstring). Read-only: reuses PublicUserResponse
(already the canonical "live user reference" shape used elsewhere, e.g.
LotResponse.creator) rather than introducing a near-duplicate schema.
"""

from fastapi import Depends
from fastapi.routing import APIRouter
from pydantic import BaseModel
from pydantic import Field

from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_identify_operator_by_rfid_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import get_operators_use_case
from src.modules.fulfillment.application.use_cases.production_order.get_operators import (
    GetOperators,
)
from src.modules.fulfillment.application.use_cases.production_order.identify_operator_by_rfid import (
    IdentifyOperatorByRfid,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.schemas.user_schema import PublicUserResponse
from src.modules.platform.application.dto.user_dto import PublicUserResult
from src.modules.platform.domain.entities.user import User

router = APIRouter()


# Deliberately unpaginated: bounded per-classifier collection (the
# selectable-operator dropdown).
@router.get("/", response_model=list[PublicUserResponse])
async def read_production_operators(
    actor: User = Depends(get_current_active_user),
    use_case: GetOperators = Depends(get_operators_use_case),
) -> list[PublicUserResult]:
    return await use_case.execute(actor)


class OperatorIdentifyRequest(BaseModel):
    # In the body rather than the path: a path parameter would land in
    # access logs, browser history and proxy logs.
    rfid: str = Field(..., min_length=8)


@router.post("/identify", response_model=PublicUserResponse)
async def identify_operator_by_rfid(
    body: OperatorIdentifyRequest,
    actor: User = Depends(get_current_active_user),
    use_case: IdentifyOperatorByRfid = Depends(get_identify_operator_by_rfid_use_case),
) -> PublicUserResult:
    """Resolve an RFID chip to one of the operators this session could
    have picked from the dropdown.

    Requires an existing session, RFID identifies who is standing at the
    terminal, it never authenticates them.
    """
    return await use_case.execute(actor=actor, rfid=body.rfid)
