"""The procurement list of external work: the positions that go to a
supplier for an outside process, with when they can go, by when they must
go and when they come back."""

from typing import Annotated

from fastapi import Depends
from fastapi import Query
from fastapi.routing import APIRouter

from src.modules.fulfillment.adapters.inbound.api.deps.external_work import (
    get_external_work_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.external_work_schema import (
    ExternalWorkFilterParams,
)
from src.modules.fulfillment.application.dto.external_work_dto import ExternalWorkRowResult
from src.modules.fulfillment.application.use_cases.external_work.get_external_work import (
    GetExternalWork,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/", response_model=PageResponse[ExternalWorkRowResult])
async def read_external_work(
    params: Annotated[ExternalWorkFilterParams, Query()],
    actor: User = Depends(get_current_active_user),
    use_case: GetExternalWork = Depends(get_external_work_use_case),
) -> PageResponse[ExternalWorkRowResult]:
    result = await use_case.execute(params.to_query())
    return PageResponse(
        items=result.items, total=result.total, limit=params.limit, skip=params.skip or 0
    )
