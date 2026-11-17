"""
Persistence port of the users' agent consents, one per user at most.
"""

from typing import Protocol
from typing import runtime_checkable

from src.modules.platform.domain.entities.agent_consent import AgentConsent


@runtime_checkable
class IAgentConsentRepository(Protocol):
    async def get_for_user(self, user_id: int) -> AgentConsent | None: ...

    async def save(self, consent: AgentConsent) -> AgentConsent:
        """Writes the user's consent without committing, replacing the one
        they gave before."""
        ...

    async def delete_for_user(self, user_id: int) -> bool:
        """Deletes the user's consent without committing. Returns whether
        there was one."""
        ...
