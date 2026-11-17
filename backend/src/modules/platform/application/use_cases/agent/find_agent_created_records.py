"""
Tells which of the given records an AI agent created, and with which token,
so the web app can mark agent drafts in its lists. A record names its kind
and public id, such as `order:<public id>`. Every user may ask: the answer
says only that a record came from an agent and through which token, never
what the agent was asked, and a public id is known only to those who can
see the record.
"""

from src.modules.platform.application.dto.agent_dto import AgentCreatedRecordResult
from src.modules.platform.domain.entities.user import User
from src.modules.platform.ports.outbound.repositories.agent_call_repository import (
    IAgentCallRepository,
)


class FindAgentCreatedRecords:
    def __init__(self, calls: IAgentCallRepository) -> None:
        self._calls = calls

    async def execute(self, actor: User, refs: list[str]) -> list[AgentCreatedRecordResult]:
        del actor  # every signed in user may ask, see the module docstring
        creators = await self._calls.find_creators(list(dict.fromkeys(refs)))
        return [
            AgentCreatedRecordResult(
                ref=ref,
                token_name=call.token_name,
                token_kind=call.token_kind,
                user_id=call.user_id,
                called_at=call.called_at,
            )
            for ref, call in creators.items()
        ]
