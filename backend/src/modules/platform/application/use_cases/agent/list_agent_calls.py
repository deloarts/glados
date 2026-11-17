"""
Lists the agent call log. Everyone sees the calls made with their own
tokens; holders of read:settings see every call, including those of API
keys, whose service accounts nobody signs in as.
"""

from dataclasses import replace

from src.modules.platform.application.dto.agent_dto import AgentCallPage
from src.modules.platform.application.mappers.agent_call_mapper import AgentCallMapper
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.ports.outbound.repositories.agent_call_repository import (
    AgentCallFilterDto,
)
from src.modules.platform.ports.outbound.repositories.agent_call_repository import (
    IAgentCallRepository,
)


class ListAgentCalls:
    def __init__(self, calls: IAgentCallRepository) -> None:
        self._calls = calls

    async def execute(self, actor: User, filters: AgentCallFilterDto) -> AgentCallPage:
        if not actor.has_permission(Permission.READ_SETTINGS):
            filters = replace(filters, user_id=actor.id, api_key_id=None)
        total, items = await self._calls.get_page(filters)
        return AgentCallPage(total=total, items=[AgentCallMapper.to_result(c) for c in items])
