"""
One tool call of an AI agent through the MCP surface. The log tells an
agent's actions apart from its owner's own: the row of every write the
agent caused records the owner as its changer, and this row records that
the change came through an agent, with which token and tool, and which
records it created. It is append-only and purged with the other credential
usage rows by the audit retention.
"""

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from typing import Any

from src.modules.platform.domain.value_objects.agent_call import AgentCallOutcome
from src.modules.platform.domain.value_objects.agent_call import AgentTokenKind
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class AgentCall(Entity):
    called_at: datetime  # UTC, aware
    user_id: int  # the token's owner, or the API key's service account
    token_kind: AgentTokenKind
    pat_id: int | None
    api_key_id: int | None
    token_name: str  # snapshot, so the row still names the token after it is deleted
    tool: str
    # The arguments as the agent sent them, cut to a bounded size. They are
    # the agent's own words and may carry text it read in Glados.
    arguments: dict[str, Any]
    outcome: AgentCallOutcome
    duration_ms: int
    error: str | None = None
    request_id: str | None = None
    # Public references of the records the call created, such as
    # "order:3f2c...", which the UI joins to mark a draft as an agent's.
    created_refs: list[str] = field(default_factory=list)
    # Sent with a draft call, so an agent that repeats the call gets the
    # first call's records back instead of a second draft.
    idempotency_key: str | None = None

    @property
    def token_id(self) -> int:
        token_id = self.pat_id if self.token_kind is AgentTokenKind.PAT else self.api_key_id
        assert token_id is not None
        return token_id
