"""
Creates a terminal key: an API key whose service account holds exactly the
terminal connect permission and nothing else. It is the only way that
permission is ever granted. The key lets an unknown display register itself
as a pending terminal; it is refused everywhere else, the key router
included. Creating one needs manage:api_keys, like any other key, and the
security settings' token lifetime cap applies to its expiry, so while the
cap is set the key needs one. The key is recorded in the settings audit
trail and, through Platform's issuing step, in the security log.
"""

from collections.abc import Awaitable
from collections.abc import Callable

from src.modules.operations.application.dto.terminal_dto import CreateTerminalKeyCommand
from src.modules.operations.application.services.terminal_audit import record_terminal_audit
from src.modules.operations.domain.errors import TokenExpiryInPastError
from src.modules.operations.ports.outbound.operations_settings_repository import (
    IOperationsSettingsRepository,
)
from src.modules.platform.application.dto.api_key_dto import CreatedApiKeyResult
from src.modules.platform.application.services.api_key_issuing import issue_api_key
from src.modules.platform.application.services.security_audit import SecurityAudit
from src.modules.platform.application.services.token_lifetime_cap import read_token_lifetime_cap
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.api_key_rules import ApiKeyRules
from src.modules.platform.domain.services.token_lifetime import assert_expiry_date_allowed
from src.modules.platform.domain.services.token_permission_rules import TERMINAL_KEY_SCOPES
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.repositories.api_key_repository import IApiKeyRepository
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc


class CreateTerminalKey:
    def __init__(
        self,
        key_repo: IApiKeyRepository,
        user_repo: IUserRepository,
        uow: IUnitOfWork,
        settings_repo: IOperationsSettingsRepository,
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

    async def execute(self, actor: User, cmd: CreateTerminalKeyCommand) -> CreatedApiKeyResult:
        ApiKeyRules.assert_can_manage(actor)

        now = now_utc()
        if cmd.expires_at is not None and cmd.expires_at <= now:
            raise TokenExpiryInPastError("The expiry date of a terminal key must lie ahead.")
        cap = await read_token_lifetime_cap(self._settings.get_security)
        assert_expiry_date_allowed(cmd.expires_at, now, cap)

        # Recorded before issue_api_key commits, so the key and its audit
        # entry land in the same transaction.
        await record_terminal_audit(
            self._settings, actor, f"Terminal key {cmd.name!r} created by {actor.username}."
        )
        result = await issue_api_key(
            self._keys,
            self._users,
            self._uow,
            self._hash_password,
            actor=actor,
            name=cmd.name,
            permissions=list(TERMINAL_KEY_SCOPES),
            expires_at=cmd.expires_at,
            now=now,
            audit=self._audit,
        )
        log.info(f"Created terminal key {result.name!r} (ID={result.id}).")
        return result
