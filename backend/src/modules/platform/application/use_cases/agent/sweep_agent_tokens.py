"""
The scheduled care of agent tokens, the PATs and API keys that carry
use:mcp. A token that has gone unused for the agent settings' idle days is
revoked, recorded in the security log with the reason "idle", and its owner
is told. The owner of a token that expires within EXPIRY_WARNING_DAYS is
told once, so an agent does not stop working without notice.

A token counts as used by its latest agent call, or from its creation when
it has none. An API key's service account is deactivated with the key, as a
manual revocation does. Runs under an advisory lock in one worker, hourly.
"""

from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta

from src.modules.platform.application.services.api_key_issuing import api_key_event
from src.modules.platform.application.services.paging import fetch_all
from src.modules.platform.application.services.security_audit import SecurityAudit
from src.modules.platform.const import MAX_PAGE_SIZE
from src.modules.platform.domain.entities.notification import make_notification
from src.modules.platform.domain.services.agent_policy import idle_since
from src.modules.platform.domain.services.agent_policy import is_agent_token
from src.modules.platform.domain.services.agent_policy import is_idle
from src.modules.platform.domain.value_objects.agent_call import AgentTokenKind
from src.modules.platform.domain.value_objects.notification_type import NotificationType
from src.modules.platform.domain.value_objects.security_event_type import SecurityEventType
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.repositories.agent_call_repository import (
    IAgentCallRepository,
)
from src.modules.platform.ports.outbound.repositories.api_key_repository import ApiKeyFilterDto
from src.modules.platform.ports.outbound.repositories.api_key_repository import IApiKeyRepository
from src.modules.platform.ports.outbound.repositories.notification_repository import (
    INotificationRepository,
)
from src.modules.platform.ports.outbound.repositories.pat_repository import IPatRepository
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc

EXPIRY_WARNING_DAYS = 3


@dataclass(frozen=True)
class AgentTokenSweepResult:
    revoked: int
    warned: int


@dataclass(frozen=True)
class _Token:
    kind: AgentTokenKind
    id: int
    name: str
    owner_id: int  # who is told: the PAT's owner, or the API key's creator
    created: datetime
    expires_at: datetime | None


class SweepAgentTokens:
    def __init__(
        self,
        settings: IPlatformSettingsRepository,
        pats: IPatRepository,
        api_keys: IApiKeyRepository,
        users: IUserRepository,
        calls: IAgentCallRepository,
        notifications: INotificationRepository,
        *,
        uow: IUnitOfWork,
        audit: SecurityAudit | None = None,
    ) -> None:
        self._settings = settings
        self._pats = pats
        self._api_keys = api_keys
        self._users = users
        self._calls = calls
        self._notifications = notifications
        self._uow = uow
        self._audit = audit or SecurityAudit.disabled()

    async def execute(self, now: datetime | None = None) -> AgentTokenSweepResult:
        now = now or now_utc()
        idle_days = (await self._settings.get_agents()).token_idle_revoke_days
        tokens = await self._agent_tokens()
        last_used = {
            kind: await self._calls.last_called_at(kind, [t.id for t in tokens if t.kind is kind])
            for kind in AgentTokenKind
        }

        revoked = warned = 0
        for token in tokens:
            used = last_used[token.kind].get(token.id)
            if is_idle(token.created, used, now, idle_days):
                await self._revoke(token, now, idle_since(token.created, used))
                revoked += 1
            elif token.expires_at is not None and token.expires_at - now <= timedelta(
                days=EXPIRY_WARNING_DAYS
            ):
                warned += await self._warn_expiry(token)

        if revoked or warned:
            await self._uow.commit()
            log.info("Agent token sweep: revoked %d idle token(s), warned %d.", revoked, warned)
        return AgentTokenSweepResult(revoked=revoked, warned=warned)

    async def _agent_tokens(self) -> list[_Token]:
        tokens = [
            _Token(AgentTokenKind.PAT, t.id, t.name, t.user_id, t.created, t.expires_at)
            for t in await self._pats.list_unrevoked_unexpired()
            if is_agent_token(t.permissions)
        ]
        keys = await fetch_all(
            lambda skip, limit: self._api_keys.get_multi(
                ApiKeyFilterDto(expiry="unexpired", skip=skip, limit=limit)
            ),
            MAX_PAGE_SIZE,
        )
        tokens += [
            _Token(AgentTokenKind.API_KEY, k.id, k.name, k.created_by_id, k.created, k.expires_at)
            for k in keys
            if k.revoked_at is None and is_agent_token(k.permissions)
        ]
        return tokens

    async def _revoke(self, token: _Token, now: datetime, unused_since: datetime) -> None:
        detail = {"name": token.name, "reason": "idle", "unused_since": unused_since.isoformat()}
        if token.kind is AgentTokenKind.PAT:
            pat = await self._pats.get_by_id(token.id)
            if pat is None or pat.revoked_at is not None:
                return
            pat.revoked_at = now
            await self._pats.save(pat)
            await self._audit.record(
                SecurityEventType.PAT_REVOKED,
                actor=None,
                target_user_id=pat.user_id,
                target_id=pat.id,
                detail=detail,
            )
        else:
            key = await self._api_keys.get_by_id(token.id)
            if key is None or key.revoked_at is not None:
                return
            key.revoked_at = now
            saved = await self._api_keys.save(key)
            service_user = await self._users.get_by_id(key.user_id)
            if service_user is not None:
                service_user.is_active = False
                await self._users.save(service_user)
            await self._audit.record(
                api_key_event(saved, created=False),
                actor=None,
                target_user=service_user,
                target_user_id=key.user_id,
                target_id=saved.id,
                detail=detail,
            )
        await self._notifications.add_for_event(
            make_notification(
                token.owner_id,
                NotificationType.AGENT_TOKEN_REVOKED,
                "Agent token revoked",
                f"The agent token {token.name!r} was revoked because no agent used it "
                f"since {unused_since.date().isoformat()}.",
                source_event_id=f"agent-token-revoked:{token.kind.value}:{token.id}",
            )
        )

    async def _warn_expiry(self, token: _Token) -> int:
        assert token.expires_at is not None
        inserted = await self._notifications.add_for_event(
            make_notification(
                token.owner_id,
                NotificationType.AGENT_TOKEN_EXPIRING,
                "Agent token expires soon",
                f"The agent token {token.name!r} expires on "
                f"{token.expires_at.date().isoformat()}. Create a new one to keep your "
                "agent connected.",
                source_event_id=f"agent-token-expiring:{token.kind.value}:{token.id}",
            )
        )
        return 1 if inserted else 0
