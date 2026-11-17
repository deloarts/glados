"""
Maps an agent call log row to its result DTO.
"""

from src.modules.platform.application.dto.agent_dto import AgentCallResult
from src.modules.platform.domain.entities.agent_call import AgentCall


class AgentCallMapper:
    @staticmethod
    def to_result(call: AgentCall) -> AgentCallResult:
        return AgentCallResult(
            public_id=call.public_id,
            called_at=call.called_at,
            user_id=call.user_id,
            token_kind=call.token_kind,
            token_name=call.token_name,
            tool=call.tool,
            arguments=call.arguments,
            outcome=call.outcome,
            duration_ms=call.duration_ms,
            error=call.error,
            created_refs=call.created_refs,
        )
