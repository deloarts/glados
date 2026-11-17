"""
Reads the token lifetime cap for the use cases that create personal access
tokens, API keys and terminal keys (domain/services/token_lifetime.py), and
the stricter cap of a token that reaches the MCP surface.
"""

from collections.abc import Awaitable
from collections.abc import Callable

from src.modules.platform.domain.entities.admin_settings.agents import (
    DEFAULT_AGENT_TOKEN_MAX_LIFETIME_DAYS,
)
from src.modules.platform.domain.entities.admin_settings.agents import AdminAgentSettings
from src.modules.platform.domain.entities.admin_settings.security import AdminSecuritySettings
from src.modules.platform.domain.services.agent_policy import agent_token_lifetime_cap
from src.modules.platform.domain.services.agent_policy import is_agent_token


async def read_token_lifetime_cap(
    get_security: Callable[[], Awaitable[AdminSecuritySettings]],
) -> int:
    """The configured `token_max_lifetime_days`. The settings row is seeded
    on every start, so it is only missing in a database that never ran the
    seed; there the cap counts as lifted, which keeps token creation working
    instead of failing every request."""
    try:
        return (await get_security()).token_max_lifetime_days
    except RuntimeError:
        return 0


async def read_token_lifetime_cap_for(
    permissions: list[str],
    get_security: Callable[[], Awaitable[AdminSecuritySettings]],
    get_agents: Callable[[], Awaitable[AdminAgentSettings]],
) -> int:
    """The cap of a new token with these permissions. A token that reaches
    the MCP surface is also held to the agent cap, which applies even while
    the general cap is lifted (domain/services/agent_policy.py). A missing
    agent settings row counts as the default agent cap, never as no cap."""
    general = await read_token_lifetime_cap(get_security)
    if not is_agent_token(permissions):
        return general
    try:
        agent_cap = (await get_agents()).token_max_lifetime_days
    except RuntimeError:
        agent_cap = DEFAULT_AGENT_TOKEN_MAX_LIFETIME_DAYS
    return agent_token_lifetime_cap(general, agent_cap)
