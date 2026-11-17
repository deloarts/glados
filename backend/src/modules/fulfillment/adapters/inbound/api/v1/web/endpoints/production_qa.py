"""
QA worklist read model. Prefix `/production-qa`, flat kebab-case, matching
this repo's convention (see production_lots.py's docstring). Read-only:
acting on a task goes through the existing production-order endpoints,
since a QA task IS a production order.

Reading the list needs no special permission: seeing what is waiting for
inspection is not privileged. Recording the result does, and that gate
lives where the write happens (write:inspections, see
record_production_order_completion.py and StartProductionOrder).
"""

from typing import Annotated

from fastapi import Depends
from fastapi import Query
from fastapi.routing import APIRouter

from src.modules.fulfillment.adapters.inbound.api.deps.production import get_qa_tasks_use_case
from src.modules.fulfillment.adapters.inbound.api.schemas.production_qa_schema import (
    QaTaskFilterParams,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_qa_schema import QaTaskResponse
from src.modules.fulfillment.application.dto.production_order_dto import QaTaskResult
from src.modules.fulfillment.application.use_cases.production_order.get_qa_tasks import GetQaTasks
from src.modules.fulfillment.application.use_cases.production_order.get_qa_tasks import (
    QaTaskFilterDto,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/", response_model=PageResponse[QaTaskResponse])
async def read_qa_tasks(
    params: Annotated[QaTaskFilterParams, Query()],
    _: User = Depends(get_current_active_user),
    use_case: GetQaTasks = Depends(get_qa_tasks_use_case),
) -> PageResponse[QaTaskResult]:
    total, items = await use_case.execute(
        QaTaskFilterDto(
            include_completed=params.include_completed,
            include_canceled=params.include_canceled,
            include_future=params.include_future,
            search=params.search,
            skip=params.skip or 0,
            limit=params.limit,
            order_by=params.order_by,
            order_dir=params.order_dir or "asc",
            status=[s.value for s in params.status] if params.status else None,
            inspection_method_ids=params.inspection_method_id,
            lot_number=params.lot_number,
            project_number=params.project_number,
            item_text=params.item_text,
            quantity_min=params.quantity_min,
            quantity_max=params.quantity_max,
            planned_start_from=params.planned_start_from,
            planned_start_to=params.planned_start_to,
            finished_from=params.finished_from,
            finished_to=params.finished_to,
            finished_by_ids=params.finished_by_id,
        ),
    )
    return PageResponse(items=items, total=total, limit=params.limit, skip=params.skip or 0)
