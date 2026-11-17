"""
The agent call log: every tool call an AI agent made through the MCP
surface. Everyone reads the calls of their own tokens; holders of
read:settings read every call, those of API keys included. Everyone may ask
which records of a list page an agent created, for the agent badge.
"""

from fastapi import Depends
from fastapi import Query
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.deps.agents import (
    get_find_agent_created_records_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.agents import get_list_agent_calls_use_case
from src.modules.platform.adapters.inbound.api.schemas.agent_schema import AgentCallResult
from src.modules.platform.adapters.inbound.api.schemas.agent_schema import AgentCreatedRecordResult
from src.modules.platform.adapters.inbound.api.schemas.agent_schema import (
    FindAgentCreatedRecordsRequest,
)
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse
from src.modules.platform.application.use_cases.agent.find_agent_created_records import (
    FindAgentCreatedRecords,
)
from src.modules.platform.application.use_cases.agent.list_agent_calls import ListAgentCalls
from src.modules.platform.const import MAX_PAGE_SIZE
from src.modules.platform.domain.entities.user import User
from src.modules.platform.ports.outbound.repositories.agent_call_repository import (
    AgentCallFilterDto,
)

router = APIRouter()


@router.get("/", response_model=PageResponse[AgentCallResult])
async def list_agent_calls(
    user_id: int | None = Query(
        default=None, description="Only the calls of this user's tokens (read:settings)."
    ),
    pat_id: int | None = Query(default=None, description="Only the calls of this PAT."),
    api_key_id: int | None = Query(
        default=None, description="Only the calls of this API key (read:settings)."
    ),
    tool: str | None = Query(default=None, max_length=64),
    created_ref: str | None = Query(
        default=None,
        max_length=128,
        description="Only the call that created this record, such as order:<public id>.",
    ),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=MAX_PAGE_SIZE),
    actor: User = Depends(get_current_active_user),
    use_case: ListAgentCalls = Depends(get_list_agent_calls_use_case),
) -> PageResponse[AgentCallResult]:
    page = await use_case.execute(
        actor,
        AgentCallFilterDto(
            user_id=user_id,
            pat_id=pat_id,
            api_key_id=api_key_id,
            tool=tool,
            created_ref=created_ref,
            skip=skip,
            limit=limit,
        ),
    )
    return PageResponse(items=page.items, total=page.total, limit=limit, skip=skip)


@router.post("/created-records", response_model=list[AgentCreatedRecordResult])
async def find_agent_created_records(
    body: FindAgentCreatedRecordsRequest,
    actor: User = Depends(get_current_active_user),
    use_case: FindAgentCreatedRecords = Depends(get_find_agent_created_records_use_case),
) -> list[AgentCreatedRecordResult]:
    """Which of the given records, each `<kind>:<public id>`, an agent created."""
    return await use_case.execute(actor, body.refs)
