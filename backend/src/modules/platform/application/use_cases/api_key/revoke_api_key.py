"""
Revocation is the only state change an API key's own record ever undergoes.
The backing service-account User is deactivated in the same transaction so
that even a stale/cached lookup by user id can't authenticate afterward,
and the revocation is recorded in the security log.
"""

from src.modules.platform.application.dto.api_key_dto import ApiKeyResult
from src.modules.platform.application.mappers.api_key_mapper import ApiKeyMapper
from src.modules.platform.application.services.api_key_issuing import api_key_event
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.services.security_audit import SecurityAudit
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import ApiKeyNotFoundError
from src.modules.platform.domain.services.api_key_rules import ApiKeyRules
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.repositories.api_key_repository import IApiKeyRepository
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc


class RevokeApiKey:
    def __init__(
        self,
        key_repo: IApiKeyRepository,
        user_repo: IUserRepository,
        uow: IUnitOfWork,
        audit: SecurityAudit | None = None,
    ) -> None:
        self._keys = key_repo
        self._users = user_repo
        self._uow = uow
        self._audit = audit or SecurityAudit.disabled()

    async def execute(self, actor: User, key_id: int) -> ApiKeyResult:
        ApiKeyRules.assert_can_manage(actor)

        key = found_or_raise(
            await self._keys.get_by_id(key_id), ApiKeyNotFoundError, f"API key #{key_id} not found."
        )

        if key.revoked_at is None:
            key.revoked_at = now_utc()
            saved_key = await self._keys.save(key)

            service_user = await self._users.get_by_id(key.user_id)
            if service_user is not None:
                service_user.is_active = False
                await self._users.save(service_user)

            await self._audit.record(
                api_key_event(saved_key, created=False),
                actor=actor,
                target_user=service_user,
                target_user_id=key.user_id,
                target_id=saved_key.id,
                detail={"name": saved_key.name},
            )
            await self._uow.commit()
        else:
            saved_key = key

        log.info(f"Revoked API key {saved_key.name!r} (ID={key_id}).")

        return ApiKeyMapper.to_result(saved_key)
