"""
The Todo sources, `/todo`. The rows the Todo page builds its tasks from,
filtered to the open work so the page never pages through whole lists.
"""

from datetime import tzinfo

from fastapi import Depends
from fastapi import Query
from fastapi.routing import APIRouter

from src.modules.fulfillment.adapters.inbound.api.deps.dashboard import get_todo_sources_use_case
from src.modules.fulfillment.adapters.inbound.api.schemas.todo_schema import TodoSourcesResponse
from src.modules.fulfillment.application.dto.todo_dto import TodoSourcesResult
from src.modules.fulfillment.application.use_cases.todo.get_todo_sources import GetTodoSources
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.deps.misc import get_tenant_zone
from src.modules.platform.domain.entities.user import User
from src.shared_kernel.domain.services.clock import today_in

router = APIRouter()


# Unpaginated on purpose: the rows are the open work the page lists in
# full, not the history of every list.
@router.get("/sources", response_model=TodoSourcesResponse)
async def read_todo_sources(
    include_lots: bool = Query(
        default=True,
        description="Include the lots, whose tasks belong to Production Planning.",
    ),
    actor: User = Depends(get_current_active_user),
    zone: tzinfo = Depends(get_tenant_zone),
    use_case: GetTodoSources = Depends(get_todo_sources_use_case),
) -> TodoSourcesResult:
    """The meeting todos are the signed-in user's own."""
    return await use_case.execute(today_in(zone), include_lots=include_lots, user_id=actor.id)
