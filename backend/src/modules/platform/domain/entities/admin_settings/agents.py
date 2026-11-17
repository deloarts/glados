"""
Domain entity for the AI agent settings singleton, the policy of the MCP
surface (`/mcp`) through which a user's agent reads Glados and prepares
drafts on the user's behalf.
"""

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime

from src.modules.platform.domain.exceptions import AgentAccessNotApprovedError
from src.shared_kernel.domain.entities.base import Entity
from src.shared_kernel.domain.services.service_url import assert_plain_http_url

DEFAULT_AGENT_TOKEN_MAX_LIFETIME_DAYS = 30
DEFAULT_AGENT_TOKEN_IDLE_REVOKE_DAYS = 14
DEFAULT_AGENT_CALLS_PER_MINUTE = 120
DEFAULT_AGENT_DRAFTS_PER_HOUR = 20
APPROVED_PROVIDERS_MAX_LENGTH = 500


def normalize_ai_policy_url(value: str | None) -> str | None:
    """The link to the company's AI policy shown in the users' consent
    dialog, or None."""
    if value is None or not value.strip():
        return None
    return assert_plain_http_url(value, "ai_policy_url")


@dataclass
class AdminAgentSettings(Entity):
    """How agents may use Glados.

    `enabled` switches the whole MCP surface. A token that may reach it
    (one carrying `use:mcp`) always needs an expiry within
    `token_max_lifetime_days`, also while the general token cap of the
    security settings is lifted, and is revoked once it has gone unused for
    `token_idle_revoke_days`. Tool results leave the company for the agent's
    model provider, so the names of people and every price or cost stay out
    of them unless `include_person_names` or `include_costs` lets them in.
    `allowed_origins` lists the browser origins that may call the surface;
    agent clients send no origin, so the default empty list refuses every
    browser. The two budgets bound one token's tool calls a minute and the
    drafts it creates an hour.

    Agent access needs the company's approval of sending Glados data to an
    AI provider, which an admin records once the company's policy allows
    it: `approved_providers` names the providers it covers, `ai_policy_url`
    links the policy, and `processing_approved_at` is when the approval was
    recorded. Every user confirms the same terms before their agent may
    call, and a confirmation counts only when it is newer than the
    approval, so changing what users confirmed asks all of them again.
    """

    enabled: bool = False
    token_max_lifetime_days: int = DEFAULT_AGENT_TOKEN_MAX_LIFETIME_DAYS
    token_idle_revoke_days: int = DEFAULT_AGENT_TOKEN_IDLE_REVOKE_DAYS
    include_person_names: bool = False
    include_costs: bool = False
    allowed_origins: list[str] = field(default_factory=list)
    calls_per_minute: int = DEFAULT_AGENT_CALLS_PER_MINUTE
    drafts_per_hour: int = DEFAULT_AGENT_DRAFTS_PER_HOUR
    approved_providers: str = ""
    ai_policy_url: str | None = None
    processing_approved_at: datetime | None = None

    @property
    def is_approved(self) -> bool:
        return self.processing_approved_at is not None

    @property
    def is_ready(self) -> bool:
        """Whether agents may connect: switched on and approved."""
        return self.enabled and self.is_approved

    def assert_valid(self) -> None:
        """Raises when the approval names no provider, or when agent access
        is switched on without the approval."""
        if self.is_approved and not self.approved_providers.strip():
            raise AgentAccessNotApprovedError(
                "Approving agent access requires naming the approved AI providers."
            )
        if self.enabled and not self.is_approved:
            raise AgentAccessNotApprovedError(
                "Agent access can only be switched on once the company's approval of AI "
                "processing is recorded."
            )
