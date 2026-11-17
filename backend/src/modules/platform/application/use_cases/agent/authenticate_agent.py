"""
Authenticates a request to the MCP surface. The surface takes a bearer
token only, a personal access token or an API key, so no session cookie and
therefore no cross-site request reaches it. Every request authenticates on
its own, so a revoked token, a permission the owner lost or maintenance mode
take effect on the agent's next call.

A token reaches the surface only while the agent settings switch it on with
the company's approval of AI processing recorded, and only when it carries
`use:mcp`, which its owner must hold to grant it. A personal access token
also needs its owner's current agent consent, so a user whose consent is
missing, withdrawn or older than the approved terms has their agent stopped
on its next call. An API key acts for a service account rather than a
person, so the company's approval covers it; it also needs API key
authentication switched on, and a terminal key never passes. A browser
origin outside the allowlist is refused before the token is looked at.
"""

from collections.abc import Callable

from src.modules.platform.application.dto.agent_dto import AgentPrincipal
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.services.validate_api_key import ValidateApiKey
from src.modules.platform.application.use_cases.pat.validate_pat import ValidatePat
from src.modules.platform.domain.exceptions import AgentAccessDisabledError
from src.modules.platform.domain.exceptions import AgentConsentRequiredError
from src.modules.platform.domain.exceptions import AgentOriginRefusedError
from src.modules.platform.domain.exceptions import AgentTokenNotAllowedError
from src.modules.platform.domain.exceptions import InvalidTokenError
from src.modules.platform.domain.services.agent_policy import consent_is_current
from src.modules.platform.domain.services.agent_policy import is_agent_token
from src.modules.platform.domain.services.agent_policy import origin_allowed
from src.modules.platform.domain.services.maintenance_policy import assert_maintenance_allows
from src.modules.platform.domain.value_objects.agent_call import AgentTokenKind
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.repositories.agent_consent_repository import (
    IAgentConsentRepository,
)
from src.modules.platform.ports.outbound.repositories.api_key_repository import IApiKeyRepository
from src.modules.platform.ports.outbound.repositories.pat_repository import IPatRepository
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository

PAT_PREFIX = "glados_pat_"
API_KEY_PREFIX = "glados_ak_"


class AuthenticateAgent:
    def __init__(
        self,
        settings: IPlatformSettingsRepository,
        pats: IPatRepository,
        api_keys: IApiKeyRepository,
        users: IUserRepository,
        consents: IAgentConsentRepository,
        *,
        hash_pat: Callable[[str], str],
        hash_api_key: Callable[[str], str],
    ) -> None:
        self._settings = settings
        self._pats = pats
        self._api_keys = api_keys
        self._users = users
        self._consents = consents
        self._hash_pat = hash_pat
        self._hash_api_key = hash_api_key

    async def execute(
        self, raw_token: str, *, origin: str | None, client_ip: str | None
    ) -> AgentPrincipal:
        agents = await self._settings.get_agents()
        if not agents.is_ready:
            raise AgentAccessDisabledError("Agent access is switched off in this Glados.")
        if not origin_allowed(origin, agents.allowed_origins):
            raise AgentOriginRefusedError(f"Origin {origin!r} may not call the agent interface.")
        if not raw_token:
            raise InvalidTokenError("A bearer token is required.")

        if raw_token.startswith(API_KEY_PREFIX):
            principal = await self._api_key_principal(raw_token)
        elif raw_token.startswith(PAT_PREFIX):
            principal = await self._pat_principal(raw_token)
        else:
            raise InvalidTokenError("Unknown token.")

        if not is_agent_token(principal.user.permissions):
            raise AgentTokenNotAllowedError(
                "This token may not be used by an agent; create one with use:mcp."
            )
        if principal.token_kind is AgentTokenKind.PAT and not consent_is_current(
            await self._consents.get_for_user(principal.user.id), agents
        ):
            raise AgentConsentRequiredError(
                "Confirm the agent consent in Glados under My Account before an agent can use "
                "this token."
            )
        assert_maintenance_allows(principal.user, await self._settings.get_maintenance(), client_ip)
        return principal

    async def _pat_principal(self, raw_token: str) -> AgentPrincipal:
        validate = ValidatePat(pat_repo=self._pats, user_repo=self._users, hash_fn=self._hash_pat)
        user, pat_id = await validate.execute(raw_token)
        token = found_or_raise(
            await self._pats.get_by_id(pat_id), InvalidTokenError, "Unknown token."
        )
        return AgentPrincipal(
            user=user, token_kind=AgentTokenKind.PAT, token_id=pat_id, token_name=token.name
        )

    async def _api_key_principal(self, raw_token: str) -> AgentPrincipal:
        if not (await self._settings.get_security()).enable_api_key_auth:
            raise AgentTokenNotAllowedError("API key authentication is switched off.")
        validate = ValidateApiKey(
            key_repo=self._api_keys, user_repo=self._users, hash_fn=self._hash_api_key
        )
        user, key_id = await validate.execute(raw_token)
        if Permission.CONNECT_TERMINALS in user.permissions:
            raise AgentTokenNotAllowedError("A terminal key cannot be used by an agent.")
        key = found_or_raise(
            await self._api_keys.get_by_id(key_id), InvalidTokenError, "Unknown token."
        )
        return AgentPrincipal(
            user=user, token_kind=AgentTokenKind.API_KEY, token_id=key_id, token_name=key.name
        )
