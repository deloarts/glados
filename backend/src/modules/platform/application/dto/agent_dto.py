"""
The caller of the MCP surface and the agent call log as the web API returns
it.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.agent_call import AgentCallOutcome
from src.modules.platform.domain.value_objects.agent_call import AgentTokenKind


@dataclass(frozen=True)
class AgentPrincipal:
    """Who an agent acts as. `user` carries the token's permissions only,
    capped at what the owner holds now. A PAT acts as its owner; an API key
    acts as its own service account."""

    user: User
    token_kind: AgentTokenKind
    token_id: int
    token_name: str

    @property
    def pat_id(self) -> int | None:
        return self.token_id if self.token_kind is AgentTokenKind.PAT else None

    @property
    def api_key_id(self) -> int | None:
        return self.token_id if self.token_kind is AgentTokenKind.API_KEY else None


class AgentCallResult(BaseModel):
    public_id: UUID
    called_at: datetime
    # The token's owner, or the API key's service account.
    user_id: int
    token_kind: AgentTokenKind
    token_name: str
    tool: str
    arguments: dict[str, Any]
    outcome: AgentCallOutcome
    duration_ms: int
    error: str | None
    created_refs: list[str]


class AgentCallPage(BaseModel):
    total: int
    items: list[AgentCallResult]


class AgentConsentStatusResult(BaseModel):
    """What the consent dialog shows the caller: whether agents may connect
    at all, whether the caller holds use:mcp, the terms the company
    approved, the consent text version to confirm and the caller's own
    confirmation."""

    access_ready: bool
    may_use_agents: bool
    approved_providers: str
    ai_policy_url: str | None
    include_person_names: bool
    include_costs: bool
    consent_version: int
    consented_at: datetime | None
    consent_current: bool


class GiveAgentConsentCommand(BaseModel):
    consent_version: int


class AgentCreatedRecordResult(BaseModel):
    """A record an agent created, such as `order:<public id>`, with the
    token that created it, for the agent badge in the web app's lists."""

    ref: str
    token_name: str
    token_kind: AgentTokenKind
    user_id: int
    called_at: datetime
