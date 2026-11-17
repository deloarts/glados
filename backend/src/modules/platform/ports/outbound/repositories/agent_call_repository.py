"""
Persistence port of the agent call log. Append-only; read back for the
token owner's and the admin's view, for the call budgets and for the idle
revocation of agent tokens.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from typing import runtime_checkable

from src.modules.platform.domain.entities.agent_call import AgentCall
from src.modules.platform.domain.value_objects.agent_call import AgentTokenKind


@dataclass
class AgentCallFilterDto:
    user_id: int | None = None
    pat_id: int | None = None
    api_key_id: int | None = None
    tool: str | None = None
    created_ref: str | None = None
    skip: int | None = None
    limit: int | None = None


@runtime_checkable
class IAgentCallRepository(Protocol):
    async def append(self, entry: AgentCall) -> AgentCall: ...

    async def find_creators(self, refs: list[str]) -> dict[str, AgentCall]:
        """The call that created each of these records, keyed by reference,
        for the records an agent created; the others are left out."""
        ...

    async def get_page(self, filters: AgentCallFilterDto) -> tuple[int, list[AgentCall]]:
        """Newest first."""
        ...

    async def count_since(
        self, kind: AgentTokenKind, token_id: int, since: datetime, *, drafts_only: bool = False
    ) -> int:
        """The calls of one token since `since`; with `drafts_only`, only
        the successful calls that created records."""
        ...

    async def find_by_idempotency_key(
        self, kind: AgentTokenKind, token_id: int, tool: str, key: str
    ) -> AgentCall | None:
        """The successful call of this token and tool with this key."""
        ...

    async def last_called_at(
        self, kind: AgentTokenKind, token_ids: list[int]
    ) -> dict[int, datetime]:
        """The time of each token's latest call; a token never called is absent."""
        ...
