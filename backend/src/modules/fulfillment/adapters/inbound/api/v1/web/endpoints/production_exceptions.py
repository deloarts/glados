"""
The planner's exception list. Prefix `/production-exceptions`. Read-only,
no table of its own: the shortfalls and delays are computed from the
stored rows on every read (get_planning_exceptions.py).
"""

from fastapi import Depends
from fastapi.routing import APIRouter

from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_planning_exceptions_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.planning_exception_schema import (
    PlanningExceptionResponse,
)
from src.modules.fulfillment.application.dto.production_lot_dto import PlanningExceptionResult
from src.modules.fulfillment.application.use_cases.production_lot.get_planning_exceptions import (
    GetPlanningExceptions,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.domain.entities.user import User

router = APIRouter()


# Unpaginated: the line part is capped by the use case, the lot part grows
# only with the live lots, as the WIP list does.
@router.get("/", response_model=list[PlanningExceptionResponse])
async def read_planning_exceptions(
    _: User = Depends(get_current_active_user),
    use_case: GetPlanningExceptions = Depends(get_planning_exceptions_use_case),
) -> list[PlanningExceptionResult]:
    """The shortfalls and delays a planner acts on: demands with a rest
    open again after lost pieces or a close short, made demands left short
    by a force-completed lot, live lots short of raw material and live lots
    late against their target date."""
    return await use_case.execute()
