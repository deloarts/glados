"""
Creates an API key together with its dedicated, non-interactive backing
service-account User in one transaction. The key authenticates as that
user for the rest of its lifetime, see src/modules/platform/domain/entities/api_key.py
for why.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from datetime import datetime
from datetime import timedelta

from src.modules.platform.application.dto.api_key_dto import CreateApiKeyCommand
from src.modules.platform.application.dto.api_key_dto import CreatedApiKeyResult
from src.modules.platform.application.services.api_key_issuing import issue_api_key
from src.modules.platform.application.services.security_audit import SecurityAudit
from src.modules.platform.application.services.token_lifetime_cap import read_token_lifetime_cap_for
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.api_key_rules import ApiKeyRules
from src.modules.platform.domain.services.token_lifetime import assert_lifetime_days_allowed
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.repositories.api_key_repository import IApiKeyRepository
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc


def _now() -> datetime:
    return now_utc()


class CreateApiKey:
    def __init__(
        self,
        key_repo: IApiKeyRepository,
        user_repo: IUserRepository,
        uow: IUnitOfWork,
        settings_repo: IPlatformSettingsRepository,
        *,
        hash_password_fn: Callable[[str], Awaitable[str]],
        audit: SecurityAudit | None = None,
    ) -> None:
        self._keys = key_repo
        self._users = user_repo
        self._uow = uow
        self._settings = settings_repo
        self._hash_password = hash_password_fn
        self._audit = audit

    async def execute(self, actor: User, cmd: CreateApiKeyCommand) -> CreatedApiKeyResult:
        ApiKeyRules.assert_can_manage(actor)
        ApiKeyRules.assert_permissions_allowed(cmd.permissions, actor)

        cap = await read_token_lifetime_cap_for(
            cmd.permissions, self._settings.get_security, lambda: self._settings.get_agents()
        )
        assert_lifetime_days_allowed(cmd.expires_in_days, cap)

        now = _now()
        expires_at = (
            now + timedelta(days=cmd.expires_in_days) if cmd.expires_in_days is not None else None
        )
        return await issue_api_key(
            self._keys,
            self._users,
            self._uow,
            self._hash_password,
            actor=actor,
            name=cmd.name,
            permissions=list(cmd.permissions),
            expires_at=expires_at,
            now=now,
            audit=self._audit,
        )
